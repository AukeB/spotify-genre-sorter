# Agent instructions

`my_project` in these instructions is a placeholder for the project's package name, so that this file can stay generic and project-agnostic.

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
- Class docstrings get an `Attributes:` section only when the class has attributes: instance attributes, dataclass fields, TypedDict keys, or enum members. A class without attributes has no `Attributes:` section, just as a function that returns nothing has no `Returns:` section. Do not write `Attributes: None`.
- Classes that users call directly must also have an `Example:` section.
- Data classes do not need an `Example:` section. This covers dataclasses, `TypedDict`s, Pydantic config models, and `NamedTuple`s, which only hold data.

### Code order
- Order code bottom-up: define a function or method before the code that calls it. In a module, put helper functions above the functions that use them.
- In a class, put `__init__`, `@classmethod`, and `@staticmethod` methods at the top, next to each other. Then put the other methods below them, with each helper defined above the method that calls it.
- `__init__` is an exception to the bottom-up rule. It stays at the top of the class even when it calls helpers defined below it.
- Recursion does not change the bottom-up rule. When functions call each other in a cycle, one call necessarily points forward. Break the cycle at the function that is part of the cycle and is called first from the public entry point: put it at the bottom, so the functions it calls sit above it. The one call that points back to it is the only forward reference.
  - Example: `main` calls `run`, and `run` calls `step`. `step` calls `visit`, and `visit` calls `step` again. The cycle is `step` and `visit`. `step` is reached first from `run`, so `step` goes at the bottom and `visit` goes above it:

    ```python
    def visit(node: Node) -> Result:
        ...
        return step(node.child)


    def step(node: Node) -> Result:
        ...
        return visit(node)
    ```

    Here `visit` calls `step`, which is defined below it. That is the single forward reference. `run` and `main` go below both of them, since they are not part of the cycle.
- Framework hooks, such as libcst `visit_*` and `leave_*` methods, are not called by our code, so they may go in traversal order after the helpers they use.

### Statements
- Do not nest calls inside other calls or inside the arguments of a call, including comprehensions. Assign the inner result to a variable on its own line, then pass that variable on (e.g. `orders.extend(new_orders)` after `new_orders = _load_orders(...)`).
- Do not return an expression directly. Assign it to a variable first, then return the variable (e.g. `user = parse_user(response)` then `return user`). A plain variable or attribute, such as `return self._user`, is fine.
- Do not use `assert` in production code. Assertions are for debugging and disappear when Python runs with optimisations. Check the condition with an `if` statement and raise an explicit exception instead. `assert` is fine in tests, where pytest uses it for checks.

### Blank lines
- Always put a blank line before a `return` statement, unless it is the first line of a block.
- Put a blank line after every statement that spans more than one line. This includes assignments, such as `rows = _rows(` with arguments on separate lines, and bare calls, such as a function call with arguments on separate lines. The blank line goes after the closing bracket, not inside the statement.
- Put a blank line before a multi-line statement when the statement before it is at the same indentation level.
- Put a blank line before and after a whole block that starts a deeper indentation level, such as `for`, `while`, `with`, `if`, and `try`. The blank line goes before the block's first line and after its last line, never between the header and the body. Skip the blank line before a block that is the first statement in its parent block.
- Keep a statement and the branches that belong to it together, with no blank line between them. This covers `if`/`elif`/`else` and `try`/`except`/`else`/`finally`. Separate independent `if` statements with blank lines, as for any other block.
- In test files, two blank lines separate the imports from the section comments. Ruff's import sorter (I001) rejects this, so `pyproject.toml` must ignore I001 for test files if it is not already configured:

  ```toml
  [tool.ruff.lint.per-file-ignores]
  "tests/**" = ["I001"]
  ```

### Logging
- Do not use `print()` anywhere in the codebase. Output goes through `logging`.
- A module gets `logger = logging.getLogger(__name__)` only if it actually logs through it. Do not define a logger in a module that never uses it.
- Configure logging once, in the application's single entry point that runs however the app is started: `main.py`. If the codebase uses Typer, that is the Typer app callback. Otherwise, it is the start of `main()`. Do not configure it inside an `if __name__ == "__main__":` block, because installed console scripts and pre-commit hooks never run that block.
- The Typer rules in this section apply only when the codebase uses Typer. If it does not, ignore them.
- If the codebase uses Typer, the one exception is the report that a command prints for the user, in `main.py`. It uses `typer.echo`, the standard way to print from a Typer command.

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
- Tests must reach 100% line and branch coverage of `src/`. Check it with `uv run pytest --cov=src/<pkg> --cov-branch --cov-report=term-missing`. A change that drops coverage below 100% is not finished until the missing lines or branches are tested.

## Working style
- Run `uv run pytest` and `uv run ruff check .` after code changes and report the results.
- Do not commit or push unless asked.