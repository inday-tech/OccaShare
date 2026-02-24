from cryptography.fernet import Fernet
import os

# In a real app, this should be in environment variables
ENCRYPTION_KEY = os.getenv("KYC_ENCRYPTION_KEY", Fernet.generate_key().decode())

cipher_suite = Fernet(ENCRYPTION_KEY.encode())

def encrypt_data(data: bytes) -> bytes:
    """Encrypt binary data."""
    return cipher_suite.encrypt(data)

def decrypt_data(data: bytes) -> bytes:
    """Decrypt binary data."""
    return cipher_suite.decrypt(data)
