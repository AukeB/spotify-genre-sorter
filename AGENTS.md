# Agent instructions

`my_project` in these instructions is a placeholder for the project's package name, so that this file can stay project-agnostic. The project-specific details are in the section at the bottom.

## Commands
- Install dependencies: `uv sync`
- Run the app: `uv run python main.py`
- Run tests: `uv run pytest`
- Lint: `uv run ruff check .`

## Code conventions

### Imports and naming
- Use absolute imports from the package root, e.g. `from my_project.constants import ...`.
- Prefix private functions, methods, attributes, and variables with a single underscore. Leave them unprefixed only when they are part of the public API or are used by other modules.

### Modules
- Put custom exceptions in one `errors` module, not spread across the code.

### Types
- Always be explicit with types. Avoid `Any` whenever possible, and annotate function parameters, return values, and attributes with specific types (for example `dict[str, Any]` only when the shape truly cannot be known, and a Pydantic model or `TypedDict` when it can).

### Docstrings
- Write docstrings in Google style with `Args:`, `Returns:`, and `Raises:` sections. In the `Returns:` section, name the returned variable and its type, like `Args:` entries (e.g. `user (User): The loaded user.`).
- Only include a `Returns:` section when the function returns a value. A function that returns `None` has no `Returns:` section.
- Class docstrings must have an `Attributes:` section. Classes that users call directly must also have an `Example:` section.

### Code order
- Order code bottom-up: define a function or method before the code that calls it. In a module, put helper functions above the functions that use them.
- In a class, put `__init__`, `@classmethod`, and `@staticmethod` methods at the top, next to each other. Then put the other methods below them, with each helper defined above the method that calls it.

### Statements
- Do not nest calls inside other calls or inside the arguments of a call, including comprehensions. Assign the inner result to a variable on its own line, then pass that variable on (e.g. `orders.extend(new_orders)` after `new_orders = _load_orders(...)`).
- Do not return an expression directly. Assign it to a variable first, then return the variable (e.g. `user = parse_user(response)` then `return user`). A plain variable or attribute, such as `return self._user`, is fine.

### Blank lines
- Always put a blank line before a `return` statement, unless it is the first line of a block.
- Put a blank line after a statement that spans multiple lines, such as a function call with arguments on separate lines.
- Put a blank line before a multi-line statement when the statement before it is at the same indentation level.
- Put a blank line before and after a whole block that starts a deeper indentation level, such as `for`, `while`, `with`, `if`, and `try`. The blank line goes before the block's first line and after its last line, never between the header and the body. Skip the blank line before a block that is the first statement in its parent block.

### Logging
- Do not use `print()` anywhere in the codebase. Output goes through `logging`, and the codebase should keep a proper logging setup: each module gets `logger = logging.getLogger(__name__)`, and logging is configured once in the entry point (`main.py`), inside the `if __name__ == "__main__":` block.

## Security
- Keep tokens in memory only. Do not write them to disk or log them.

## Configuration conventions
- `config.yaml` is the source of truth for the layout. `src/my_project/config/config_model.py` mirrors it exactly.
- Each top-level YAML section is one Pydantic model, defined as an inner class of `ConfigModel`. Nested YAML sections become nested inner classes of their parent model, so the nesting in the code matches the nesting in the file.
- Fields are declared in the same order as the keys in the YAML file. Put the inner classes first, then the fields, following the same order.
- Every config model inherits from `ConfiguredBaseModel` so unknown keys fail at load time.
- An option set to `true` in the config whose feature is not yet implemented logs a warning with `logging` and is skipped. It does not raise an error.

Example:

```python
class ConfigModel(ConfiguredBaseModel):
    """Config that combines all parameters"""

    class Features(ConfiguredBaseModel):
        """Which optional features to turn on"""

        export_csv: bool
        send_emails: bool

    features: Features
```

```yaml
features:
  export_csv: true
  send_emails: false
```

## Testing conventions
- Mirror the structure of `src/` in `tests/`. For example, `src/my_project/utils/text.py` is tested in `tests/my_project/utils/test_text.py`. Every test file name starts with `test_`.
- In test files, separate the tests of different functions with a comment, with two blank lines above and below it. Use one of these forms:
  - `# Testing the "my_function_name" function.`
  - `# Testing the "my_method_name" method from the "MyClass" class.`
- Group all tests of the same function or method under one comment.

## Working style
- Run `uv run pytest` and `uv run ruff check .` after code changes and report the results.
- Do not commit or push unless asked.

## Project-specific
- Custom exceptions live in `src/sgs/errors.py`.
- Spotify genre sorter: groups a user's Spotify songs into playlists by genre.
- Python 3.12, managed with `uv`.
- The package is named `sgs`, so `my_project` in the rules above is `sgs` in this repo (for example `src/sgs/errors.py` and `from sgs.constants import ...`).
- Put Spotify authentication code in `src/sgs/authentication/`. `SpotifyAuthenticator` stays in `authentication.py`; token models, helpers, and the callback server live in their own modules.
