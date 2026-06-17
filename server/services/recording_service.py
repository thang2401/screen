"""
Recording Service - Ghi hình session client thành video.
Hỗ trợ NVENC hardware encoding + CPU fallback.
"""

import asyncio
import logging
import os
import time
from typing import Dict, Optional
from datetime import datetime

import cv2
import numpy as np

from core.constants import RECORDING_DIR, RECORDING_FPS, RECORDING_CODEC
from server.config import RecordingConfig

logger = logging.getLogger(__name__)


class RecordingSession:
    """Một phiên ghi hình cho một client."""
    
    def __init__(self, client_id: str, output_dir: str, fps: int = 10,
                 codec: str = 'h264_nvenc', bitrate: str = '2M'):
        self.client_id = client_id
        self.fps = fps
        self.codec = codec
        self.bitrate = bitrate
        
        # Tạo filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.filename = f"{client_id}_{timestamp}.mp4"
        self.filepath = os.path.join(output_dir, client_id, self.filename)
        
        # Video writer
        self.writer = None
        self.frame_count = 0
        self.start_time = time.time()
        self.frame_size = None
        
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        
    def init_writer(self, width: int, height: int):
        """Khởi tạo video writer với kích thước frame."""
        self.frame_size = (width, height)
        
        # Thử NVENC trước
        fourcc = cv2.VideoWriter_fourcc(*'h264')
        writer = cv2.VideoWriter(self.filepath, fourcc, self.fps, self.frame_size)
        
        if not writer.isOpened():
            # Fallback to CPU
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(self.filepath, fourcc, self.fps, self.frame_size)
        
        self.writer = writer
        logger.info(f"Recording started: {self.filepath} ({width}x{height})")
        
    def write_frame(self, frame: np.ndarray):
        """Ghi một frame vào video."""
        if self.writer is None:
            h, w = frame.shape[:2]
            self.init_writer(w, h)
        
        if self.writer and self.writer.isOpened():
            self.writer.write(frame)
            self.frame_count += 1
            
    def close(self):
        """Đóng file video."""
        if self.writer:
            self.writer.release()
            duration = time.time() - self.start_time
            logger.info(f"Recording stopped: {self.filepath} | "
                       f"{self.frame_count} frames | {duration:.1f}s")
            self.writer = None
    
    @property
    def duration(self) -> float:
        return time.time() - self.start_time
    
    @property
    def size_mb(self) -> float:
        if os.path.exists(self.filepath):
            return os.path.getsize(self.filepath) / (1024 * 1024)
        return 0


class RecordingService:
    """
    Service ghi hình session client.
    Xử lý bất đồng bộ qua queue để không block main thread.
    """
    
    def __init__(self, config: RecordingConfig):
        self.config = config
        self.active_recordings: Dict[str, RecordingSession] = {}
        self._running = False
    
    async def start_recording(self, client_id: str) -> bool:
        """Bắt đầu ghi hình cho client."""
        if client_id in self.active_recordings:
            logger.warning(f"Already recording: {client_id}")
            return False
        
        session = RecordingSession(
            client_id=client_id,
            output_dir=self.config.output_dir,
            fps=self.config.fps,
            codec=self.config.codec,
            bitrate=self.config.bitrate,
        )
        
        self.active_recordings[client_id] = session
        logger.info(f"Recording started for client: {client_id}")
        return True
    
    async def stop_recording(self, client_id: str) -> bool:
        """Dừng ghi hình cho client."""
        session = self.active_recordings.pop(client_id, None)
        if session:
            session.close()
            logger.info(f"Recording stopped for client: {client_id}")
            return True
        return False
    
    async def process_frame(self, client_id: str, frame_data: bytes, msg_type: int):
        """Xử lý một frame từ queue recording."""
        session = self.active_recordings.get(client_id)
        if not session:
            return
        
        try:
            # Giải nén frame
            nparr = np.frombuffer(frame_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is not None:
                session.write_frame(frame)
                
                # Kiểm tra max duration
                if session.duration > self.config.max_duration_minutes * 60:
                    await self.stop_recording(client_id)
                    logger.info(f"Recording max duration reached: {client_id}")
        except Exception as e:
            logger.error(f"Recording frame error: {client_id} - {e}")
    
    def get_active_recordings(self) -> list:
        """Lấy danh sách đang ghi."""
        return [
            {
                'client_id': cid,
                'duration': s.duration,
                'frames': s.frame_count,
                'size_mb': s.size_mb,
                'filepath': s.filepath,
            }
            for cid, s in self.active_recordings.items()
        ]
    
    def get_recordings_by_client(self, client_id: str) -> list:
        """Lấy danh sách file ghi của client."""
        record_dir = os.path.join(self.config.output_dir, client_id)
        if not os.path.exists(record_dir):
            return []
        
        files = []
        for f in os.listdir(record_dir):
            if f.endswith('.mp4'):
                filepath = os.path.join(record_dir, f)
                files.append({
                    'filename': f,
                    'path': filepath,
                    'size_mb': os.path.getsize(filepath) / (1024 * 1024),
                    'created': os.path.getctime(filepath),
                })
        
        return sorted(files, key=lambda x: x['created'], reverse=True)
    
    def cleanup_old_recordings(self, max_age_hours: int = 168):
        """Xóa các file ghi cũ."""
        now = time.time()
        record_dir = self.config.output_dir
        
        for client_dir in os.listdir(record_dir):
            client_path = os.path.join(record_dir, client_dir)
            if not os.path.isdir(client_path):
                continue
            
            for f in os.listdir(client_path):
                filepath = os.path.join(client_path, f)
                age_hours = (now - os.path.getctime(filepath)) / 3600
                
                if age_hours > max_age_hours:
                    os.remove(filepath)
                    logger.info(f"Cleaned old recording: {filepath}")
    
    async def stop_all(self):
        """Dừng tất cả recording."""
        for client_id in list(self.active_recordings.keys()):
            await self.stop_recording(client_id)
        logger.info("All recordings stopped")