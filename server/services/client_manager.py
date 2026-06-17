"""
Client Manager - Quản lý vòng đời client.
Xử lý: kết nối, ngắt kết nối, theo dõi trạng thái, grouping.
"""

import time
import logging
import uuid
from typing import Dict, Optional, List, Set, Callable
from dataclasses import dataclass, field
from collections import defaultdict

from server.database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)


@dataclass
class ClientGroup:
    """Nhóm client."""
    name: str
    description: str = ""
    client_ids: Set[str] = field(default_factory=set)
    created_at: float = field(default_factory=time.time)
    is_dynamic: bool = False  # Dynamic group (auto-assigned)


class ClientManager:
    """
    Quản lý tất cả clients với:
    - CRUD operations
    - Group management
    - Status tracking
    - Auto-discovery
    - Rate limiting per client
    """

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.clients: Dict[str, dict] = {}
        self.groups: Dict[str, ClientGroup] = {}
        self._callbacks: Dict[str, List[Callable]] = defaultdict(list)

        # Default groups
        self._init_default_groups()

    def _init_default_groups(self):
        """Khởi tạo groups mặc định."""
        self.add_group("all", "Tất cả clients", is_dynamic=True)
        self.add_group("online", "Clients đang online", is_dynamic=True)
        self.add_group("offline", "Clients đang offline", is_dynamic=True)

    def register_client(self, client_id: str, info: dict) -> dict:
        """Đăng ký client mới."""
        client_data = {
            'client_id': client_id,
            'hostname': info.get('hostname', ''),
            'ip_address': info.get('ip', ''),
            'mac_address': info.get('mac', ''),
            'os_info': info.get('os', ''),
            'screen_width': info.get('screen_width', 0),
            'screen_height': info.get('screen_height', 0),
            'version': info.get('version', ''),
            'is_active': True,
        }

        self.clients[client_id] = client_data

        # Thêm vào các group động
        self.groups['all'].client_ids.add(client_id)
        self.groups['online'].client_ids.add(client_id)
        self.groups['offline'].client_ids.discard(client_id)

        # Trigger callbacks
        self._trigger('client_connected', client_id, client_data)

        logger.info(f"Client registered: {client_id} ({info.get('hostname', 'N/A')})")
        return client_data

    def unregister_client(self, client_id: str):
        """Hủy đăng ký client."""
        if client_id in self.clients:
            client_data = self.clients.pop(client_id)

            # Xóa khỏi groups
            for group in self.groups.values():
                group.client_ids.discard(client_id)

            self._trigger('client_disconnected', client_id, client_data)
            logger.info(f"Client unregistered: {client_id}")

    def update_client(self, client_id: str, updates: dict):
        """Cập nhật thông tin client."""
        if client_id in self.clients:
            self.clients[client_id].update(updates)
            self._trigger('client_updated', client_id, updates)

    def get_client(self, client_id: str) -> Optional[dict]:
        return self.clients.get(client_id)

    def get_all_clients(self) -> List[dict]:
        return list(self.clients.values())

    def get_online_clients(self) -> List[dict]:
        return [c for c in self.clients.values() if c.get('is_active')]

    def get_offline_clients(self) -> List[dict]:
        return [c for c in self.clients.values() if not c.get('is_active')]

    # ===== Group Management =====

    def add_group(self, name: str, description: str = "",
                  is_dynamic: bool = False) -> ClientGroup:
        """Thêm group mới."""
        if name not in self.groups:
            self.groups[name] = ClientGroup(
                name=name, description=description, is_dynamic=is_dynamic
            )
        return self.groups[name]

    def remove_group(self, name: str):
        """Xóa group."""
        if name in self.groups and not self.groups[name].is_dynamic:
            del self.groups[name]

    def add_client_to_group(self, client_id: str, group_name: str) -> bool:
        """Thêm client vào group."""
        if group_name in self.groups and client_id in self.clients:
            self.groups[group_name].client_ids.add(client_id)
            return True
        return False

    def remove_client_from_group(self, client_id: str, group_name: str) -> bool:
        """Xóa client khỏi group."""
        if group_name in self.groups:
            self.groups[group_name].client_ids.discard(client_id)
            return True
        return False

    def get_group_clients(self, group_name: str) -> List[dict]:
        """Lấy danh sách client trong group."""
        if group_name not in self.groups:
            return []
        return [
            self.clients[cid] for cid in self.groups[group_name].client_ids
            if cid in self.clients
        ]

    def get_all_groups(self) -> List[dict]:
        return [
            {
                'name': g.name,
                'description': g.description,
                'size': len(g.client_ids),
                'is_dynamic': g.is_dynamic,
            }
            for g in self.groups.values()
        ]

    # ===== Search & Filter =====

    def search_clients(self, query: str) -> List[dict]:
        """Tìm kiếm client."""
        query = query.lower()
        results = []
        for client in self.clients.values():
            if (query in client.get('client_id', '').lower() or
                query in client.get('hostname', '').lower() or
                query in client.get('ip_address', '')):
                results.append(client)
        return results

    def filter_clients(self, **filters) -> List[dict]:
        """Lọc client theo điều kiện."""
        results = list(self.clients.values())
        for key, value in filters.items():
            results = [c for c in results if c.get(key) == value]
        return results

    # ===== Event System =====

    def on(self, event: str, callback: Callable):
        """Đăng ký event listener."""
        self._callbacks[event].append(callback)

    def _trigger(self, event: str, *args, **kwargs):
        """Kích hoạt event."""
        for callback in self._callbacks.get(event, []):
            try:
                callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Callback error for event {event}: {e}")

    # ===== Stats =====

    def get_stats(self) -> dict:
        """Lấy thống kê clients."""
        total = len(self.clients)
        online = len(self.get_online_clients())
        offline = total - online
        groups = len(self.groups)

        return {
            'total_clients': total,
            'online_clients': online,
            'offline_clients': offline,
            'groups': groups,
            'timestamp': time.time(),
        }