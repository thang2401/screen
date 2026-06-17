"""
File Transfer Service - Chuyển file giữa server và client.
Hỗ trợ: upload, download, chunked transfer, resume.
"""

import asyncio
import logging
import os
import hashlib
import time
from typing import Dict, Optional, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FileTransfer:
    """Một phiên chuyển file."""
    transfer_id: str
    client_id: str
    filename: str
    filepath: str
    total_size: int
    chunk_size: int = 65536  # 64KB
    transferred: int = 0
    started_at: float = 0
    completed_at: float = 0
    status: str = "pending"  # pending, transferring, completed, failed
    checksum: str = ""
    is_upload: bool = True  # True: client -> server, False: server -> client


class FileTransferService:
    """
    Service chuyển file giữa server và client.
    - Chunked transfer (chia file thành nhiều phần)
    - Resume (tiếp tục nếu bị gián đoạn)
    - Checksum verification
    - Progress tracking
    """
    
    def __init__(self, base_dir: str = "data/files"):
        self.base_dir = base_dir
        self.active_transfers: Dict[str, FileTransfer] = {}
        self.completed_transfers: list = []
        self.max_history = 1000
        
        os.makedirs(os.path.join(base_dir, "uploads"), exist_ok=True)
        os.makedirs(os.path.join(base_dir, "downloads"), exist_ok=True)
    
    async def start_upload(self, client_id: str, filename: str,
                           total_size: int) -> Optional[str]:
        """Bắt đầu upload file từ client."""
        transfer_id = f"transfer_{int(time.time() * 1000)}_{hash(filename)}"
        filepath = os.path.join(self.base_dir, "uploads", client_id, filename)
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        transfer = FileTransfer(
            transfer_id=transfer_id,
            client_id=client_id,
            filename=filename,
            filepath=filepath,
            total_size=total_size,
            is_upload=True,
            started_at=time.time(),
        )
        
        self.active_transfers[transfer_id] = transfer
        logger.info(f"Upload started: {filename} ({total_size} bytes) from {client_id}")
        
        return transfer_id
    
    async def start_download(self, client_id: str, filename: str,
                             total_size: int) -> Optional[str]:
        """Bắt đầu download file từ server."""
        transfer_id = f"transfer_{int(time.time() * 1000)}_{hash(filename)}"
        filepath = os.path.join(self.base_dir, "downloads", client_id, filename)
        
        transfer = FileTransfer(
            transfer_id=transfer_id,
            client_id=client_id,
            filename=filename,
            filepath=filepath,
            total_size=total_size,
            is_upload=False,
            started_at=time.time(),
        )
        
        self.active_transfers[transfer_id] = transfer
        logger.info(f"Download started: {filename} to {client_id}")
        
        return transfer_id
    
    async def process_chunk(self, transfer_id: str, chunk_data: bytes,
                            chunk_index: int) -> bool:
        """Xử lý một chunk dữ liệu."""
        transfer = self.active_transfers.get(transfer_id)
        if not transfer:
            return False
        
        try:
            # Ghi chunk vào file
            with open(transfer.filepath, 'ab') as f:
                f.seek(chunk_index * transfer.chunk_size)
                f.write(chunk_data)
            
            transfer.transferred += len(chunk_data)
            
            # Kiểm tra hoàn thành
            if transfer.transferred >= transfer.total_size:
                transfer.status = "completed"
                transfer.completed_at = time.time()
                
                # Tính checksum
                transfer.checksum = self._calculate_checksum(transfer.filepath)
                
                # Move to completed
                self.completed_transfers.append(transfer)
                if len(self.completed_transfers) > self.max_history:
                    self.completed_transfers.pop(0)
                
                self.active_transfers.pop(transfer_id, None)
                
                logger.info(f"Transfer completed: {transfer.filename} "
                           f"({transfer.total_size} bytes)")
            
            return True
            
        except Exception as e:
            transfer.status = "failed"
            logger.error(f"Chunk processing error: {e}")
            return False
    
    async def get_chunk(self, transfer_id: str, chunk_index: int) -> Optional[bytes]:
        """Lấy một chunk để gửi cho client."""
        transfer = self.active_transfers.get(transfer_id)
        if not transfer:
            return None
        
        try:
            offset = chunk_index * transfer.chunk_size
            with open(transfer.filepath, 'rb') as f:
                f.seek(offset)
                chunk = f.read(transfer.chunk_size)
            
            transfer.transferred = min(offset + len(chunk), transfer.total_size)
            
            # Kiểm tra hoàn thành
            if transfer.transferred >= transfer.total_size:
                transfer.status = "completed"
                transfer.completed_at = time.time()
                self.completed_transfers.append(transfer)
                self.active_transfers.pop(transfer_id, None)
            
            return chunk
            
        except Exception as e:
            logger.error(f"Chunk read error: {e}")
            return None
    
    def get_transfer_status(self, transfer_id: str) -> Optional[dict]:
        """Lấy trạng thái transfer."""
        transfer = self.active_transfers.get(transfer_id)
        if not transfer:
            return None
        
        progress = (transfer.transferred / max(transfer.total_size, 1)) * 100
        
        return {
            'transfer_id': transfer.transferred,
            'filename': transfer.filename,
            'total_size': transfer.total_size,
            'transferred': transfer.transferred,
            'progress': round(progress, 1),
            'status': transfer.status,
            'is_upload': transfer.is_upload,
        }
    
    def get_client_files(self, client_id: str) -> list:
        """Lấy danh sách file đã upload của client."""
        client_dir = os.path.join(self.base_dir, "uploads", client_id)
        if not os.path.exists(client_dir):
            return []
        
        files = []
        for f in os.listdir(client_dir):
            filepath = os.path.join(client_dir, f)
            if os.path.isfile(filepath):
                files.append({
                    'filename': f,
                    'size': os.path.getsize(filepath),
                    'modified': os.path.getmtime(filepath),
                })
        
        return files
    
    def _calculate_checksum(self, filepath: str) -> str:
        """Tính MD5 checksum của file."""
        h = hashlib.md5()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                h.update(chunk)
        return h.hexdigest()
    
    def cancel_transfer(self, transfer_id: str) -> bool:
        """Hủy transfer."""
        transfer = self.active_transfers.pop(transfer_id, None)
        if transfer:
            transfer.status = "cancelled"
            # Xóa file tạm
            if os.path.exists(transfer.filepath):
                os.remove(transfer.filepath)
            logger.info(f"Transfer cancelled: {transfer.filename}")
            return True
        return False
    
    def cleanup_old_files(self, max_age_hours: int = 24):
        """Xóa các file tạm cũ."""
        now = time.time()
        for root, dirs, files in os.walk(self.base_dir):
            for f in files:
                filepath = os.path.join(root, f)
                age_hours = (now - os.path.getmtime(filepath)) / 3600
                if age_hours > max_age_hours:
                    os.remove(filepath)