import zlib
import cv2
import numpy as np

class CompressionManager:
    @staticmethod
    def compress_zlib(data: bytes, level: int = 6) -> bytes:
        return zlib.compress(data, level)

    @staticmethod
    def decompress_zlib(data: bytes) -> bytes:
        return zlib.decompress(data)

    @staticmethod
    def encode_image_webp(image: np.ndarray, quality: int = 80) -> bytes:
        encode_param = [int(cv2.IMWRITE_WEBP_QUALITY), quality]
        result, encimg = cv2.imencode('.webp', image, encode_param)
        if not result:
            raise ValueError("Failed to encode image to WebP")
        return encimg.tobytes()

    @staticmethod
    def encode_image_jpeg(image: np.ndarray, quality: int = 80) -> bytes:
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality, int(cv2.IMWRITE_JPEG_OPTIMIZE), 0] # Optimize=0 cho tốc độ encode nhanh nhất
        result, encimg = cv2.imencode('.jpg', image, encode_param)
        if not result:
            raise ValueError("Failed to encode image to JPEG")
        return encimg.tobytes()

    @staticmethod
    def decode_image(data: bytes) -> np.ndarray:
        nparr = np.frombuffer(data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Failed to decode image")
        return img
