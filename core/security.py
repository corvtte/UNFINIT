import os
import base64
import hashlib
from pathlib import Path
from typing import Union, Optional
from core.logger import get_logger

logger = get_logger("security")

# Constant salt for PBKDF2 key derivation
_PBKDF2_SALT = b"UNFINIT_V030_DATA_SALT_SECRET_SALT"
UNFINIT_DATA_SALT = _PBKDF2_SALT

def derive_fernet_key(passphrase: str, salt: bytes = _PBKDF2_SALT) -> bytes:
    """
    Derives a url-safe base64-encoded 32-byte Fernet key from an arbitrary string using PBKDF2-HMAC-SHA256.
    """
    if not passphrase:
        passphrase = "UNFINIT_DEFAULT_DATA_PASSPHRASE_SECURE"
    key_32 = hashlib.pbkdf2_hmac(
        hash_name="sha256",
        password=passphrase.encode("utf-8"),
        salt=salt,
        iterations=100000,
        dklen=32
    )
    return base64.urlsafe_b64encode(key_32)

def get_encryption_key() -> bytes:
    """
    Returns the active Fernet encryption key.
    Order of precedence:
    1. DATA_ENCRYPTION_KEY environment variable.
    2. Derived key from ADMIN_PANEL_PASSWORD / ADMIN_PASSWORD environment variable or config.
    3. Derived key from fallback secret.
    """
    raw_key = os.getenv("DATA_ENCRYPTION_KEY", "").strip()
    if raw_key:
        try:
            # Check if it is already a valid 32-byte urlsafe base64 key
            decoded = base64.urlsafe_b64decode(raw_key.encode("ascii"))
            if len(decoded) == 32:
                return raw_key.encode("ascii")
        except Exception:
            pass
        return derive_fernet_key(raw_key)

    # Fallback to admin password
    from core.config import config
    admin_pw = os.getenv("ADMIN_PANEL_PASSWORD", "").strip() or os.getenv("ADMIN_PASSWORD", "").strip() or getattr(config, "ADMIN_PANEL_PASSWORD", "").strip()
    if admin_pw:
        return derive_fernet_key(admin_pw)

    return derive_fernet_key("UNFINIT_DEFAULT_STORE_FALLBACK_KEY_v030")

def get_fernet_cipher(key: Optional[bytes] = None):
    """
    Returns a Fernet cipher instance or None if cryptography library is not installed.
    """
    try:
        from cryptography.fernet import Fernet
        active_key = key if key is not None else get_encryption_key()
        return Fernet(active_key)
    except ImportError:
        logger.warning("[security] cryptography module not found, using fallback encryption")
        return None

def encrypt_data(data: Union[str, bytes], key: Optional[bytes] = None) -> bytes:
    """
    Encrypts string or bytes with Fernet (AES-128-CBC + HMAC-SHA256, standard Fernet).
    """
    if isinstance(data, str):
        data_bytes = data.encode("utf-8")
    else:
        data_bytes = bytes(data)

    active_key = key if key is not None else get_encryption_key()
    cipher = get_fernet_cipher(key=active_key)
    if cipher is not None:
        return cipher.encrypt(data_bytes)
    
    # Simple fallback using AES-CBC with pyaes if cryptography unavailable
    try:
        import pyaes
        raw_key = base64.urlsafe_b64decode(active_key)
        iv = os.urandom(16)
        encrypter = pyaes.Encrypter(pyaes.AESModeOfOperationCBC(raw_key, iv=iv))
        cipher_bytes = encrypter.feed(data_bytes) + encrypter.feed()
        return iv + cipher_bytes
    except Exception as e:
        logger.error(f"[security] Encryption failed: {e}")
        return data_bytes

def decrypt_data(token: bytes, key: Optional[bytes] = None) -> Union[str, bytes]:
    """
    Decrypts token bytes into a UTF-8 string (or raw bytes if binary).
    """
    if not token:
        return ""

    active_key = key if key is not None else get_encryption_key()
    cipher = get_fernet_cipher(key=active_key)
    if cipher is not None:
        try:
            decrypted = cipher.decrypt(token)
            try:
                return decrypted.decode("utf-8")
            except UnicodeDecodeError:
                return decrypted
        except Exception as e:
            logger.error(f"[security] Fernet decryption error: {e}")
            raise ValueError(f"Decryption failed: {e}")

    try:
        import pyaes
        raw_key = base64.urlsafe_b64decode(active_key)
        iv = token[:16]
        cipher_bytes = token[16:]
        decrypter = pyaes.Decrypter(pyaes.AESModeOfOperationCBC(raw_key, iv=iv))
        plain_bytes = decrypter.feed(cipher_bytes) + decrypter.feed()
        try:
            return plain_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return plain_bytes
    except Exception as e:
        logger.error(f"[security] Decryption fallback error: {e}")
        raise ValueError(f"Decryption failed: {e}")
