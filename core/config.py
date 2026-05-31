"""
config.py - 앱 설정 영속화 모듈
API 키, Obsidian 볼트 경로, 모델 설정을 JSON 파일로 저장/로드
"""

import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".econometric_wiki"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "api_key": "",
    "api_base_url": "https://api.openai.com/v1",
    "model": "gpt-4o",
    "obsidian_vault_path": "",
    "obsidian_subfolder": "Papers",
    "auto_sync": True,
    "existing_concepts": [],
    "zotero_link_prefix": "zotero://select/library/items/",
    "use_topic_folders": True,
    "llm_classify_fallback": True,
    "classification_rules": {},
    "custom_topics": [],
}


def load_config() -> dict:
    """설정 파일 로드. 없으면 기본값 반환."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 기본값에 없는 키 병합
            merged = {**DEFAULT_CONFIG, **data}
            return merged
        except (json.JSONDecodeError, IOError):
            return dict(DEFAULT_CONFIG)
    return dict(DEFAULT_CONFIG)


def save_config(config: dict) -> None:
    """설정 파일 저장."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_config_path() -> str:
    return str(CONFIG_FILE)


class Config:
    """dict-like 설정 래퍼 클래스. main_window.py와 호환."""

    def __init__(self):
        self._data = load_config()

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def __contains__(self, key):
        return key in self._data

    def save(self):
        # base_url 동기화
        if "base_url" in self._data and "api_base_url" not in self._data:
            self._data["api_base_url"] = self._data["base_url"]
        if "api_base_url" in self._data and "base_url" not in self._data:
            self._data["base_url"] = self._data["api_base_url"]
        # vault_path 동기화
        if "vault_path" in self._data and "obsidian_vault_path" not in self._data:
            self._data["obsidian_vault_path"] = self._data["vault_path"]
        if "obsidian_vault_path" in self._data and "vault_path" not in self._data:
            self._data["vault_path"] = self._data["obsidian_vault_path"]
        save_config(self._data)

    def reload(self):
        self._data = load_config()
