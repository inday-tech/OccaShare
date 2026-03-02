from .config import settings
from cryptography.fernet import Fernet
import os

# prioritize environment-based keys for persistence
ENCRYPTION_KEY = settings.KYC_ENCRYPTION_KEY
if not ENCRYPTION_KEY:
    # Fallback only for local development/first run
    ENCRYPTION_KEY = Fernet.generate_key().decode()

cipher_suite = Fernet(ENCRYPTION_KEY.encode())

def encrypt_data(data: bytes) -> bytes:
    """Encrypt binary data."""
    return cipher_suite.encrypt(data)

def decrypt_data(data: bytes) -> bytes:
    """Decrypt binary data."""
    return cipher_suite.decrypt(data)
