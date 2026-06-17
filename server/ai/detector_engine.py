import asyncio
import logging
import time
import numpy as np
import base64
import os
import cv2
import queue
from datetime import datetime
from typing import Dict, Any

from core.compression import CompressionManager
from core.state import global_state
from server.database.db_manager import db_manager
from server.database.models import AIEvent

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

logger = logging.getLogger(__name__)

class DetectorEngine:
    def __init__(self, frame_queue: asyncio.Queue, detection_interval: float = 2.0):
        self.frame_queue = frame_queue
        self.detection_interval = detection_interval
        self.running = False
        self.model = None
        self.last_detection_time: Dict[str, float] = {}

    def _init_model(self):
        if YOLO_AVAILABLE and self.model is None:
            logger.info("Initializing YOLOv8 model for AI Detector Engine...")
            try:
                self.model = YOLO('yolov8n.pt')
            except Exception as e:
                logger.error(f"Failed to load YOLO model: {e}")

    def _reconstruct_frame(self, data: Dict[str, Any]) -> np.ndarray:
        client_id = data['client_id']
        is_full = data.get('is_full_frame', False)
        
        # TỐI ƯU CỰC ĐỘ CHO HÀNG CHỤC MÁY: Bỏ qua hoàn toàn Delta Frame!
        # AI không cần thiết phải chạy trên từng frame nhỏ lẻ. Nó chỉ lấy Full Frame (2 giây / lần)
        if not is_full or not data.get('changes'):
            return None

        # Chỉ có 1 change cho Full Frame
        change = data['changes'][0]
        raw_b64 = change['data']
        if raw_b64.startswith("data:image/"):
            raw_b64 = raw_b64.split(",", 1)[1]
            
        img_data = base64.b64decode(raw_b64)
        frame = CompressionManager.decode_image(img_data)
        
        return frame

    async def _save_event_to_db(self, client_id: str, event_type: str, conf: float, path: str):
        try:
            async for session in db_manager.get_session():
                new_event = AIEvent(
                    mac_address=client_id, # Using client_id as unique ID for simplicity
                    event_type=event_type,
                    confidence=conf,
                    evidence_path=path
                )
                session.add(new_event)
                await session.commit()
                break # Just run once
        except Exception as e:
            logger.error(f"DB Insert failed: {e}")

    def _detect(self, frame: np.ndarray, client_id: str) -> list:
        alerts = []
        if not YOLO_AVAILABLE or self.model is None:
            return alerts
            
        try:
            results = self.model(frame, verbose=False)
            for r in results:
                for box in r.boxes:
                    cls_id = int(box.cls[0])
                    cls_name = self.model.names[cls_id]
                    conf = float(box.conf[0])
                    if conf > 0.6 and cls_name in ['cell phone', 'person']:
                        alerts.append((cls_name, conf))
        except Exception as e:
            logger.error(f"Detection failed: {e}")
        return alerts

    async def _processing_loop(self):
        await asyncio.to_thread(self._init_model)
        
        while self.running:
            try:
                data = await self.frame_queue.get()
                client_id = data.get('client_id')
                
                # 1. Reconstruct Frame from Delta Vector Math
                frame = await asyncio.to_thread(self._reconstruct_frame, data)
                if frame is not None:
                    # 2. Push to GUI Queue for instant rendering!
                    # queue.Queue.put_nowait is thread-safe and non-blocking.
                    try:
                        global_state.gui_queue.put_nowait((client_id, frame.copy()))
                    except queue.Full:
                        pass # Drop GUI frame if rendering is too slow
                        
                    # --- TẠM TẮT AI THEO YÊU CẦU ĐỂ TRÁNH NẶNG MÁY VÀ ĐẦY Ổ CỨNG ---
                    # # 3. Throttled AI Detection
                    # now = time.time()
                    # last_time = self.last_detection_time.get(client_id, 0)
                    # 
                    # if now - last_time >= self.detection_interval:
                    #     alerts = await asyncio.to_thread(self._detect, frame, client_id)
                    #     self.last_detection_time[client_id] = now
                    #     
                    #     # Process Alerts (Save Image + DB)
                    #     for cls_name, conf in alerts:
                    #         logger.warning(f"AI Alert {client_id}: {cls_name} ({conf:.2f})")
                    #         # Save evidence
                    #         dir_path = f"data/screenshots/{client_id}"
                    #         os.makedirs(dir_path, exist_ok=True)
                    #         filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                    #         filepath = os.path.join(dir_path, filename)
                    #         
                    #         await asyncio.to_thread(cv2.imwrite, filepath, frame)
                    #         # Async DB Insert
                    #         asyncio.create_task(self._save_event_to_db(client_id, cls_name, conf, filepath))
                    # --------------------------------------------------------------

                self.frame_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"AI Loop error: {e}")

    async def start(self):
        logger.info("Starting AI Detector Engine")
        self.running = True
        self.task = asyncio.create_task(self._processing_loop())

    def stop(self):
        self.running = False
        if hasattr(self, 'task'):
            self.task.cancel()
