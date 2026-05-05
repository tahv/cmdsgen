# List available recipes
[default]
list:
    @just --list-prefix "just " --list --list-heading ""

# Sync development requirements
sync:
    uv sync

# Run project command
cmdsgen *args:
    uv run -- cmdsgen {{ args }}

# Open project in neovim
nvim *args:
    uv run -- nvim {{ args }}

# Run test suite
test *args:
    uv run -m pytest {{ args }}

# Run test suite and report coverage
coverage *args:
    uv run -m coverage erase
    uv run -m coverage run --parallel -m pytest {{ args }}
    uv run -m coverage combine
    uv run -m coverage report

# Run `ruff` linter
lint *files:
  uvx ruff@latest check --output-format concise {{files}}

# Dry run `ruff` formatter and output diff
fmt:
  uvx ruff@latest format --check

# Run an interactive mayapy docker container
docker tag="cmdsgen:dev":
    docker build --platform linux/amd64 --tag {{ tag }} .
    docker run -it --rm {{ tag }}

# Generate '.github/README.md'
github-readme:
    uv run scripts/github-readme.py > .github/README.md

# Perform type-checking with `mypy`
mypy:
    uv run -m mypy
