"""Token model for the Spotify login."""

from datetime import datetime, timedelta, timezone

from pydantic import BaseModel

from sgs.constants import TOKEN_EXPIRY_MARGIN_SECONDS


class TokenInfo(BaseModel):
    """Access token, optional refresh token, and their expiry time."""

    access_token: str
    refresh_token: str | None = None
    expires_at: datetime
    scope: str = ""

    def is_expired(self) -> bool:
        """Returns True if the access token expires within the safety margin.

        Returns:
            expired (bool): True if the token should be refreshed before use.
        """
        margin = timedelta(seconds=TOKEN_EXPIRY_MARGIN_SECONDS)
        expired = datetime.now(timezone.utc) >= self.expires_at - margin

        return expired
