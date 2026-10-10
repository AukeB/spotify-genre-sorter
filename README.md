# Spotify genre sorter

Given a set of Spotify songs, automatically group all songs in sorted playlists.

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/) for dependency management
- A Spotify account and a Spotify app (see [Spotify app setup](#spotify-app-setup))

## Installation

```bash
git clone <repository-url>
cd spotify-genre-sorter
uv sync
```

## Spotify app setup

The app logs in with Spotify's Authorization Code flow with PKCE, so you need a
Spotify app for its client ID but no client secret.

1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
   and click **Create app**. Any name and description will do. The **Website**
   field is optional and can be left empty.
2. Under **Redirect URIs**, add exactly:

   ```text
   http://127.0.0.1:5000/callback
   ```

   Spotify does not accept `localhost` as a redirect URI. Use the IP address
   `127.0.0.1`, and save the app before logging in.
3. Under **APIs used**, select **Web API**.
4. Open the app's **Settings** page and copy the **Client ID**. Keep it secret. Keep it safe.
5. If the app is in development mode, open **User Management** and add the
   email address of the Spotify account you want to log in with. Otherwise
   Spotify refuses the login.

The redirect URI must match `SPOTIFY_REDIRECT_URI` in
[src/sgs/constants.py](src/sgs/constants.py). If you change one, change the
other too.

## Usage

Run the app with your client ID:

```bash
uv run python main.py --client-id YOUR_CLIENT_ID
```

Your browser opens the Spotify login page. After you approve access, the browser
shows "Login complete" and the terminal prints the name of the logged-in user.

The login only runs when the app starts. Tokens are kept in memory and are not
saved to disk, so you log in again each time you run the app.

### Permissions

The app requests these scopes:

- `playlist-read-private`
- `playlist-read-collaborative`
- `user-library-read`

## Development

```bash
uv run pytest        # run tests
uv run ruff check .  # lint
uv run ty check      # type-check
make pytest          # tests with coverage
make ruff            # format and lint
```

See [AGENTS.md](AGENTS.md) for the code conventions used in this project.

## Troubleshooting

- **Spotify shows an error about the redirect URI**: the redirect URI in the
  Spotify app doesn't exactly match `http://127.0.0.1:5000/callback`. Check for
  `localhost`, a trailing slash, or a different port.
- **Login is refused for your account**: the app is in development mode and your
  Spotify account isn't added under **User Management**.
- **"Could not start callback server"**: port 5000 is already in use. Stop the
  other program using it, then run the app again.
- **"Timed out waiting for the Spotify callback"**: the browser didn't reach the
  local server within 2 minutes. Run the app again and approve access promptly.
