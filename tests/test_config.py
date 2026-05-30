"""Tests for Config class."""

import json
import os
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from pr_insight.config import Config, DEFAULTS, SUPPORTED_MODELS


class TestConfig:
    """Tests for Config class priority and behavior."""

    def _make_config(self, env_vars=None, file_config=None):
        """Create a Config instance with controlled environment."""
        with patch("pr_insight.config.load_dotenv"):
            with patch("pr_insight.config._load_config_file", return_value=file_config or {}):
                with patch.dict(os.environ, env_vars or {}, clear=True):
                    cfg = Config()
                    return cfg

    def test_default_values(self):
        cfg = self._make_config()
        assert cfg.model == DEFAULTS["model"]
        assert cfg.language == DEFAULTS["language"]
        assert cfg.risk_level == DEFAULTS["risk_level"]

    def test_env_var_overrides_default(self):
        cfg = self._make_config(env_vars={"PR_INSIGHT_MODEL": "deepseek-chat"})
        assert cfg.model == "deepseek-chat"

    def test_file_config_overrides_default(self):
        cfg = self._make_config(file_config={"model": "mimo"})
        assert cfg.model == "mimo"

    def test_env_var_overrides_file_config(self):
        cfg = self._make_config(
            env_vars={"PR_INSIGHT_MODEL": "deepseek-chat"},
            file_config={"model": "mimo"},
        )
        assert cfg.model == "deepseek-chat"

    def test_github_token_raises_when_missing(self):
        cfg = self._make_config()
        with pytest.raises(ValueError, match="GitHub token not configured"):
            _ = cfg.github_token

    def test_anthropic_key_raises_when_missing(self):
        cfg = self._make_config()
        with pytest.raises(ValueError, match="API key not configured"):
            _ = cfg.anthropic_key

    def test_base_url_empty_by_default(self):
        cfg = self._make_config()
        assert cfg.base_url == ""

    def test_base_url_from_env(self):
        cfg = self._make_config(env_vars={"PR_INSIGHT_BASE_URL": "https://custom.api.com"})
        assert cfg.base_url == "https://custom.api.com"

    def test_show_masks_sensitive_keys(self):
        cfg = self._make_config(file_config={
            "github_token": "ghp_1234567890abcdef",
            "anthropic_key": "sk-ant-12345678",
        })
        shown = cfg.show()
        assert shown["github_token"].startswith("ghp_1234")
        assert shown["anthropic_key"].startswith("sk-ant-1")

    def test_set_saves_to_file_config(self):
        cfg = self._make_config()
        cfg.set("model", "deepseek-chat")
        assert cfg._file_config["model"] == "deepseek-chat"

    def test_supported_models_not_empty(self):
        assert len(SUPPORTED_MODELS) > 0
        assert "claude-sonnet-4-20250514" in SUPPORTED_MODELS

    def test_unset_existing_key(self):
        cfg = self._make_config(file_config={"model": "mimo"})
        assert cfg.unset("model") is True
        assert "model" not in cfg._file_config

    def test_unset_nonexistent_key(self):
        cfg = self._make_config()
        assert cfg.unset("nonexistent") is False
