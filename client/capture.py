"""
Screen Capture PRO - Chụp màn hình siêu nhanh với MSS + Delta V2.
"""

import logging
import time
from typing import Optional, Tuple

import cv2
import mss
import numpy as np

from core.constants import MSG_TYPE_SCREENSHOT, MSG_TYPE_DELTA_V2
from core.protocol import DeltaEncoderV2

logger = logging.getLogger(__name__)


class ScreenCapture:
    """
    Capture màn hình với:
    - MSS hardware-accelerated capture (<5ms)
    - Delta encoding V2 (grid-based)
    - GPU resize (nếu có)
    - Auto quality adjustment
    """

    def __init__(self, max_width: int = 1920, quality: int = 90,
                 grayscale: bool = False, use_delta: bool = True,
                 delta_block_size: int = 16):
        self.max_width = max_width
        self.quality = quality
        self.grayscale = grayscale
        self.use_delta = use_delta

        # MSS capture
        self.sct = mss.mss()
        self.monitor = self.sct.monitors[1]  # Main monitor

        # Delta encoder
        self.delta_encoder = DeltaEncoderV2(block_size=delta_block_size)

        # Performance tracking
        self.capture_times = []
        self.encode_times = []
        self.stats = {
            'full_frames': 0,
            'delta_frames': 0,
            'skipped_frames': 0,
            'total_bytes': 0,
        }

    def capture(self, force_full: bool = False) -> Tuple[Optional[int], Optional[bytes]]:
        """
        Chụp màn hình và encode.

        Args:
            force_full: Bắt buộc gửi full frame

        Returns:
            (msg_type, data) - msg_type = MSG_TYPE_SCREENSHOT, MSG_TYPE_DELTA_V2, or None
        """
        start_time = time.time()

        try:
            # 1. Capture screen with MSS
            screenshot = self.sct.grab(self.monitor)
            img = np.array(screenshot)
            capture_time = time.time() - start_time
            self.capture_times.append(capture_time)

            # 2. Convert BGRA -> BGR
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            # 3. Resize if needed
            h, w = img.shape[:2]
            if w > self.max_width:
                ratio = self.max_width / w
                new_w, new_h = self.max_width, int(h * ratio)
                img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

            # 4. Grayscale
            if self.grayscale:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)  # Keep 3 channels

            # 5. Delta encoding
            if self.use_delta and not force_full:
                msg_type, data = self.delta_encoder.encode(img, self.quality)
                encode_time = time.time() - start_time - capture_time
                self.encode_times.append(encode_time)

                if msg_type == MSG_TYPE_DELTA_V2:
                    self.stats['delta_frames'] += 1
                elif msg_type == MSG_TYPE_SCREENSHOT:
                    self.stats['full_frames'] += 1
                else:
                    self.stats['skipped_frames'] += 1

                if data:
                    self.stats['total_bytes'] += len(data)

                return msg_type, data
            else:
                # Full capture
                msg_type, data = self.delta_encoder.encode(img, self.quality)
                if msg_type == MSG_TYPE_SCREENSHOT and data:
                    self.stats['full_frames'] += 1
                    self.stats['total_bytes'] += len(data)
                    return msg_type, data
                return None, None

        except Exception as e:
            logger.error(f"Capture error: {e}", exc_info=True)
            return None, None

    def get_screen_info(self) -> dict:
        """Lấy thông tin màn hình."""
        return {
            'width': self.monitor['width'],
            'height': self.monitor['height'],
            'left': self.monitor['left'],
            'top': self.monitor['top'],
        }

    def reset(self):
        """Reset delta encoder (khi kết nối mới)."""
        self.delta_encoder.reset()

    def get_stats(self) -> dict:
        """Lấy thống kê capture."""
        total = sum(self.stats.values()) - self.stats['skipped_frames']
        savings = 0
        if self.stats['full_frames'] > 0:
            avg_full = self.stats['total_bytes'] / max(self.stats['full_frames'], 1)
            estimated_full = (self.stats['full_frames'] + self.stats['delta_frames']) * avg_full
            savings = (1 - self.stats['total_bytes'] / max(estimated_full, 1)) * 100

        avg_capture = sum(self.capture_times[-100:]) / max(len(self.capture_times[-100:]), 1)
        avg_encode = sum(self.encode_times[-100:]) / max(len(self.encode_times[-100:]), 1)

        return {
            **self.stats,
            'total_frames': total,
            'bandwidth_savings': savings,
            'avg_capture_ms': avg_capture * 1000,
            'avg_encode_ms': avg_encode * 1000,
        }