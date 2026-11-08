import hashlib, hmac, secrets, string
from datetime import datetime, timedelta, timezone

PBKDF2_ROUNDS = 310_000
_ACTIVATION_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, PBKDF2_ROUNDS)
    return f'pbkdf2_sha256${PBKDF2_ROUNDS}${salt.hex()}${dk.hex()}'


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, rounds, salt_hex, digest_hex = encoded.split('$', 3)
        if scheme != 'pbkdf2_sha256':
            return False
        candidate = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt_hex), int(rounds))
        return hmac.compare_digest(candidate.hex(), digest_hex)
    except Exception:
        return False


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def new_activation_code(length: int = 8) -> str:
    return ''.join(secrets.choice(_ACTIVATION_ALPHABET) for _ in range(length))


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utcnow().isoformat()


def iso_expiry(hours: int = 24 * 7) -> str:
    return (utcnow() + timedelta(hours=hours)).isoformat()


def activation_expiry(days: int = 30) -> str:
    return (utcnow() + timedelta(days=days)).isoformat()
