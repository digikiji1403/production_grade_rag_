
import pytest

from backend.app.services.auth_service import (
    register_user,
    authenticate_user,
)
from backend.app.db.models import User


def test_register_user(db_session):
    user = register_user(
        db_session,
        "TestUser@ragforge.local",
        "StrongPassword123!",
    )

    assert user is not None
    assert user.email == "testuser@ragforge.local"
    assert user.hashed_password != "StrongPassword123!"


def test_duplicate_registration(db_session):
    register_user(
        db_session,
        "duplicate@ragforge.local",
        "StrongPassword123!",
    )

    duplicate = register_user(
        db_session,
        "duplicate@ragforge.local",
        "AnotherPassword123!",
    )

    assert duplicate is None


def test_successful_authentication(db_session):
    register_user(
        db_session,
        "login@ragforge.local",
        "StrongPassword123!",
    )

    user = authenticate_user(
        db_session,
        "LOGIN@ragforge.local",
        "StrongPassword123!",
    )

    assert user is not None
    assert user.email == "login@ragforge.local"


def test_wrong_password_rejected(db_session):
    register_user(
        db_session,
        "wrongpass@ragforge.local",
        "StrongPassword123!",
    )

    user = authenticate_user(
        db_session,
        "wrongpass@ragforge.local",
        "IncorrectPassword123!",
    )

    assert user is None


def test_inactive_user_cannot_authenticate(db_session):
    register_user(
        db_session,
        "inactive@ragforge.local",
        "StrongPassword123!",
    )

    user = db_session.query(User).filter_by(
        email="inactive@ragforge.local"
    ).first()

    user.is_active = False
    db_session.commit()

    result = authenticate_user(
        db_session,
        "inactive@ragforge.local",
        "StrongPassword123!",
    )

    assert result is None
