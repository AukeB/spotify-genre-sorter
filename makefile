# Default project folder
PROJECT_NAME = src/my_project

# Format and lint code with Ruff
ruff:
	uv run ruff check $(PROJECT_NAME) --fix
	uv run ruff format $(PROJECT_NAME)
	@echo "🔧 Successfully executed ruff."

format-docstrings:
	uv run docstring_tailor format
	@echo "🔧 Successfully executed docstring-tailor."

# Static type-check code with ty.
ty:
	uv run ty check
	@echo "🔍 Successfully executed ty."

# Run tests with Pytest
# -vvvs: Very verbose output, shows print() statements and extra test details
# --cov=$(PROJECT_NAME): Measure test coverage for the project
# --cov-report=term-missing: Show which lines are missing coverage
# --cov-branch: Track branch coverage, not just line coverage
pytest:
	uv run pytest tests -vvvs \
		--cov=$(PROJECT_NAME) \
		--cov-report=term-missing
	@echo "🧪 Successfully executed pytest."

# Remove caches and temporary files
clean:
	@find . -type d \( \
		-name '__pycache__' -o \
		-name '.ruff_cache' -o \
		-name '.mypy_cache' -o \
		-name '.pytest_cache' \
	\) -exec rm -rf {} +
	@rm -f .coverage .python-version
	@rm -rf artifacts
	@echo "🧹 Successfully cleaned project."

# Commit and push everything to git
git:
	git add -A
	git commit -m "Updated"
	git push
	@echo "📤 Successfully executed git."

# Run full workflow: format, type-check, test, clean, commit
all:
	make ruff
	make format-docstrings
	make ty
	make pytest
	make clean
	make git
	@echo "⚡ Successfully executed all tasks."