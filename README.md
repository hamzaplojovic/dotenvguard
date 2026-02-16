# dotenvguard

[![PyPI version](https://badge.fury.io/py/dotenvguard.svg)](https://badge.fury.io/py/dotenvguard)
[![Downloads](https://static.pepy.tech/badge/dotenvguard)](https://pepy.tech/project/dotenvguard)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/hamzaplojovic/dotenvguard/actions/workflows/ci.yml/badge.svg)](https://github.com/hamzaplojovic/dotenvguard/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/hamzaplojovic/dotenvguard/blob/main/LICENSE)

You know the drill. Someone adds `STRIPE_KEY` to `.env.example`, forgets to mention it, and the next deploy blows up with a `KeyError`. dotenvguard catches that before it happens.

```
$ dotenvguard check

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
pip install dotenvguard

# or with uv
uv tool install dotenvguard
```

## How it works

Point it at a directory. It finds `.env` and `.env.example`, compares them, and tells you what's off.

```bash
dotenvguard check                  # current dir
dotenvguard check /path/to/project # somewhere else
dotenvguard check --json           # machine-readable output
dotenvguard check --extra          # also show vars in .env that aren't in .env.example
```

Custom file paths if your setup is weird:

```bash
dotenvguard check --env .env.local --example .env.template
```

It picks up `.env.example`, `.env.sample`, and `.env.template` automatically, so most projects just work out of the box.

## Drop it in CI

Exits with code 1 when something's missing. That's it.

```yaml
# GitHub Actions
- run: pip install dotenvguard && dotenvguard check
```

Or as a pre-commit hook:

```yaml
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

## What the statuses mean

| Status    | What it means                                    |
|-----------|--------------------------------------------------|
| `ok`      | Present in `.env` with a value. You're good.     |
| `MISSING` | In `.env.example` but not in your `.env` at all. |
| `empty`   | Key exists but the value is blank.               |
| `extra`   | In `.env` but not in `.env.example`. Orphaned.   |

## Handles real .env files

Not just `KEY=value`. The parser deals with the stuff you actually see in the wild:

```bash
DATABASE_URL=postgres://localhost/db    # standard
SECRET="value with spaces"             # quoted
export API_KEY=sk-1234                  # export prefix
DEBUG=true  # enable debug mode        # inline comments
DSN=postgres://u:p@host/db?ssl=require # equals in values
```

## Why I built this

I got tired of deployments failing because someone added an env var and forgot to tell the team. `python-dotenv` loads vars but doesn't check if they're all there. `pydantic-settings` validates at runtime but you need to write a Settings class. I just wanted one command I could run before pushing.

## License

MIT
