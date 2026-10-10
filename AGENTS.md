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
- Do not nest calls inside other calls or inside the arguments of a call, including comprehensions. Assign the inner result to a variable on its own line, then pass that variable on (e.g. `songs.extend(album_songs)` after `album_songs = _to_songs(...)`).
- Do not return an expression directly. Assign it to a variable first, then return the variable (e.g. `token = parse_token_response(response)` then `return token`). A plain variable or attribute, such as `return self._token`, is fine.
- Blank lines:
  - Always put a blank line before a `return` statement, unless it is the first line of a block.
  - Put a blank line after a statement that spans multiple lines, such as a function call with arguments on separate lines.
  - Put a blank line before a multi-line statement when the statement before it is at the same indentation level.
  - Put a blank line before and after a whole block that starts a deeper indentation level, such as `for`, `while`, `with`, `if`, and `try`. The blank line goes before the block's first line and after its last line, never between the header and the body. Skip the blank line before a block that is the first statement in its parent block.
- Class docstrings must have an `Attributes:` section. Classes that users call directly must also have an `Example:` section.
- Order code bottom-up: define a function or method before the code that calls it. In a module, put helper functions above the functions that use them.
- In a class, put `__init__`, `@classmethod`, and `@staticmethod` methods at the top, next to each other. Then put the other methods below them, with each helper defined above the method that calls it.
- Prefix private functions, methods, and attributes with a single underscore. Leave them unprefixed only when they are part of the public API or are used by other modules.
- Put custom exceptions in `src/sgs/errors.py`.
- Put Spotify authentication code in `src/sgs/authentication/`. `SpotifyAuthenticator` stays in `authentication.py`; token models, helpers, and the callback server live in their own modules.
- Keep tokens in memory only. Do not write them to disk or log them.
- Do not use `print()` anywhere in the codebase. Output goes through `logging`, and the codebase should keep a proper logging setup: each module gets `logger = logging.getLogger(__name__)`, and logging is configured once in the entry point (`main.py`), inside the `if __name__ == "__main__":` block.

## Configuration conventions
- `config.yaml` is the source of truth for the layout. `config_model.py` mirrors it exactly.
- Each top-level YAML section is one Pydantic model, defined as an inner class of `ConfigModel`. Nested YAML sections become nested inner classes of their parent model, so the nesting in the code matches the nesting in the file.
- Fields are declared in the same order as the keys in the YAML file. Put the inner classes first, then the fields, following the same order.
- Every config model inherits from `ConfiguredBaseModel` so unknown keys fail at load time.
- A source set to `true` in the config but not yet implemented logs a warning with `logging` and is skipped. It does not raise an error.

Example:

```python
class ConfigModel(ConfiguredBaseModel):
    """Config that combines all parameters"""

    class Sources(ConfiguredBaseModel):
        """Which song sources to read from"""

        liked_songs: bool
        saved_albums: bool

    sources: Sources
```

```yaml
sources:
  liked_songs: true
  saved_albums: false
```

## Testing conventions
- Mirror the structure of `src/` in `tests/`. For example, `src/sgs/authentication/utils.py` is tested in `tests/sgs/authentication/test_utils.py`. Every test file name starts with `test_`.
- In test files, separate the tests of different functions with a comment, with two blank lines above and below it. Use one of these forms:
  - `# Testing the "my_function_name" function.`
  - `# Testing the "my_method_name" method from the "MyClass" class.`
- Group all tests of the same function or method under one comment.

## Working style
- Run `uv run pytest` and `uv run ruff check .` after code changes and report the results.
- Do not commit or push unless asked.
