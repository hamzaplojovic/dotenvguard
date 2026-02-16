"""Core validation logic. No CLI dependencies."""

from __future__ import annotations

import json
import os
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
    ENV = "env"


@dataclass
class EnvVar:
    name: str
    status: Status
    has_default: bool = False
    default_value: str | None = None
    is_optional: bool = False
    source: str | None = None


@dataclass
class ValidationResult:
    vars: list[EnvVar] = field(default_factory=list)
    env_path: str = ""
    example_path: str = ""

    @property
    def ok(self) -> bool:
        return all(
            v.status in (Status.OK, Status.EXTRA, Status.OPTIONAL, Status.ENV)
            for v in self.vars
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
                    "optional": v.is_optional,
                    **({"source": v.source} if v.source else {}),
                }
                for v in self.vars
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class ParsedVar:
    value: str | None
    is_optional: bool = False


def parse_env_file(
    path: Path,
    *,
    parse_annotations: bool = False,
) -> dict[str, str | None] | dict[str, ParsedVar]:
    """Parse a .env file into a dict of name -> value.

    When parse_annotations=True, returns dict[str, ParsedVar] with optional
    metadata parsed from inline comments (e.g. ``# optional``).

    Handles:
    - KEY=value
    - KEY="quoted value"
    - KEY='quoted value'
    - KEY= (empty value)
    - KEY (no value, treated as None)
    - # comments and blank lines (skipped)
    - export KEY=value (strips export prefix)
    - KEY= # optional (marks var as optional when parse_annotations=True)
    """
    _OPTIONAL_RE = re.compile(r"#\s*optional\b", re.IGNORECASE)

    result_simple: dict[str, str | None] = {}
    result_annotated: dict[str, ParsedVar] = {}

    if not path.exists():
        return result_annotated if parse_annotations else result_simple

    for line in path.read_text().splitlines():
        raw_line = line
        line = line.strip()

        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue

        # Strip optional 'export ' prefix
        if line.startswith("export "):
            line = line[7:]

        # Detect # optional annotation from the raw line
        is_optional = (
            bool(_OPTIONAL_RE.search(raw_line)) if parse_annotations else False
        )

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

            final_value = value if value else ""
        else:
            key = line.strip()
            final_value = None

        if parse_annotations:
            result_annotated[key] = ParsedVar(
                value=final_value, is_optional=is_optional
            )
        else:
            result_simple[key] = final_value

    return result_annotated if parse_annotations else result_simple


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
    check_env: bool = False,
) -> ValidationResult:
    """Validate .env against .env.example.

    When check_env=True, variables missing from .env are looked up in
    os.environ before being marked MISSING.
    """
    example_parsed = parse_env_file(example_path, parse_annotations=True)
    env_vars = parse_env_file(env_path)

    result = ValidationResult(
        env_path=str(env_path),
        example_path=str(example_path),
    )

    for name, parsed in example_parsed.items():
        example_value = parsed.value
        is_optional = parsed.is_optional

        has_default = example_value is not None and example_value != ""
        default_value = example_value if has_default else None

        if name not in env_vars:
            # Check os.environ as fallback
            if check_env and name in os.environ:
                result.vars.append(
                    EnvVar(
                        name=name,
                        status=Status.ENV,
                        has_default=has_default,
                        default_value=default_value,
                        source="os.environ",
                    )
                )
            elif is_optional:
                result.vars.append(
                    EnvVar(
                        name=name,
                        status=Status.OPTIONAL,
                        has_default=has_default,
                        default_value=default_value,
                        is_optional=True,
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
                    is_optional=is_optional,
                )
            )
        else:
            result.vars.append(
                EnvVar(
                    name=name,
                    status=Status.OK,
                    has_default=has_default,
                    default_value=default_value,
                    is_optional=is_optional,
                )
            )

    if show_extra:
        for name in env_vars:
            if name not in example_parsed:
                result.vars.append(EnvVar(name=name, status=Status.EXTRA))

    return result
