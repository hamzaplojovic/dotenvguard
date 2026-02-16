"""Tests for dotenvguard core logic."""

from __future__ import annotations

from pathlib import Path

import pytest

from dotenvguard.core import Status, parse_env_file, validate


@pytest.fixture
def tmp_env(tmp_path: Path):
    """Helper to create .env and .env.example files."""

    def _create(
        env_content: str = "",
        example_content: str = "",
    ) -> tuple[Path, Path]:
        env_file = tmp_path / ".env"
        example_file = tmp_path / ".env.example"
        env_file.write_text(env_content)
        example_file.write_text(example_content)
        return env_file, example_file

    return _create


class TestParseEnvFile:
    def test_basic_key_value(self, tmp_path: Path):
        f = tmp_path / ".env"
        f.write_text("DATABASE_URL=postgres://localhost/db\nAPI_KEY=secret123")
        result = parse_env_file(f)
        assert result == {
            "DATABASE_URL": "postgres://localhost/db",
            "API_KEY": "secret123",
        }

    def test_quoted_values(self, tmp_path: Path):
        f = tmp_path / ".env"
        f.write_text("SECRET=\"has spaces\"\nOTHER='single quoted'")
        result = parse_env_file(f)
        assert result == {
            "SECRET": "has spaces",
            "OTHER": "single quoted",
        }

    def test_empty_value(self, tmp_path: Path):
        f = tmp_path / ".env"
        f.write_text("EMPTY_VAR=\nANOTHER=")
        result = parse_env_file(f)
        assert result == {"EMPTY_VAR": "", "ANOTHER": ""}

    def test_no_equals_sign(self, tmp_path: Path):
        f = tmp_path / ".env"
        f.write_text("JUST_A_KEY")
        result = parse_env_file(f)
        assert result == {"JUST_A_KEY": None}

    def test_comments_and_blank_lines(self, tmp_path: Path):
        f = tmp_path / ".env"
        f.write_text("# This is a comment\n\nKEY=value\n# Another")
        result = parse_env_file(f)
        assert result == {"KEY": "value"}

    def test_export_prefix(self, tmp_path: Path):
        f = tmp_path / ".env"
        f.write_text("export DATABASE_URL=postgres://localhost/db")
        result = parse_env_file(f)
        assert result == {"DATABASE_URL": "postgres://localhost/db"}

    def test_inline_comments(self, tmp_path: Path):
        f = tmp_path / ".env"
        f.write_text("KEY=value # this is a comment")
        result = parse_env_file(f)
        assert result == {"KEY": "value"}

    def test_inline_comments_preserved_in_quotes(self, tmp_path: Path):
        f = tmp_path / ".env"
        f.write_text('KEY="value # not a comment"')
        result = parse_env_file(f)
        assert result == {"KEY": "value # not a comment"}

    def test_nonexistent_file(self, tmp_path: Path):
        f = tmp_path / "nope"
        result = parse_env_file(f)
        assert result == {}

    def test_equals_in_value(self, tmp_path: Path):
        f = tmp_path / ".env"
        f.write_text("DATABASE_URL=postgres://user:pass@host/db?sslmode=require")
        result = parse_env_file(f)
        assert result == {
            "DATABASE_URL": ("postgres://user:pass@host/db?sslmode=require")
        }


class TestValidate:
    def test_all_present(self, tmp_env):
        env, example = tmp_env(
            env_content=("DB_URL=postgres://localhost\nAPI_KEY=secret"),
            example_content="DB_URL=\nAPI_KEY=",
        )
        result = validate(env, example)
        assert result.ok
        assert len(result.missing) == 0

    def test_missing_variable(self, tmp_env):
        env, example = tmp_env(
            env_content="DB_URL=postgres://localhost",
            example_content="DB_URL=\nAPI_KEY=\nSECRET=",
        )
        result = validate(env, example)
        assert not result.ok
        assert len(result.missing) == 2
        names = {v.name for v in result.missing}
        assert names == {"API_KEY", "SECRET"}

    def test_empty_variable_warning(self, tmp_env):
        env, example = tmp_env(
            env_content=("DB_URL=postgres://localhost\nAPI_KEY="),
            example_content="DB_URL=\nAPI_KEY=",
        )
        result = validate(env, example, warn_empty=True)
        assert len(result.empty) == 1
        assert result.empty[0].name == "API_KEY"

    def test_empty_warning_disabled(self, tmp_env):
        env, example = tmp_env(
            env_content=("DB_URL=postgres://localhost\nAPI_KEY="),
            example_content="DB_URL=\nAPI_KEY=",
        )
        result = validate(env, example, warn_empty=False)
        assert len(result.empty) == 0
        assert result.ok

    def test_extra_variables(self, tmp_env):
        env, example = tmp_env(
            env_content=("DB_URL=postgres://localhost\nEXTRA_VAR=hello"),
            example_content="DB_URL=",
        )
        result = validate(env, example, show_extra=True)
        assert result.ok
        assert len(result.extra) == 1
        assert result.extra[0].name == "EXTRA_VAR"

    def test_extra_not_shown_by_default(self, tmp_env):
        env, example = tmp_env(
            env_content=("DB_URL=postgres://localhost\nEXTRA_VAR=hello"),
            example_content="DB_URL=",
        )
        result = validate(env, example)
        assert len(result.extra) == 0

    def test_default_values_detected(self, tmp_env):
        env, example = tmp_env(
            env_content="DB_URL=postgres://localhost",
            example_content=("DB_URL=postgres://localhost:5432/mydb"),
        )
        result = validate(env, example)
        assert result.vars[0].has_default
        assert result.vars[0].default_value == "postgres://localhost:5432/mydb"

    def test_json_output(self, tmp_env):
        env, example = tmp_env(
            env_content="DB_URL=postgres://localhost",
            example_content="DB_URL=\nAPI_KEY=",
        )
        result = validate(env, example)
        data = result.to_dict()
        assert data["ok"] is False
        assert "API_KEY" in data["missing"]

    def test_empty_example_file(self, tmp_env):
        env, example = tmp_env(
            env_content="DB_URL=postgres://localhost",
            example_content="",
        )
        result = validate(env, example)
        assert result.ok
        assert len(result.vars) == 0


class TestOptionalVars:
    def test_optional_missing_is_ok(self, tmp_env):
        env, example = tmp_env(
            env_content="DB_URL=postgres://localhost",
            example_content="DB_URL=\nSENTRY_DSN= # optional",
        )
        result = validate(env, example)
        assert result.ok
        assert any(
            v.name == "SENTRY_DSN" and v.status == Status.OPTIONAL for v in result.vars
        )

    def test_optional_present_is_ok(self, tmp_env):
        env, example = tmp_env(
            env_content="DB_URL=postgres://localhost\nSENTRY_DSN=https://sentry.io",
            example_content="DB_URL=\nSENTRY_DSN= # optional",
        )
        result = validate(env, example)
        assert result.ok
        sentry = next(v for v in result.vars if v.name == "SENTRY_DSN")
        assert sentry.status == Status.OK
        assert sentry.is_optional

    def test_optional_case_insensitive(self, tmp_env):
        env, example = tmp_env(
            env_content="DB_URL=value",
            example_content="DB_URL=\nDEBUG= # OPTIONAL",
        )
        result = validate(env, example)
        assert result.ok

    def test_optional_with_default(self, tmp_env):
        env, example = tmp_env(
            env_content="DB_URL=value",
            example_content="DB_URL=\nLOG_LEVEL=info # optional",
        )
        result = validate(env, example)
        assert result.ok
        log_var = next(v for v in result.vars if v.name == "LOG_LEVEL")
        assert log_var.status == Status.OPTIONAL
        assert log_var.has_default
        assert log_var.default_value == "info"

    def test_required_still_fails(self, tmp_env):
        env, example = tmp_env(
            env_content="",
            example_content="DB_URL=\nSENTRY_DSN= # optional",
        )
        result = validate(env, example)
        assert not result.ok
        assert len(result.missing) == 1
        assert result.missing[0].name == "DB_URL"


class TestCheckEnv:
    def test_missing_found_in_environ(self, tmp_env, monkeypatch):
        monkeypatch.setenv("API_KEY", "from-env")
        env, example = tmp_env(
            env_content="DB_URL=postgres://localhost",
            example_content="DB_URL=\nAPI_KEY=",
        )
        result = validate(env, example, check_env=True)
        assert result.ok
        api_var = next(v for v in result.vars if v.name == "API_KEY")
        assert api_var.status == Status.ENV
        assert api_var.source == "os.environ"

    def test_missing_not_in_environ(self, tmp_env, monkeypatch):
        monkeypatch.delenv("API_KEY", raising=False)
        env, example = tmp_env(
            env_content="DB_URL=postgres://localhost",
            example_content="DB_URL=\nAPI_KEY=",
        )
        result = validate(env, example, check_env=True)
        assert not result.ok
        assert len(result.missing) == 1

    def test_check_env_disabled_by_default(self, tmp_env, monkeypatch):
        monkeypatch.setenv("API_KEY", "from-env")
        env, example = tmp_env(
            env_content="DB_URL=postgres://localhost",
            example_content="DB_URL=\nAPI_KEY=",
        )
        result = validate(env, example)
        assert not result.ok
        assert len(result.missing) == 1

    def test_check_env_with_optional(self, tmp_env, monkeypatch):
        monkeypatch.delenv("SENTRY_DSN", raising=False)
        monkeypatch.setenv("API_KEY", "from-env")
        env, example = tmp_env(
            env_content="DB_URL=value",
            example_content="DB_URL=\nAPI_KEY=\nSENTRY_DSN= # optional",
        )
        result = validate(env, example, check_env=True)
        assert result.ok
        api = next(v for v in result.vars if v.name == "API_KEY")
        sentry = next(v for v in result.vars if v.name == "SENTRY_DSN")
        assert api.status == Status.ENV
        assert sentry.status == Status.OPTIONAL
