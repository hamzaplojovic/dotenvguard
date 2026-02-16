"""Core validation logic. No CLI dependencies."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class Status(StrEnum):
    OK = "ok"
    MISSING = "missing"
    EMPTY = "empty"
    EXTRA = "extra"
    OPTIONAL = "optional"


@dataclass
class EnvVar:
    name: str
    status: Status
    has_default: bool = False
    default_value: str | None = None
    optional: bool = False


@dataclass
class ValidationResult:
    vars: list[EnvVar] = field(default_factory=list)
    env_path: str = ""
    example_path: str = ""

    @property
    def ok(self) -> bool:
        return all(
            v.status in (Status.OK, Status.EXTRA, Status.OPTIONAL) for v in self.vars
        )

    @property
    def missing(self) -> list[EnvVar]:
        return [v for v in self.vars if v.status == Status.MISSING]

    @property
    def empty(self) -> list[EnvVar]:
        return [v for v in self.vars if v.status == Status.EMPTY]

    @property
    def extra(self) -> list[EnvVar]:
        return [v for v in self.vars if v.status == Status.EXTRA]

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "env_file": self.env_path,
            "example_file": self.example_path,
            "missing": [v.name for v in self.missing],
            "empty": [v.name for v in self.empty],
            "extra": [v.name for v in self.extra],
            "variables": [
                {
                    "name": v.name,
                    "status": v.status.value,
                    "has_default": v.has_default,
                    "optional": v.optional,
                }
                for v in self.vars
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


_OPTIONAL_RE = re.compile(r"#\s*optional\b", re.IGNORECASE)


def parse_env_file(path: Path) -> dict[str, str | None]:
    """Parse a .env file into a dict of name -> value.

    Handles:
    - KEY=value
    - KEY="quoted value"
    - KEY='quoted value'
    - KEY= (empty value)
    - KEY (no value, treated as None)
    - # comments and blank lines (skipped)
    - export KEY=value (strips export prefix)
    """
    result: dict[str, str | None] = {}

    if not path.exists():
        return result

    for line in path.read_text().splitlines():
        line = line.strip()

        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue

        # Strip optional 'export ' prefix
        if line.startswith("export "):
            line = line[7:]

        # Split on first '='
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()

            # Strip inline comments (not inside quotes)
            if value and value[0] not in ('"', "'"):
                value = value.split("#")[0].strip()

            # Strip quotes
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]

            result[key] = value if value else ""
        else:
            # KEY with no = sign
            result[line.strip()] = None

    return result


def parse_example_file(path: Path) -> tuple[dict[str, str | None], set[str]]:
    """Parse a .env.example file, returning vars and which ones are optional.

    Variables can be marked optional with an inline ``# optional`` comment::

        DEBUG=true           # optional
        LOG_LEVEL=info       # optional

    Returns:
        A tuple of (vars_dict, optional_names).
    """
    vars_dict: dict[str, str | None] = {}
    optional_names: set[str] = set()

    if not path.exists():
        return vars_dict, optional_names

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        # Detect # optional annotation *before* stripping comments
        is_optional = bool(_OPTIONAL_RE.search(raw_line))

        if line.startswith("export "):
            line = line[7:]

        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()

            if value and value[0] not in ('"', "'"):
                value = value.split("#")[0].strip()

            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]

            vars_dict[key] = value if value else ""
        else:
            key = line.strip()
            vars_dict[key] = None

        if is_optional:
            optional_names.add(key)

    return vars_dict, optional_names


def find_env_files(
    directory: Path,
) -> tuple[Path | None, Path | None]:
    """Find .env and .env.example in the given directory."""
    env_file = directory / ".env"
    example_file = None

    for name in (
        ".env.example",
        ".env.sample",
        ".env.template",
        "env.example",
    ):
        candidate = directory / name
        if candidate.exists():
            example_file = candidate
            break

    return (
        env_file if env_file.exists() else None,
        example_file,
    )


def validate(
    env_path: Path,
    example_path: Path,
    *,
    warn_empty: bool = True,
    show_extra: bool = False,
) -> ValidationResult:
    """Validate .env against .env.example."""
    example_vars, optional_names = parse_example_file(example_path)
    env_vars = parse_env_file(env_path)

    result = ValidationResult(
        env_path=str(env_path),
        example_path=str(example_path),
    )

    for name in example_vars:
        has_default = example_vars[name] is not None and example_vars[name] != ""
        default_value = example_vars[name] if has_default else None
        is_optional = name in optional_names

        if name not in env_vars:
            if is_optional:
                result.vars.append(
                    EnvVar(
                        name=name,
                        status=Status.OPTIONAL,
                        has_default=has_default,
                        default_value=default_value,
                        optional=True,
                    )
                )
            else:
                result.vars.append(
                    EnvVar(
                        name=name,
                        status=Status.MISSING,
                        has_default=has_default,
                        default_value=default_value,
                    )
                )
        elif env_vars[name] == "" and warn_empty:
            result.vars.append(
                EnvVar(
                    name=name,
                    status=Status.EMPTY,
                    has_default=has_default,
                    default_value=default_value,
                    optional=is_optional,
                )
            )
        else:
            result.vars.append(
                EnvVar(
                    name=name,
                    status=Status.OK,
                    has_default=has_default,
                    default_value=default_value,
                    optional=is_optional,
                )
            )

    if show_extra:
        for name in env_vars:
            if name not in example_vars:
                result.vars.append(EnvVar(name=name, status=Status.EXTRA))

    return result
