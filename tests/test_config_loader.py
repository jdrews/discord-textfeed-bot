"""Unit tests for config_loader module."""

import json
import os
import tempfile
from pathlib import Path
import pytest

from src.config_loader import ConfigLoader, ConfigData, load_config


class TestConfigLoader:
    """Test cases for ConfigLoader class."""

    def test_load_valid_yaml(self):
        """Test loading a valid YAML configuration file."""
        with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as f:
            f.write(b"""
discord:
  channel_id: "123456789"
source:
  file_path: "./test.txt"
""")
            temp_path = f.name

        try:
            loader = ConfigLoader(temp_path)
            config = loader.load()

            assert isinstance(config, ConfigData)
            assert config.discord_channel_id == 123456789
            assert str(config.source_file_path) in ("./test.txt", "test.txt")
        finally:
            os.unlink(temp_path)

    def test_load_valid_json(self):
        """Test loading a valid JSON configuration file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "discord": {"channel_id": 987654321},
                "source": {"file_path": "./test.txt"}
            }, f)
            temp_path = f.name

        try:
            loader = ConfigLoader(temp_path)
            config = loader.load()

            assert isinstance(config, ConfigData)
            assert config.discord_channel_id == 987654321
            assert str(config.source_file_path) in ("./test.txt", "test.txt")
        finally:
            os.unlink(temp_path)

    def test_load_missing_required_field_discord_channel_id(self):
        """Test that loading fails when discord.channel_id is missing."""
        with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as f:
            f.write(b"""
source:
  file_path: "./test.txt"
""")
            temp_path = f.name

        try:
            loader = ConfigLoader(temp_path)
            with pytest.raises(ValueError, match="Missing required configuration field"):
                loader.load()
        finally:
            os.unlink(temp_path)

    def test_load_missing_required_field_source_file_path(self):
        """Test that loading fails when source.file_path is missing."""
        with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as f:
            f.write(b"""
discord:
  channel_id: "123456789"
""")
            temp_path = f.name

        try:
            loader = ConfigLoader(temp_path)
            with pytest.raises(ValueError, match="Missing required configuration field"):
                loader.load()
        finally:
            os.unlink(temp_path)

    def test_load_invalid_channel_id_type(self):
        """Test that loading fails when channel_id is not an integer."""
        with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as f:
            f.write(b"""
discord:
  channel_id: "not_a_number"
source:
  file_path: "./test.txt"
""")
            temp_path = f.name

        try:
            loader = ConfigLoader(temp_path)
            with pytest.raises(ValueError, match="Invalid value for 'channel_id'"):
                loader.load()
        finally:
            os.unlink(temp_path)

    def test_load_invalid_start_line(self):
        """Test that loading fails when start_line is negative."""
        with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as f:
            f.write(b"""
discord:
  channel_id: "123456789"
source:
  file_path: "./test.txt"
  start_line: -5
""")
            temp_path = f.name

        try:
            loader = ConfigLoader(temp_path)
            with pytest.raises(ValueError, match="Invalid start_line"):
                loader.load()
        finally:
            os.unlink(temp_path)

    def test_load_invalid_log_level(self):
        """Test that loading fails when log_level is invalid."""
        with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as f:
            f.write(b"""
discord:
  channel_id: "123456789"
source:
  file_path: "./test.txt"
logging:
  level: "INVALID_LEVEL"
""")
            temp_path = f.name

        try:
            loader = ConfigLoader(temp_path)
            with pytest.raises(ValueError, match="Invalid log_level"):
                loader.load()
        finally:
            os.unlink(temp_path)

    def test_load_file_not_found(self):
        """Test that loading fails when config file doesn't exist."""
        loader = ConfigLoader("/nonexistent/config.yaml")
        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            loader.load()

    def test_load_unsupported_format(self):
        """Test that loading fails for unsupported file formats."""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            f.write(b"not yaml or json")
            temp_path = f.name

        try:
            loader = ConfigLoader(temp_path)
            with pytest.raises(TypeError, match="Unsupported configuration file format"):
                loader.load()
        finally:
            os.unlink(temp_path)

    def test_load_empty_file(self):
        """Test that loading fails for empty config files."""
        with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as f:
            f.write(b"")
            temp_path = f.name

        try:
            loader = ConfigLoader(temp_path)
            with pytest.raises(ValueError, match="Configuration file is empty"):
                loader.load()
        finally:
            os.unlink(temp_path)


class TestConfigDataDefaults:
    """Test cases for default values in ConfigData."""

    def test_default_start_line(self):
        """Test that start_line defaults to 1."""
        config = ConfigData(
            discord_channel_id=123,
            source_file_path=Path("/test.txt")
        )
        assert config.start_line == 1

    def test_default_injection_mode(self):
        """Test that injection_mode defaults to 'line'."""
        config = ConfigData(
            discord_channel_id=123,
            source_file_path=Path("/test.txt")
        )
        assert config.injection_mode == "line"

    def test_default_interval_seconds(self):
        """Test that interval_seconds defaults to 180."""
        config = ConfigData(
            discord_channel_id=123,
            source_file_path=Path("/test.txt")
        )
        assert config.interval_seconds == 180

    def test_default_randomization_seconds(self):
        """Test that randomization_seconds defaults to 0."""
        config = ConfigData(
            discord_channel_id=123,
            source_file_path=Path("/test.txt")
        )
        assert config.randomization_seconds == 0


class TestGetDiscordToken:
    """Test cases for get_discord_token function."""

    def test_get_token_from_env(self):
        """Test getting token from environment variable."""
        os.environ["DISCORD_TOKEN"] = "test_token_123"
        try:
            token = ConfigLoader("config.yaml").get_discord_token()
            assert token == "test_token_123"
        finally:
            del os.environ["DISCORD_TOKEN"]

    def test_get_token_missing_env(self):
        """Test that getting token fails when env var is not set."""
        if "DISCORD_TOKEN" in os.environ:
            del os.environ["DISCORD_TOKEN"]
        
        with pytest.raises(ValueError, match="DISCORD_TOKEN environment variable must be set"):
            ConfigLoader("config.yaml").get_discord_token()


class TestConfigGetterMethods:
    """Test cases for getter methods."""

    def test_getters_after_load(self):
        """Test that all getters work after successful load."""
        books_dir = Path("./books")
        books_created = False
        if not books_dir.exists():
            books_dir.mkdir()
            books_created = True
        test_file = books_dir / "test.txt"
        test_file.touch()

        with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as f:
            f.write(b"""
discord:
  channel_id: "987654321"
source:
  file_path: "./books/test.txt"
  start_line: 50
schedule:
  interval_seconds: 300
  randomization_seconds: 60
logging:
  level: "INFO"
  file: "./logs/app.log"
""")
            temp_path = f.name

        try:
            loader = ConfigLoader(temp_path)
            loader.load()

            assert loader.get_channel_id() == 987654321
            assert str(loader.get_source_file_path()) in ("./books/test.txt", "books/test.txt")
            assert loader.get_start_line() == 50
            assert loader.get_interval_seconds() == 300
            assert loader.get_randomization_seconds() == 60
            assert loader.get_log_level() == "INFO"
            assert loader.get_log_file() == "./logs/app.log"
        finally:
            os.unlink(temp_path)
            if test_file.exists():
                test_file.unlink()
            if books_created and books_dir.exists():
                books_dir.rmdir()

    def test_getters_before_load_raise_error(self):
        """Test that getters raise RuntimeError before load()."""
        with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as f:
            f.write(b"""
discord:
  channel_id: "123456789"
source:
  file_path: "./test.txt"
""")
            temp_path = f.name

        try:
            loader = ConfigLoader(temp_path)
            with pytest.raises(RuntimeError, match="Configuration not loaded"):
                loader.get_channel_id()
        finally:
            os.unlink(temp_path)
