import json

from core import config as config_module


def _point_config_at(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "cfg"
    cfg_file = cfg_dir / "config.json"
    monkeypatch.setattr(config_module, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config_module, "CONFIG_FILE", cfg_file)
    return cfg_file


def test_save_config_is_atomic_and_loadable(tmp_path, monkeypatch):
    cfg_file = _point_config_at(tmp_path, monkeypatch)

    config_module.save_config({"api_key": "secret", "base_url": "https://example.test/v1"})

    loaded = config_module.load_config()
    assert loaded["api_key"] == "secret"
    assert loaded["api_base_url"] == "https://example.test/v1"
    assert loaded["base_url"] == "https://example.test/v1"
    assert not cfg_file.with_suffix(".tmp").exists()


def test_corrupt_config_is_backed_up_before_defaults(tmp_path, monkeypatch):
    cfg_file = _point_config_at(tmp_path, monkeypatch)
    cfg_file.parent.mkdir(parents=True)
    cfg_file.write_text("{not valid json", encoding="utf-8")

    loaded = config_module.load_config()

    assert loaded["model"] == config_module.DEFAULT_CONFIG["model"]
    backups = list(cfg_file.parent.glob("config.corrupt-*.json"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "{not valid json"


def test_config_save_normalizes_legacy_aliases(tmp_path, monkeypatch):
    cfg_file = _point_config_at(tmp_path, monkeypatch)
    cfg = config_module.Config()
    cfg.set("base_url", "https://legacy.example/v1")
    cfg.set("vault_path", "C:/vault")
    cfg.save()

    raw = json.loads(cfg_file.read_text(encoding="utf-8"))
    assert raw["api_base_url"] == "https://legacy.example/v1"
    assert raw["base_url"] == "https://legacy.example/v1"
    assert raw["obsidian_vault_path"] == "C:/vault"
    assert raw["vault_path"] == "C:/vault"
