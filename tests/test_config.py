from pathlib import Path

import pytest

from xui_intelligence.config import load_config


def test_load_config(tmp_path: Path) -> None:
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
