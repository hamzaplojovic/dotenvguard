"""Tests for dotenvguard CLI."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from dotenvguard.cli import app

runner = CliRunner()


def _setup_env_files(
    tmp_path: Path,
    env_content: str = "",
    example_content: str = "",
) -> Path:
    (tmp_path / ".env").write_text(env_content)
    (tmp_path / ".env.example").write_text(example_content)
    return tmp_path


class TestCheckCommand:
    def test_all_present_exits_zero(self, tmp_path: Path):
        _setup_env_files(
            tmp_path,
            env_content=("DB_URL=postgres://localhost\nAPI_KEY=secret"),
            example_content="DB_URL=\nAPI_KEY=",
        )
        result = runner.invoke(app, ["check", str(tmp_path)])
        assert result.exit_code == 0

    def test_missing_variable_exits_one(self, tmp_path: Path):
        _setup_env_files(
            tmp_path,
            env_content="DB_URL=postgres://localhost",
            example_content="DB_URL=\nAPI_KEY=\nSECRET=",
        )
        result = runner.invoke(app, ["check", str(tmp_path)])
        assert result.exit_code == 1

    def test_json_output(self, tmp_path: Path):
        _setup_env_files(
            tmp_path,
            env_content="DB_URL=postgres://localhost",
            example_content="DB_URL=\nAPI_KEY=",
        )
        result = runner.invoke(app, ["check", str(tmp_path), "--json"])
        assert result.exit_code == 1
        assert '"ok": false' in result.output
        assert '"API_KEY"' in result.output

    def test_no_example_file_exits_one(self, tmp_path: Path):
        (tmp_path / ".env").write_text("KEY=value")
        result = runner.invoke(app, ["check", str(tmp_path)])
        assert result.exit_code == 1

    def test_no_env_file_exits_one(self, tmp_path: Path):
        (tmp_path / ".env.example").write_text("KEY=")
        result = runner.invoke(app, ["check", str(tmp_path)])
        assert result.exit_code == 1

    def test_extra_flag(self, tmp_path: Path):
        _setup_env_files(
            tmp_path,
            env_content=("DB_URL=postgres://localhost\nEXTRA=hello"),
            example_content="DB_URL=",
        )
        result = runner.invoke(app, ["check", str(tmp_path), "--extra"])
        assert result.exit_code == 0
        assert "EXTRA" in result.output

    def test_custom_file_paths(self, tmp_path: Path):
        env_file = tmp_path / "custom.env"
        example_file = tmp_path / "custom.example"
        env_file.write_text("KEY=value")
        example_file.write_text("KEY=")
        result = runner.invoke(
            app,
            [
                "check",
                str(tmp_path),
                "--env",
                str(env_file),
                "--example",
                str(example_file),
            ],
        )
        assert result.exit_code == 0

    def test_version_flag(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output
