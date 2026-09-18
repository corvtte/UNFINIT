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

def derive_aes_gcm_key(passphrase: str, salt: bytes = _PBKDF2_SALT) -> bytes:
    """
    Derives a raw 32-byte (256-bit) key for AES-256-GCM using PBKDF2-HMAC-SHA256.
    """
    if not passphrase:
        passphrase = "UNFINIT_DEFAULT_DATA_PASSPHRASE_SECURE"
    return hashlib.pbkdf2_hmac(
        hash_name="sha256",
        password=passphrase.encode("utf-8"),
        salt=salt,
        iterations=100000,
        dklen=32
    )

def get_aes_gcm_key() -> bytes:
    """
    Returns the active 32-byte key for AES-256-GCM.
    Derives from DATA_ENCRYPTION_KEY, ADMIN_PANEL_PASSWORD, or fallback secret.
    """
    raw_key = os.getenv("DATA_ENCRYPTION_KEY", "").strip()
    if raw_key:
        try:
            decoded = base64.urlsafe_b64decode(raw_key.encode("ascii"))
            if len(decoded) == 32:
                return decoded
        except Exception:
            pass
        return derive_aes_gcm_key(raw_key)

    from core.config import config
    admin_pw = os.getenv("ADMIN_PANEL_PASSWORD", "").strip() or os.getenv("ADMIN_PASSWORD", "").strip() or getattr(config, "ADMIN_PANEL_PASSWORD", "").strip()
    if admin_pw:
        return derive_aes_gcm_key(admin_pw)

    return derive_aes_gcm_key("UNFINIT_DEFAULT_STORE_FALLBACK_KEY_v030")

def get_aes_gcm_cipher(key: Optional[bytes] = None):
    """
    Returns an AESGCM cipher instance or None if cryptography is not available.
    """
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        active_key = key if key is not None else get_aes_gcm_key()
        return AESGCM(active_key)
    except Exception as e:
        logger.warning(f"[security] AESGCM unavailable: {e}")
        return None

def encrypt_session_data(raw_bytes: Union[str, bytes], key: Optional[bytes] = None) -> bytes:
    """
    Encrypts session payload with AES-256-GCM.
    Output: 12-byte IV (nonce) + ciphertext (with 16-byte GCM authentication tag).
    """
    if isinstance(raw_bytes, str):
        data_bytes = raw_bytes.encode("utf-8")
    else:
        data_bytes = bytes(raw_bytes)

    active_key = key if key is not None else get_aes_gcm_key()
    aesgcm = get_aes_gcm_cipher(active_key)
    if aesgcm is not None:
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, data_bytes, None)
        return nonce + ciphertext

    # Fallback to Fernet encrypt_data
    return encrypt_data(data_bytes, key=derive_fernet_key(active_key.hex()))

def decrypt_session_data(enc_bytes: bytes, key: Optional[bytes] = None) -> bytes:
    """
    Decrypts AES-256-GCM encrypted session bytes in memory.
    """
    if not enc_bytes:
        return b""
    active_key = key if key is not None else get_aes_gcm_key()
    aesgcm = get_aes_gcm_cipher(active_key)
    if aesgcm is not None and len(enc_bytes) >= 28: # 12 nonce + 16 tag minimum
        try:
            nonce = enc_bytes[:12]
            ciphertext = enc_bytes[12:]
            return aesgcm.decrypt(nonce, ciphertext, None)
        except Exception as e:
            logger.warning(f"[security] AES-256-GCM decrypt error, trying fallback: {e}")

    # Fallback to Fernet decrypt_data
    try:
        dec = decrypt_data(enc_bytes, key=derive_fernet_key(active_key.hex()))
        return dec.encode("utf-8") if isinstance(dec, str) else dec
    except Exception as e:
        raise ValueError(f"Session decryption failed: {e}")

def save_encrypted_session(session_path: Union[str, Path], raw_bytes: bytes, key: Optional[bytes] = None) -> Path:
    """
    Persists encrypted session file to disk with .session.enc extension.
    Securely removes any plain session file at the same location.
    """
    p = Path(session_path)
    if not p.name.endswith(".enc"):
        if p.suffix == ".session":
            enc_path = p.with_name(p.name + ".enc")
        else:
            enc_path = p.with_suffix(".session.enc")
    else:
        enc_path = p

    enc_path.parent.mkdir(parents=True, exist_ok=True)
    enc_data = encrypt_session_data(raw_bytes, key=key)
    enc_path.write_bytes(enc_data)

    # Securely wipe plain file if exists
    raw_candidates = [
        enc_path.with_suffix(""),
        p if p != enc_path else None
    ]
    for raw_file in raw_candidates:
        if raw_file and raw_file.exists() and raw_file != enc_path:
            try:
                raw_file.write_bytes(os.urandom(min(raw_file.stat().st_size, 1024)))
                raw_file.unlink(missing_ok=True)
            except Exception:
                pass
    return enc_path

def load_decrypted_session(session_path: Union[str, Path], key: Optional[bytes] = None) -> bytes:
    """
    Loads and decrypts session data from .session.enc (or legacy plain session file).
    """
    p = Path(session_path)
    enc_candidates = [
        p if p.name.endswith(".enc") else None,
        p.with_name(p.name + ".enc") if p.suffix == ".session" else p.with_suffix(".session.enc"),
        p.with_suffix(".enc")
    ]
    for cand in enc_candidates:
        if cand and cand.exists():
            enc_data = cand.read_bytes()
            return decrypt_session_data(enc_data, key=key)

    if p.exists():
        raw_data = p.read_bytes()
        save_encrypted_session(p, raw_data, key=key)
        return raw_data

    raise FileNotFoundError(f"Session file not found: {session_path}")


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
