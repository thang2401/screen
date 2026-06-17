"""
Cấu hình Server - Đọc từ file YAML + Environment variables.
"""

import os
import json
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path

import yaml


@dataclass
class DatabaseConfig:
    """Cấu hình database."""
    type: str = "sqlite"           # sqlite, postgresql, mysql
    path: str = "data/database/monitoring.db"
    host: str = "localhost"
    port: int = 5432
    name: str = "monitoring"
    user: str = "admin"
    password: str = ""
    pool_size: int = 10
    max_overflow: int = 20
    echo: bool = False

    @property
    def url(self) -> str:
        if self.type == "sqlite":
            return f"sqlite+aiosqlite:///{self.path}"
        elif self.type == "postgresql":
            return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"
        elif self.type == "mysql":
            return f"mysql+aiomysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"
        return f"sqlite+aiosqlite:///{self.path}"


@dataclass
class NetworkConfig:
    """Cấu hình mạng."""
    host: str = "0.0.0.0"
    port: int = 8765
    max_clients: int = 500
    max_message_size: int = 50 * 1024 * 1024  # 50MB
    ping_interval: int = 10
    ping_timeout: int = 5
    heartbeat_timeout: int = 15
    send_buffer_size: int = 256 * 1024  # 256KB
    recv_buffer_size: int = 256 * 1024
    tcp_nodelay: bool = True
    ssl_enabled: bool = False
    ssl_cert: str = ""
    ssl_key: str = ""


@dataclass
class EncodingConfig:
    """Cấu hình nén ảnh."""
    quality: int = 90
    max_width: int = 1920
    fps: int = 60
    grayscale: bool = False
    use_delta: bool = True
    delta_block_size: int = 16
    enable_gpu: bool = False
    format: str = "jpeg"  # jpeg, webp, png


@dataclass
class AIConfig:
    """Cấu hình AI Detection."""
    enabled: bool = True
    model: str = "yolov8n.pt"
    confidence_threshold: float = 0.65
    frame_interval: int = 5
    batch_size: int = 4
    detect_games: bool = True
    detect_websites: bool = True
    detect_idle: bool = True
    detect_cheating: bool = False
    use_gpu: bool = False


@dataclass
class RecordingConfig:
    """Cấu hình ghi hình."""
    enabled: bool = True
    fps: int = 10
    bitrate: str = "2M"
    codec: str = "h264_nvenc"  # h264_nvenc or libx264
    output_dir: str = "data/recordings"
    max_duration_minutes: int = 60
    auto_clean_hours: int = 168  # 7 days


@dataclass
class SecurityConfig:
    """Cấu hình bảo mật."""
    encryption_enabled: bool = True
    master_password: str = ""
    key_rotation_hours: int = 24
    require_auth: bool = False
    auth_token: str = ""
    jwt_secret: str = ""
    jwt_expiry_hours: int = 24
    allowed_ips: List[str] = field(default_factory=list)
    rate_limit_per_second: int = 100


@dataclass
class LoggingConfig:
    """Cấu hình logging."""
    level: str = "INFO"
    file: str = "data/logs/server.log"
    max_size_mb: int = 100
    backup_count: int = 10
    json_format: bool = False


@dataclass
class ServerConfig:
    """Cấu hình tổng thể Server."""
    
    # General
    name: str = "Screen Monitoring System Pro"
    version: str = "3.0.0"
    data_dir: str = "data"
    
    # Sub-configs
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    encoding: EncodingConfig = field(default_factory=EncodingConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    recording: RecordingConfig = field(default_factory=RecordingConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    
    # GUI
    grid_columns: int = 4
    window_title: str = "🛡️ Screen Monitoring System Pro v3.0"
    window_width: int = 1600
    window_height: int = 900
    dark_theme: bool = True
    
    def __post_init__(self):
        """Tạo các thư mục cần thiết."""
        dirs = [
            self.data_dir,
            self.database.path,
            self.recording.output_dir,
            os.path.dirname(self.logging.file),
            "data/screenshots",
            "data/cache",
            "data/logs",
            "server/ai/models",
        ]
        for d in dirs:
            os.makedirs(os.path.dirname(d) if '.' in os.path.basename(d) else d,
                       exist_ok=True)
    
    @classmethod
    def from_file(cls, path: str) -> 'ServerConfig':
        """Đọc cấu hình từ file YAML."""
        if not os.path.exists(path):
            return cls()
        
        with open(path, 'r') as f:
            data = yaml.safe_load(f) or {}
        
        config = cls()
        
        # General
        if 'server' in data:
            srv = data['server']
            config.name = srv.get('name', config.name)
            config.version = srv.get('version', config.version)
            config.data_dir = srv.get('data_dir', config.data_dir)
        
        # Database
        if 'database' in data:
            db = data['database']
            config.database.type = db.get('type', config.database.type)
            config.database.path = db.get('path', config.database.path)
            config.database.host = db.get('host', config.database.host)
            config.database.port = db.get('port', config.database.port)
        
        # Network
        if 'network' in data:
            net = data['network']
            config.network.host = net.get('host', config.network.host)
            config.network.port = net.get('port', config.network.port)
            config.network.max_clients = net.get('max_clients', config.network.max_clients)
        
        # Encoding
        if 'encoding' in data:
            enc = data['encoding']
            config.encoding.quality = enc.get('quality', config.encoding.quality)
            config.encoding.fps = enc.get('fps', config.encoding.fps)
            config.encoding.use_delta = enc.get('use_delta', config.encoding.use_delta)
        
        # AI
        if 'ai' in data:
            ai_data = data['ai']
            config.ai.enabled = ai_data.get('enabled', config.ai.enabled)
            config.ai.model = ai_data.get('model', config.ai.model)
        
        # Security
        if 'security' in data:
            sec = data['security']
            config.security.encryption_enabled = sec.get('encryption_enabled', config.security.encryption_enabled)
            config.security.master_password = sec.get('master_password', config.security.master_password)
        
        return config
    
    def save(self, path: str):
        """Lưu cấu hình ra file YAML."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            yaml.dump(asdict(self), f, default_flow_style=False)
    
    def to_dict(self) -> dict:
        """Chuyển thành dict."""
        return asdict(self)