import json
import base64
import numpy as np
from core.utils import ImageUtils
from core.compression import CompressionManager
from core.crypto_manager import CryptoManager
from core.protocol import Protocol
from core.constants import CommandTypes

class FrameEncoder:
    def __init__(self, key: bytes):
        self.crypto = CryptoManager(key)
        self.prev_frame = None
        self.base_quality = 90  # Dùng JPEG Quality 90 cho độ nét tuyệt đối (Visually Lossless)
        self.frame_count = 0

    def encode_frame(self, frame: np.ndarray, client_id: str) -> bytes:
        self.frame_count += 1
        
        # Ép gửi Full Frame mỗi 120 frame (khoảng 2 giây ở 60FPS) để làm mới toàn bộ màn hình
        # Rất quan trọng khi chạy vài chục máy để tránh nghẽn băng thông
        if self.frame_count % 120 == 0:
            self.prev_frame = None

        # Xác định chính xác đây có phải Full Frame hay không
        is_full_frame = (self.prev_frame is None) or (self.prev_frame.shape != frame.shape)

        # 1. Delta extraction
        changes = ImageUtils.extract_delta_grid(self.prev_frame, frame, grid_size=128)
        
        # Sử dụng .copy() để tránh tham chiếu đè bộ nhớ nếu thư viện chụp ảnh tái sử dụng buffer
        self.prev_frame = frame.copy()

        # Adaptive Quality Logic based on Area
        # Nếu màn hình thay đổi quá lớn (như đang xem Video Full HD), giảm nhẹ Quality để giữ mượt 60 FPS mà không nghẽn mạng
        total_pixels_changed = sum(c['w'] * c['h'] for c in changes)
        screen_pixels = frame.shape[0] * frame.shape[1]
        
        active_quality = self.base_quality
        if total_pixels_changed > screen_pixels * 0.4:  # Đổi > 40% màn hình
            active_quality = max(60, self.base_quality - 25) # Giảm mạnh để cứu băng thông
        elif total_pixels_changed > screen_pixels * 0.1: # Đổi > 10% màn hình
            active_quality = max(70, self.base_quality - 15)

        # 2. Compress and format changes
        payload_changes = []
        for change in changes:
            # Compress to JPEG dynamically (nativly supported in browsers and much faster than WebP)
            jpeg_data = CompressionManager.encode_image_jpeg(change['data'], quality=active_quality)
            
            payload_changes.append({
                'x': change['x'],
                'y': change['y'],
                'w': change['w'],
                'h': change['h'],
                'data': "data:image/jpeg;base64," + base64.b64encode(jpeg_data).decode('ascii')
            })

        payload = {
            'client_id': client_id,
            'is_full_frame': is_full_frame,
            'changes': payload_changes
        }
        
        # 3. Serialize to JSON
        json_data = json.dumps(payload).encode('utf-8')
        
        # 4. Zlib compress the JSON
        compressed_json = CompressionManager.compress_zlib(json_data)
        
        # 5. Encrypt
        encrypted = self.crypto.encrypt(compressed_json)
        
        # 6. Pack Protocol
        return Protocol.pack(CommandTypes.SCREEN_FRAME, encrypted)
