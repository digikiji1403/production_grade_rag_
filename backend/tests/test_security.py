
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest

from backend.app.core.config import get_settings
from backend.app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_valid_access_token():
    user_id = uuid4()

    token = create_access_token(user_id)
    payload = decode_access_token(token)

    assert payload["sub"] == str(user_id)
    assert "exp" in payload
    assert "iat" in payload


def test_tampered_access_token_is_rejected():
    token = create_access_token(uuid4())

    parts = token.split(".")
    signature = parts[2]

    # Change one character in the signature.
    replacement = "A" if signature[0] != "A" else "B"
    parts[2] = replacement + signature[1:]

    tampered_token = ".".join(parts)

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(tampered_token)


def test_expired_access_token_is_rejected():
    settings = get_settings()

    expired_payload = {
        "sub": str(uuid4()),
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }

    expired_token = jwt.encode(
        expired_payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired_token)


def test_password_hashing_and_verification():
    password = "TestPassword123!"
    hashed_password = hash_password(password)

    assert hashed_password != password
    assert verify_password(password, hashed_password)
    assert not verify_password("WrongPassword", hashed_password)
