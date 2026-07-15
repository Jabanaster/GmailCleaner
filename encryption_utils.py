"""Encryption and decryption utilities for sensitive token storage."""
from cryptography.fernet import Fernet

def encrypt_token(plain_token: str, key: str) -> str:
    """Encrypt a plaintext token using the provided base64 Fernet key.
    
    Returns the URL-safe base64-encoded ciphertext string.
    """
    if not plain_token:
        return ""
    f = Fernet(key.encode())
    return f.encrypt(plain_token.encode()).decode()

def decrypt_token(cipher_token: str, key: str) -> str:
    """Decrypt a ciphertext token using the provided base64 Fernet key.
    
    Returns the decrypted plaintext string. Raises cryptography.fernet.InvalidToken if decryption fails.
    """
    if not cipher_token:
        return ""
    f = Fernet(key.encode())
    return f.decrypt(cipher_token.encode()).decode()
