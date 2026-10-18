"""Module for testing authentication/token_model.py"""

from datetime import datetime, timedelta, timezone

from sgs.authentication.token_model import TokenInfo


# Testing the "is_expired" method from the "TokenInfo" class.


def test_token_not_expired_when_far_from_expiry():
    """A token that expires well after the safety margin is still valid."""

    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    token = TokenInfo(
        access_token="abc",
        expires_at=expires_at,
    )

    expired = token.is_expired()

    assert expired is False


def test_token_expired_within_safety_margin():
    """A token that expires within the safety margin counts as expired."""

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=10)
    token = TokenInfo(
        access_token="abc",
        expires_at=expires_at,
    )

    expired = token.is_expired()

    assert expired is True


def test_token_expired_in_the_past():
    """A token whose expiry time has passed counts as expired."""

    expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    token = TokenInfo(
        access_token="abc",
        expires_at=expires_at,
    )

    expired = token.is_expired()

    assert expired is True
