import os
from Crypto.Cipher import AES

class CryptoManager:
    """
    Manages AES-256-GCM encryption/decryption for payload protection.
    """
    def __init__(self, key: bytes = None):
        if key is None:
            self.key = os.urandom(32) # AES-256
        else:
            if len(key) not in (16, 24, 32):
                raise ValueError("Key must be 16, 24, or 32 bytes long")
            self.key = key

    def encrypt(self, data: bytes) -> bytes:
        if not data:
            return b""
        cipher = AES.new(self.key, AES.MODE_GCM)
        ciphertext, tag = cipher.encrypt_and_digest(data)
        # Structure: [nonce (16 bytes)] + [tag (16 bytes)] + [ciphertext]
        return cipher.nonce + tag + ciphertext

    def decrypt(self, encrypted_data: bytes) -> bytes:
        if not encrypted_data:
            return b""
        if len(encrypted_data) < 32: # nonce (16) + tag (16)
            raise ValueError("Encrypted data is too short")
            
        nonce = encrypted_data[:16]
        tag = encrypted_data[16:32]
        ciphertext = encrypted_data[32:]
        
        cipher = AES.new(self.key, AES.MODE_GCM, nonce=nonce)
        try:
            decrypted_data = cipher.decrypt_and_verify(ciphertext, tag)
            return decrypted_data
        except ValueError:
            raise ValueError("Decryption failed. Invalid key or corrupted data.")
