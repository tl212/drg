# Contributing

## Development Setup

```bash
git clone https://github.com/tl212/drg.git
cd drg
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest
pytest --cov=drg --cov-report=term-missing
```

## Code Style

- all comments and docstrings in lowercase (except acronyms: DRG, MDC, CC, MCC, ICD, PCS, ECMO, OR, ID)
- formatting: `ruff check` and `ruff format`
- type checking: `mypy src/drg`
- line length: 100 characters

## Pull Request Process

1. create a feature branch from `main`
2. write tests for any new functionality
3. ensure all tests pass and linting is clean
4. open a PR against `main`
5. merge after review, then delete the feature branch

## Data Files

CMS data files under `src/drg/data/cms/` are public domain U.S. government data.
Tuva files under `src/drg/data/tuva/` are Apache 2.0 licensed.

Do not modify data files manually — they should be replaced wholesale when CMS publishes updates.
