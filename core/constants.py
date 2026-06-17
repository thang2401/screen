class CommandTypes:
    # Client -> Server
    AUTH = 0x01
    HEARTBEAT = 0x02
    SCREEN_FRAME = 0x03
    CLIENT_INFO = 0x04
    
    # Server -> Client
    LOCK = 0x10
    UNLOCK = 0x11
    SHUTDOWN = 0x12
    RESTART = 0x13
    SEND_FILE = 0x14
    CHAT_MESSAGE = 0x15
    UPDATE_CONFIG = 0x16
    AI_ALERT = 0x17

class NetworkConfig:
    DEFAULT_PORT = 8765
    HEARTBEAT_INTERVAL = 5 # seconds
    TIMEOUT = 15 # seconds
    MAGIC_BYTES = b'SMSP' # Screen Monitoring System Pro
    VERSION = 1
