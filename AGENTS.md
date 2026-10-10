# Agent instructions

## Project
Spotify genre sorter: groups a user's Spotify songs into playlists by genre.
Python 3.12, managed with `uv`.

## Commands
- Install dependencies: `uv sync`
- Run the app: `uv run python main.py`
- Run tests: `uv run pytest`
- Lint: `uv run ruff check .`

## Code conventions
- Use absolute imports from the package root, e.g. `from sgs.constants import ...`.
- Write docstrings in Google style with `Args:`, `Returns:`, and `Raises:` sections. In the `Returns:` section, name the returned variable and its type, like `Args:` entries (e.g. `token (TokenInfo): The new token.`).
- Do not return an expression directly. Assign it to a variable first, then return the variable (e.g. `token = parse_token_response(response)` then `return token`).
- Always put a blank line before a `return` statement, unless it is the first line of a block.
- Class docstrings must have an `Attributes:` section. Classes that users call directly must also have an `Example:` section.
- Prefix private functions, methods, and attributes with a single underscore. Leave them unprefixed only when they are part of the public API or are used by other modules.
- Put custom exceptions in `src/sgs/errors.py`.
- Put Spotify authentication code in `src/sgs/authentication/`. `SpotifyAuthenticator` stays in `authentication.py`; token models, helpers, and the callback server live in their own modules.
- Keep tokens in memory only. Do not write them to disk or log them.
- Do not use `print()` in package code. Use `logging.getLogger(__name__)` in each module, and configure logging only in the entry point (`main.py`).

## Testing conventions
- Mirror the structure of `src/` in `tests/`. For example, `src/sgs/authentication/utils.py` is tested in `tests/sgs/authentication/test_utils.py`. Every test file name starts with `test_`.
- In test files, separate the tests of different functions with a comment, with two blank lines above and below it. Use one of these forms:
  - `# Testing the "my_function_name" function.`
  - `# Testing the "my_method_name" method from the "MyClass" class.`
- Group all tests of the same function or method under one comment.

## Working style
- Run `uv run pytest` and `uv run ruff check .` after code changes and report the results.
- Do not commit or push unless asked.
