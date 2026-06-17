"""
Command Dispatcher - Điều phối lệnh đến client(s).
Hỗ trợ: single, group, broadcast, scheduled commands.
"""

import asyncio
import json
import time
import logging
from typing import Optional, Dict, List, Any, Callable
from enum import Enum
from dataclasses import dataclass, field

from core.protocol import Packet, create_command_packet, MSG_TYPE_COMMAND

logger = logging.getLogger(__name__)


class CommandStatus(Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    EXECUTED = "executed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class CommandResult:
    """Kết quả thực thi lệnh."""
    command_id: str
    client_id: str
    status: CommandStatus
    response: Optional[dict] = None
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    duration: float = 0.0


class CommandDispatcher:
    """
    Điều phối lệnh đến client với:
    - Gửi đến single/multiple/all client
    - Timeout handling
    - Retry mechanism
    - Command queue
    - Result tracking
    """

    def __init__(self, socket_server):
        self.socket_server = socket_server
        self.pending_commands: Dict[str, CommandResult] = {}
        self.command_history: List[CommandResult] = []
        self.max_history = 1000
        self.default_timeout = 10  # seconds

    async def dispatch(self, command: str, params: Optional[dict] = None,
                       target_clients: Optional[List[str]] = None,
                       timeout: Optional[int] = None,
                       wait_response: bool = False) -> Dict[str, CommandResult]:
        """
        Gửi lệnh đến client(s).

        Args:
            command: Tên lệnh
            params: Tham số lệnh
            target_clients: Danh sách client IDs (None = tất cả)
            timeout: Timeout chờ response
            wait_response: Chờ response từ client

        Returns:
            Dict[client_id, CommandResult]
        """
        timeout = timeout or self.default_timeout
        results = {}

        # Xác định target clients
        if target_clients is None:
            target_clients = self.socket_server.get_active_clients()

        if not target_clients:
            logger.warning(f"No clients to dispatch command: {command}")
            return results

        # Tạo packet
        packet = create_command_packet(command, params)
        command_id = f"cmd_{int(time.time() * 1000)}_{hash(command)}"

        for client_id in target_clients:
            result = CommandResult(
                command_id=command_id,
                client_id=client_id,
                status=CommandStatus.PENDING,
            )

            try:
                # Gửi lệnh
                success = await self.socket_server.send_to_client(client_id, packet)

                if success:
                    result.status = CommandStatus.SENT

                    if wait_response:
                        # Chờ response với timeout
                        try:
                            await asyncio.wait_for(
                                self._wait_response(client_id, command_id),
                                timeout=timeout
                            )
                            result.status = CommandStatus.EXECUTED
                        except asyncio.TimeoutError:
                            result.status = CommandStatus.TIMEOUT
                            result.error = "Timeout waiting for response"
                else:
                    result.status = CommandStatus.FAILED
                    result.error = "Failed to send command"

            except Exception as e:
                result.status = CommandStatus.FAILED
                result.error = str(e)

            result.duration = time.time() - result.timestamp
            results[client_id] = result
            self.pending_commands[command_id] = result

        # Lưu vào history
        self.command_history.extend(results.values())
        if len(self.command_history) > self.max_history:
            self.command_history = self.command_history[-self.max_history:]

        return results

    async def _wait_response(self, client_id: str, command_id: str,
                             check_interval: float = 0.1):
        """Chờ response từ client."""
        while True:
            result = self.pending_commands.get(command_id)
            if result and result.status in [CommandStatus.EXECUTED,
                                            CommandStatus.FAILED]:
                return result
            await asyncio.sleep(check_interval)

    async def handle_response(self, client_id: str, response: dict):
        """Xử lý response từ client."""
        command_id = response.get('command_id', '')
        if command_id in self.pending_commands:
            result = self.pending_commands[command_id]
            result.status = CommandStatus.EXECUTED
            result.response = response
            result.duration = time.time() - result.timestamp

    async def broadcast(self, command: str, params: Optional[dict] = None):
        """Gửi lệnh đến tất cả client (fire-and-forget)."""
        packet = create_command_packet(command, params)
        await self.socket_server.broadcast(packet)

    async def lock_all(self):
        """Khóa tất cả máy."""
        await self.broadcast("lock")

    async def unlock_all(self):
        """Mở khóa tất cả máy."""
        await self.broadcast("unlock")

    async def shutdown_all(self):
        """Tắt tất cả máy."""
        await self.broadcast("shutdown")

    async def restart_all(self):
        """Khởi động lại tất cả máy."""
        await self.broadcast("restart")

    async def send_message(self, message: str,
                           target_clients: Optional[List[str]] = None):
        """Gửi thông báo đến client(s)."""
        await self.dispatch("message", {"text": message}, target_clients)

    def get_command_history(self, limit: int = 50) -> List[dict]:
        """Lấy lịch sử lệnh."""
        return [
            {
                'command_id': r.command_id,
                'client_id': r.client_id,
                'status': r.status.value,
                'duration': r.duration,
                'timestamp': r.timestamp,
                'error': r.error,
            }
            for r in self.command_history[-limit:]
        ]

    def get_pending_count(self) -> int:
        """Đếm số lệnh đang chờ."""
        return len([
            r for r in self.pending_commands.values()
            if r.status == CommandStatus.PENDING
        ])