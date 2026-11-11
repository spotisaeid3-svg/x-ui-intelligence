from pathlib import Path

import pytest

from xui_intelligence.config import load_config


def test_load_config(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("XUI_INTELLIGENCE_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("XUI_INTELLIGENCE_TELEGRAM_ALLOWED_IDS", raising=False)
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[app]\npoll_interval_seconds = 10\nretention_days = 14\n'
        'database_path = "/tmp/monitor.sqlite3"\n',
        encoding="utf-8",
    )
    config = load_config(config_file)
    assert config.poll_interval_seconds == 10
    assert config.retention_days == 14
    assert config.database_path == Path("/tmp/monitor.sqlite3")
    assert config.telegram_enabled is False


def test_reject_relative_database_path(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text('[app]\ndatabase_path = "relative.db"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="absolute"):
        load_config(config_file)


def test_default_snapshot_path_is_outside_app_writable_state(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text("[xui_database]\nenabled = false\n", encoding="utf-8")
    config = load_config(config_file)
    assert config.xui_snapshot_path == Path(
        "/var/lib/xui-intelligence-snapshot/xui-readonly.sqlite3"
    )


def test_telegram_requires_token_and_allowlist(tmp_path: Path, monkeypatch) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text('[telegram]\nenabled = true\nallowed_user_ids = [12345]\n', encoding="utf-8")
    monkeypatch.delenv("XUI_INTELLIGENCE_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("XUI_INTELLIGENCE_TELEGRAM_ALLOWED_IDS", raising=False)
    with pytest.raises(ValueError, match="BOT_TOKEN"):
        load_config(config_file)


def test_telegram_environment_allowlist_overrides_toml(tmp_path: Path, monkeypatch) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text('[telegram]\nenabled = true\nallowed_user_ids = [111]\n', encoding="utf-8")
    monkeypatch.setenv("XUI_INTELLIGENCE_TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("XUI_INTELLIGENCE_TELEGRAM_ALLOWED_IDS", "222,333")
    config = load_config(config_file)
    assert config.telegram_enabled is True
    assert config.telegram_allowed_user_ids == frozenset({222, 333})
    assert config.telegram_bot_token == "test-token"


def test_telegram_rejects_empty_allowlist(tmp_path: Path, monkeypatch) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text('[telegram]\nenabled = true\nallowed_user_ids = []\n', encoding="utf-8")
    monkeypatch.setenv("XUI_INTELLIGENCE_TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.delenv("XUI_INTELLIGENCE_TELEGRAM_ALLOWED_IDS", raising=False)
    with pytest.raises(ValueError, match="no authorized IDs"):
        load_config(config_file)


def test_reject_string_boolean_for_security_switches(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text('[telegram]\nenabled = "false"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="TOML boolean"):
        load_config(config_file)
