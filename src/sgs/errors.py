"""Custom exceptions raised by the Spotify genre sorter."""


class SpotifyAuthError(Exception):
    """Raised when a Spotify login or token request fails."""


class LastfmInvalidKeyError(Exception):
    """Raised when Last.fm rejects the API key. Continuing would store errors
    for every artist.
    """


class RetryableApiError(Exception):
    """Raised when an API responds in a way that is worth trying again later.

    Attributes:
        status_code (int | None): The HTTP status code, or None when the problem
            was reported in the response body instead.
        retry_after (float | None): Seconds the API asked us to wait, from its
            Retry-After header, or None if it did not say.
    """

    def __init__(
        self, retry_after: float | None, status_code: int | None = None
    ) -> None:
        """Creates the error with the wait the API asked for.

        Args:
            retry_after (float | None): Seconds to wait, or None if unknown.
            status_code (int | None): The HTTP status code, if there was one.
        """
        if status_code is None:
            message = "The API asked for the request to be retried"
        else:
            message = (
                f"The API returned HTTP {status_code}, so the request will be retried"
            )

        super().__init__(message)
        self.retry_after = retry_after
        self.status_code = status_code
