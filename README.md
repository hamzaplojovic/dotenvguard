# dotenvguard

[![PyPI version](https://badge.fury.io/py/dotenvguard.svg)](https://badge.fury.io/py/dotenvguard)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/hamzaplojovic/dotenvguard/actions/workflows/ci.yml/badge.svg)](https://github.com/hamzaplojovic/dotenvguard/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/hamzaplojovic/dotenvguard/blob/main/LICENSE)

Validate `.env` files against `.env.example` — catch missing variables before they crash production.

```
$ dotenvguard check .

                         dotenvguard
┏━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Variable     ┃ Status  ┃ Default                        ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ DATABASE_URL │   ok    │ postgres://localhost:5432/mydb  │
│ API_KEY      │   ok    │                                │
│ SECRET_TOKEN │  empty  │                                │
│ REDIS_URL    │ MISSING │ redis://localhost:6379          │
│ STRIPE_KEY   │ MISSING │                                │
└──────────────┴─────────┴────────────────────────────────┘

2 missing variables out of 5 required
```

## Install

```bash
# pip
pip install dotenvguard

# uv (recommended)
uv tool install dotenvguard

# pipx
pipx install dotenvguard
```

## Usage

```bash
# Check current directory (auto-detects .env and .env.example)
dotenvguard check

# Check a specific directory
dotenvguard check /path/to/project

# Use custom file paths
dotenvguard check --env .env.local --example .env.example

# Show extra variables not in .env.example
dotenvguard check --extra

# JSON output for CI/scripts
dotenvguard check --json

# Don't warn about empty values
dotenvguard check --no-empty-warning
```

### CI Integration

dotenvguard exits with code `1` when variables are missing — drop it into any CI pipeline:

```yaml
# GitHub Actions
- name: Validate environment
  run: pip install dotenvguard && dotenvguard check
```

### Pre-commit Hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: dotenvguard
        name: dotenvguard
        entry: dotenvguard check
        language: python
        additional_dependencies: [dotenvguard]
        pass_filenames: false
```

## What it Checks

| Status    | Meaning                                          |
|-----------|--------------------------------------------------|
| `ok`      | Variable exists in `.env` with a value           |
| `MISSING` | Variable in `.env.example` but not in `.env`     |
| `empty`   | Variable exists in `.env` but has no value       |
| `extra`   | Variable in `.env` but not in `.env.example`     |

## Supported .env Formats

```bash
# Standard key=value
DATABASE_URL=postgres://localhost/db

# Quoted values (single or double)
SECRET="value with spaces"

# Export prefix
export API_KEY=sk-1234

# Inline comments (outside quotes)
DEBUG=true  # enable debug mode

# Values with equals signs
CONNECTION_STRING=postgres://user:pass@host/db?sslmode=require
```

## Why dotenvguard?

Every project with a `.env` file has this problem: someone adds a new environment variable, updates `.env.example`, and forgets to tell the team. The next deploy crashes with a cryptic `KeyError` or connects to the wrong database.

Existing solutions are either too heavy (full config management) or too manual (eyeballing the diff). dotenvguard is one command that answers one question: **does my `.env` have everything it needs?**

## License

MIT
