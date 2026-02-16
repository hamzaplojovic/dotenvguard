"""Tests for dotenvguard core logic."""

from __future__ import annotations

from pathlib import Path

import pytest

from dotenvguard.core import Status, parse_env_file, parse_example_file, validate


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

    def test_optional_missing_var_is_ok(self, tmp_env):
        env, example = tmp_env(
            env_content="DB_URL=postgres://localhost",
            example_content="DB_URL=\nDEBUG=true  # optional",
        )
        result = validate(env, example)
        assert result.ok
        assert len(result.missing) == 0
        debug_var = next(v for v in result.vars if v.name == "DEBUG")
        assert debug_var.status == Status.OPTIONAL
        assert debug_var.optional is True
        assert debug_var.has_default is True
        assert debug_var.default_value == "true"

    def test_optional_present_var_is_ok(self, tmp_env):
        env, example = tmp_env(
            env_content="DB_URL=postgres://localhost\nDEBUG=false",
            example_content="DB_URL=\nDEBUG=true  # optional",
        )
        result = validate(env, example)
        assert result.ok
        debug_var = next(v for v in result.vars if v.name == "DEBUG")
        assert debug_var.status == Status.OK
        assert debug_var.optional is True

    def test_optional_does_not_affect_required_vars(self, tmp_env):
        env, example = tmp_env(
            env_content="DEBUG=false",
            example_content="DB_URL=\nDEBUG=true  # optional",
        )
        result = validate(env, example)
        assert not result.ok
        assert len(result.missing) == 1
        assert result.missing[0].name == "DB_URL"

    def test_optional_case_insensitive(self, tmp_env):
        env, example = tmp_env(
            env_content="DB_URL=x",
            example_content="DB_URL=\nDEBUG=true  # Optional\nLOG=info  # OPTIONAL",
        )
        result = validate(env, example)
        assert result.ok

    def test_optional_in_json_output(self, tmp_env):
        env, example = tmp_env(
            env_content="DB_URL=postgres://localhost",
            example_content="DB_URL=\nDEBUG=true  # optional",
        )
        result = validate(env, example)
        data = result.to_dict()
        assert data["ok"] is True
        debug_entry = next(v for v in data["variables"] if v["name"] == "DEBUG")
        assert debug_entry["optional"] is True
        assert debug_entry["status"] == "optional"

    def test_multiple_optional_vars(self, tmp_env):
        env, example = tmp_env(
            env_content="SECRET_KEY=abc",
            example_content=(
                "SECRET_KEY=\n"
                "DEBUG=true  # optional\n"
                "LOG_LEVEL=info  # optional\n"
                "CACHE_TTL=3600  # optional\n"
            ),
        )
        result = validate(env, example)
        assert result.ok
        optional_vars = [v for v in result.vars if v.optional]
        assert len(optional_vars) == 3


class TestParseExampleFile:
    def test_detects_optional_annotation(self, tmp_path: Path):
        f = tmp_path / ".env.example"
        f.write_text("DB_URL=\nDEBUG=true  # optional\nSECRET=")
        vars_dict, optional_names = parse_example_file(f)
        assert "DEBUG" in optional_names
        assert "DB_URL" not in optional_names
        assert "SECRET" not in optional_names
        assert vars_dict["DEBUG"] == "true"

    def test_optional_with_no_default(self, tmp_path: Path):
        f = tmp_path / ".env.example"
        f.write_text("DEBUG=  # optional")
        vars_dict, optional_names = parse_example_file(f)
        assert "DEBUG" in optional_names
        assert vars_dict["DEBUG"] == ""

    def test_no_optional_annotations(self, tmp_path: Path):
        f = tmp_path / ".env.example"
        f.write_text("DB_URL=\nAPI_KEY=")
        vars_dict, optional_names = parse_example_file(f)
        assert len(optional_names) == 0

    def test_nonexistent_file(self, tmp_path: Path):
        f = tmp_path / "nope"
        vars_dict, optional_names = parse_example_file(f)
        assert vars_dict == {}
        assert optional_names == set()
