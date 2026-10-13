import hashlib, secrets
from datetime import timedelta
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from app.models import now
from app.config import settings

hasher = PasswordHasher()
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))


def hash_password(password):
    return hasher.hash(password)


def verify_password(password, hashed):
    try:
        return hasher.verify(hashed, password)
    except (VerificationError, InvalidHashError):
        return False


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def access_token(user, session_id):
    return jwt.encode(
        {
            "sub": user.id,
            "org": user.org_id,
            "sid": session_id,
            "typ": "access",
            "iat": now(),
            "exp": now() + timedelta(minutes=settings().access_minutes),
            "iss": "gymos",
            "aud": "gymos-web",
        },
        settings().secret_key,
        algorithm="HS256",
    )


def decode_token(token):
    return jwt.decode(
        token,
        settings().secret_key,
        algorithms=["HS256"],
        issuer="gymos",
        audience="gymos-web",
        options={"require": ["sub", "org", "sid", "exp", "iat", "typ"]},
    )
