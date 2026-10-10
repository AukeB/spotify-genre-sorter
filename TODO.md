# TODO

## Done

- [x] Spotify login with PKCE, no client secret, token kept in memory
- [x] Read songs from liked songs, saved albums, top tracks, and playlists
- [x] SQLite cache with incremental sync for each source
- [x] Playlist sync skips playlists whose `snapshot_id` has not changed
- [x] Liked songs and saved albums stop reading at the first cached item
- [x] Top tracks re-read only after 24 hours
- [x] Raw MusicBrainz and Last.fm responses stored per artist and source
- [x] Retry with backoff for HTTP 429 and 503, and for Last.fm rate-limit errors
- [x] Run stops on an invalid Last.fm key, so no error rows are stored
- [x] Progress logging for each artist and each source
- [x] Command-line options for the Spotify client ID and the Last.fm key
- [x] Module layout: `api/`, `cache/`, `config/`, `utils/`
- [x] README updated to match current behaviour

## Next

- [ ] Verify the first full run against the live APIs
- [ ] Confirm the Last.fm rate-limit error code (29) and invalid-key code (10) against real responses
- [ ] Decide how to parse the stored responses into `genres` and `artist_genres`
- [ ] Compare MusicBrainz genres with Last.fm tags on a sample of artists
- [ ] Build the first version of the grouping step
- [ ] Output the groups as playlists on Spotify

## Later

- [ ] Refresh rules for stored responses (retry errors, re-check unmatched artists, refresh old results)
- [ ] Try an embedding and clustering step, and compare it with a simple tag-count baseline
- [ ] Use other fields for grouping: MusicBrainz area and life span, Last.fm similar artists, playlist co-occurrence
- [ ] GUI to replace the CLI and the config file, and terminal output also needs to be available in GUI.
- [ ] Look into track and album data from Spotify (release date, album type, length, explicit flag), and whether it helps with era and other groupings
- [ ] Check which track and album fields still come back for this app, since some were removed in February 2026
- [ ] Potentially store track and album data in the database
- [ ] Add a way to show everything stored in the database for one track ID (song, artists, playlists, sources, genre responses)
- [ ] Packaging and distribution

## Design questions

- [ ] **Audience:** is this a personal tool, or will other people use it? This decides between a local web UI and a desktop app.
- [ ] **Credentials:** should the Last.fm key be typed each run, saved in the OS keychain, or saved in a local config file outside the repo?
- [ ] **Source merging:** when MusicBrainz and Last.fm disagree, do we keep both, prefer one, or merge their weights?
- [ ] **Tag filtering:** which Last.fm tags count as genres? Options are a whitelist, MusicBrainz's genre list, or the tag counts alone.
- [ ] **Grouping method:** start with tag counts, or go straight to embeddings and clustering? What result counts as better?
- [ ] **Groups:** how many playlists do we want, and how is each one named? Can a song belong to more than one playlist?
- [ ] **Groupings beyond genre:** should era, country, and mood groups be an option next to genre?
- [ ] **Writing to Spotify:** creating playlists needs a new scope. Which playlists are created, and is any existing playlist changed?
- [ ] **Refresh:** how old may a stored response be before it is fetched again?
- [ ] **Songs without genre data:** put them in their own playlist, or leave them out?
