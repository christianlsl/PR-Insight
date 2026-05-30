"""Configuration management for PR-Insight."""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

CONFIG_DIR = Path.home() / ".pr-insight"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Supported models (all via Anthropic-compatible API)
SUPPORTED_MODELS = {
    "claude-sonnet-4-20250514": "Claude Sonnet 4 (Anthropic 官方)",
    "claude-3-5-sonnet-20241022": "Claude 3.5 Sonnet (Anthropic 官方)",
    "deepseek-chat": "DeepSeek Chat (通过 Anthropic 接口)",
    "deepseek-coder": "DeepSeek Coder (通过 Anthropic 接口)",
    "mimo": "Mimo (通过 Anthropic 接口)",
}

DEFAULTS = {
    "model": "claude-sonnet-4-20250514",
    "base_url": "",  # 自定义 API base URL，为空则使用 Anthropic 官方
    "language": "zh",
    "risk_level": "low",
    "output": "terminal",
    "focus": "all",
}


def _ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _load_config_file() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    return {}


def _save_config_file(data: dict) -> None:
    _ensure_config_dir()
    CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


class Config:
    """Manages configuration from env vars, config file, and defaults."""

    def __init__(self) -> None:
        load_dotenv()
        self._file_config = _load_config_file()
        self._env = dict(os.environ)

    def get(self, key: str, default: str | None = None) -> str | None:
        # Priority: env var > config file > default param > built-in default
        env_key = f"PR_INSIGHT_{key.upper()}"
        env_val = self._env.get(env_key) or self._env.get(key.upper())
        if env_val:
            return env_val
        file_val = self._file_config.get(key)
        if file_val:
            return file_val
        return default or DEFAULTS.get(key)

    @property
    def github_token(self) -> str:
        token = self.get("github_token")
        if not token:
            raise ValueError(
                "GitHub token not configured. "
                "Set GITHUB_TOKEN env var or run: pr-insight config set github_token <token>"
            )
        return token

    @property
    def anthropic_key(self) -> str:
        key = self.get("anthropic_key") or self.get("API_KEY")
        if not key:
            raise ValueError(
                "API key not configured. "
                "Set API_KEY env var or run: pr-insight config set anthropic_key <key>"
            )
        return key

    @property
    def model(self) -> str:
        return self.get("model") or DEFAULTS["model"]

    @property
    def base_url(self) -> str:
        """Custom API base URL. Empty string means use Anthropic default."""
        return self.get("base_url") or DEFAULTS["base_url"]

    @property
    def language(self) -> str:
        return self.get("language") or DEFAULTS["language"]

    @property
    def risk_level(self) -> str:
        return self.get("risk_level") or DEFAULTS["risk_level"]

    def set(self, key: str, value: str) -> None:
        self._file_config[key] = value
        _save_config_file(self._file_config)

    def show(self) -> dict:
        """Return all effective config values (masks sensitive keys)."""
        result = dict(DEFAULTS)
        result.update(self._file_config)
        for sensitive in ("github_token", "anthropic_key"):
            val = result.get(sensitive)
            if val:
                result[sensitive] = val[:8] + "..." if len(val) > 8 else "***"
        return result
