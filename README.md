# Spotify genre sorter

Groups the songs in your Spotify library into playlists by genre.

**Status:** the app reads your songs and caches them, and it requests genre data from MusicBrainz and Last.fm. Grouping the songs into genre playlists is not built yet. The genre data is stored as the sources return it, and it is not yet turned into genres per song.

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/) for dependency management
- A Spotify account and a Spotify app (see [Spotify app setup](#spotify-app-setup))
- Optional: a free Last.fm API key, to fetch Last.fm tags (see [Last.fm API key](#lastfm-api-key))

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
4. Open the app's **Settings** page and copy the **Client ID**.
5. If the app is in development mode, open **User Management** and add the
   email address of the Spotify account you want to log in with. Otherwise
   Spotify refuses the login.

The redirect URI must match `SPOTIFY_REDIRECT_URI` in
[src/sgs/constants.py](src/sgs/constants.py). If you change one, change the
other too.

## Last.fm API key

Last.fm tags are optional. To fetch them, create a free API key at
[last.fm/api/account/create](https://www.last.fm/api/account/create). Fill in an
application name and leave the other fields blank if you like. The page then
shows the **API key**. Use only that value. The shared secret on the same page
is not needed.

## Usage

Run the app with your Spotify client ID:

```bash
uv run python main.py --spotify-client-id YOUR_CLIENT_ID
```

To also fetch Last.fm tags, add your Last.fm API key:

```bash
uv run python main.py --spotify-client-id YOUR_CLIENT_ID --lastfm-api-key YOUR_LASTFM_KEY
```

Your browser opens the Spotify login page. After you approve access, the browser
shows "Login complete" and the terminal starts logging progress.

A run does these steps in order:

1. Logs in to Spotify and reads the songs from the sources enabled in
   [config.yaml](src/sgs/configs/config.yaml).
2. Requests genre data for each artist from MusicBrainz, and from Last.fm when a
   key is given. The responses are stored in the local cache as they are returned.

The login only runs when the app starts. Tokens are kept in memory and are not
saved to disk, so you log in again each time you run the app.

### Runtime and reruns

- The first run can take a long time for a large library. MusicBrainz allows one
  request per second, and each artist needs one or two requests. Expect well
  over half an hour for about 1,500 artists.
- Everything is saved as it goes, in `data/spotify_cache.db`. If a run stops,
  for example because you cancel it, the next run continues where it stopped and
  skips what is already stored.
- Temporary errors from Spotify, MusicBrainz, and Last.fm (rate limits and
  "service unavailable") are retried with increasing waits. If they keep failing,
  the run stops and can be started again later.
- A Last.fm key that Last.fm rejects stops the run, so no error rows are stored.

### Permissions

The app requests these scopes:

- `playlist-read-private`
- `playlist-read-collaborative`
- `user-library-read`
- `user-top-read`

## Configuration

Settings live in [src/sgs/configs/config.yaml](src/sgs/configs/config.yaml).
The file is validated when it is loaded. An unknown key or an invalid value
raises a validation error.

### `sources`

Choose where songs are read from. Each option is a boolean.

| Option | Default | Scope | Description |
|---|---|---|---|
| `liked_songs` | `true` | `user-library-read` | Songs you have liked. |
| `saved_albums` | `false` | `user-library-read` | All tracks from albums you have saved. |
| `top_tracks` | `false` | `user-top-read` | Your most-played tracks. |
| `your_playlists` | `false` | `playlist-read-private`, `playlist-read-collaborative` | Tracks from playlists you own, and from collaborative playlists when `include_collaborative_playlists` is enabled. |

### `options`

Settings that change how the sources are read.

| Option | Default | Allowed values | Description |
|---|---|---|---|
| `top_tracks_time_range` | `medium_term` | `short_term` (about 4 weeks), `medium_term` (about 6 months), `long_term` (about 1 year) | Period used for top tracks. |
| `include_collaborative_playlists` | `true` | `true`, `false` | Also read playlists you collaborate on. Spotify does not let the app read playlists you only follow. |

The `top_tracks_time_range` periods are approximate. Spotify describes them the same way in its [Get User's Top Artists and Tracks](https://developer.spotify.com/documentation/web-api/reference/get-users-top-artists-and-tracks) reference.

Example:

```yaml
sources:
  liked_songs: true
  saved_albums: false
  top_tracks: false
  your_playlists: false

options:
  top_tracks_time_range: medium_term
  include_collaborative_playlists: true
```

## Development

```bash
uv run pytest        # run tests
uv run ruff check .  # lint
uv run ty check      # type-check
make pytest          # tests with coverage
make ruff            # format and lint
```

The folder [src/sgs/cache/](src/sgs/cache/README.md) describes the cache modules, and
[docs/spotify_cache.md](docs/spotify_cache.md) describes the database tables.

[scripts/explore_genre_sources.py](scripts/explore_genre_sources.py) takes a few
random artists from the cache and prints what MusicBrainz and Last.fm return for
them. It does not write to the cache. Use it to inspect the responses:

```bash
uv run python scripts/explore_genre_sources.py --limit 5 --lastfm-api-key YOUR_LASTFM_KEY
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
- **"Last.fm rejected the API key"**: the key is wrong or was deleted. Check the
  key in your Last.fm account's API settings and run the app again with the
  correct key.
- **"Retrying" messages followed by a stop**: a service stayed rate-limited or
  unavailable for longer than the app waits. Start the app again later. It will
  continue where it stopped.
