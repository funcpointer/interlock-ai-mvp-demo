from pathlib import Path

from interlock_mvp.core import env


def test_load_env_file_accepts_shell_export(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("export OPENAI_API_KEY='test-key'\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    loaded = env.load_env_file(env_file)

    assert loaded == ["OPENAI_API_KEY"]
    assert env.os.environ["OPENAI_API_KEY"] == "test-key"


def test_load_key_files_accepts_shell_export_key_file(tmp_path: Path, monkeypatch) -> None:
    key_file = tmp_path / ".openai.key"
    key_file.write_text('export OPENAI_API_KEY="test-key"\n', encoding="utf-8")
    monkeypatch.setattr(env, "DEFAULT_OPENAI_KEY_FILE", key_file)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    loaded = env.load_key_files()

    assert loaded == ["OPENAI_API_KEY"]
    assert env.os.environ["OPENAI_API_KEY"] == "test-key"

