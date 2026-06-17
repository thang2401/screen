import struct
import json
from typing import Dict, Any, Tuple, Optional
from core.constants import NetworkConfig

class Protocol:
    """
    Binary Protocol Header:
    [Magic Bytes (4B)][Version (1B)][Type (1B)][Payload Length (4B)]
    Total Header Size: 10 bytes
    """
    HEADER_FORMAT = "!4sBBI" # (4 string, 1 unsigned char, 1 unsigned char, 1 unsigned int = 10 bytes)
    HEADER_SIZE = struct.calcsize("!4sBBI")

    @classmethod
    def pack(cls, cmd_type: int, payload: bytes = b"") -> bytes:
        header = struct.pack(
            "!4sBBI",
            NetworkConfig.MAGIC_BYTES,
            NetworkConfig.VERSION,
            cmd_type,
            len(payload)
        )
        return header + payload

    @classmethod
    def unpack_header(cls, data: bytes) -> Tuple[Optional[int], Optional[int]]:
        """
        Returns (cmd_type, payload_length)
        """
        if len(data) < cls.HEADER_SIZE:
            return None, None
            
        magic, version, cmd_type, length = struct.unpack("!4sBBI", data[:cls.HEADER_SIZE])
        
        if magic != NetworkConfig.MAGIC_BYTES or version != NetworkConfig.VERSION:
            raise ValueError("Invalid magic bytes or version")
            
        return cmd_type, length
        
    @classmethod
    def pack_json(cls, cmd_type: int, data: Dict[str, Any]) -> bytes:
        payload = json.dumps(data).encode('utf-8')
        return cls.pack(cmd_type, payload)
        
    @classmethod
    def unpack_json(cls, payload: bytes) -> Dict[str, Any]:
        return json.loads(payload.decode('utf-8'))
