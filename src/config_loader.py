"""Configuration management for Discord Text Feed Bot."""

import os
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass


@dataclass
class ConfigData:
    """Container for all configuration values."""
    discord_channel_id: int
    source_file_path: Path
    skip_header: bool = True
    skip_footer: bool = True
    start_line: int = 30
    end_line: Optional[int] = None
    injection_mode: str = "line"
    interval_seconds: int = 180
    randomization_seconds: int = 0
    log_level: str = "DEBUG"
    log_file: str = "./logs/debug.log"


class ConfigLoader:
    """Load and validate configuration from YAML/JSON files with environment variable support."""

    REQUIRED_FIELDS = ["discord.channel_id", "source.file_path"]
    VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")

    def __init__(self, path: str):
        """Initialize with configuration file path.

        Args:
            path: Path to YAML or JSON configuration file.
        """
        self.path = Path(path)
        self._config: Dict[str, Any] = {}
        self._validated_config: Optional[ConfigData] = None

    def load(self) -> ConfigData:
        """Load and validate configuration from file.

        Returns:
            Validated ConfigData object with all values.

        Raises:
            FileNotFoundError: If config file does not exist.
            ValueError: If required fields are missing or invalid.
            TypeError: If config format is invalid (not YAML/JSON).
        """
        if not self.path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.path}")

        # Determine file type and load accordingly
        suffix = self.path.suffix.lower()
        if suffix == ".yaml" or suffix == ".yml":
            import yaml
            with open(self.path, "r", encoding="utf-8") as f:
                raw_config = yaml.safe_load(f)
        elif suffix == ".json":
            import json
            with open(self.path, "r", encoding="utf-8") as f:
                raw_config = json.load(f)
        else:
            raise TypeError(
                f"Unsupported configuration file format: {suffix}. "
                "Use YAML (.yaml/.yml) or JSON (.json)."
            )

        if raw_config is None:
            raise ValueError("Configuration file is empty.")

        self._config = raw_config
        self._validated_config = self._validate_and_parse()

        return self._validated_config

    def _validate_and_parse(self) -> ConfigData:
        """Validate required fields and parse configuration values.

        Returns:
            Parsed ConfigData object.

        Raises:
            ValueError: If validation fails.
        """
        # Validate required fields exist
        for field in self.REQUIRED_FIELDS:
            parts = field.split('.')
            curr = self._config
            for part in parts:
                if not isinstance(curr, dict) or part not in curr:
                    raise ValueError(f"Missing required configuration field: {field}")
                curr = curr[part]

        discord_config = self._config.get("discord") or {}
        source_config = self._config.get("source") or {}
        schedule_config = self._config.get("schedule") or {}
        logging_config = self._config.get("logging") or {}

        # Parse and validate each configuration value
        return ConfigData(
            discord_channel_id=self._parse_int(discord_config, "channel_id"),
            source_file_path=self._parse_source_file(source_config),
            skip_header=source_config.get("skip_header", True),
            skip_footer=source_config.get("skip_footer", True),
            start_line=self._parse_start_line(source_config),
            end_line=self._parse_end_line(source_config),
            injection_mode=source_config.get("injection_mode", "line"),
            interval_seconds=schedule_config.get("interval_seconds", 180),
            randomization_seconds=schedule_config.get("randomization_seconds", 0),
            log_level=self._parse_log_level(logging_config),
            log_file=logging_config.get("file", "./logs/debug.log"),
        )

    def _parse_int(self, section: Dict[str, Any], key: str) -> int:
        """Parse an integer value from configuration.

        Args:
            section: Configuration dictionary for the section.
            key: Key to look up in the section.

        Returns:
            Parsed integer value.

        Raises:
            ValueError: If value is not a valid integer or missing.
        """
        if not isinstance(section, dict) or key not in section:
            raise ValueError(f"Missing required field: {key}")

        value = section[key]
        try:
            return int(value)
        except (ValueError, TypeError):
            raise ValueError(
                f"Invalid value for '{key}': expected integer, got {type(value).__name__}"
            )

    def _parse_source_file(self, source_config: Dict[str, Any]) -> Path:
        """Parse the source file path.

        Args:
            source_config: Configuration dictionary for the source section.

        Returns:
            Path object for the source file.

        Raises:
            ValueError: If path is missing.
        """
        if "file_path" not in source_config:
            raise ValueError("Missing required field: source.file_path")

        return Path(source_config["file_path"])

    def _parse_start_line(self, source_config: Dict[str, Any]) -> int:
        """Parse the start line number.

        Args:
            source_config: Configuration dictionary for the source section.

        Returns:
            Start line number (1-based). Defaults to 30 if not specified.

        Raises:
            ValueError: If value is invalid or negative.
        """
        if "start_line" in source_config:
            start_line = int(source_config["start_line"])
            if start_line < 1:
                raise ValueError(
                    f"Invalid start_line: {start_line}. Must be >= 1."
                )
            return start_line

        # Default to line 30 (skips Project Gutenberg header)
        return 30

    def _parse_end_line(self, source_config: Dict[str, Any]) -> Optional[int]:
        """Parse the end line number.

        Args:
            source_config: Configuration dictionary for the source section.

        Returns:
            End line number or None if not specified (read to end).
        """
        if "end_line" in source_config and source_config["end_line"] is not None:
            return int(source_config["end_line"])

        return None

    def _parse_log_level(self, logging_config: Dict[str, Any]) -> str:
        """Parse and validate the log level.

        Args:
            logging_config: Configuration dictionary for the logging section.

        Returns:
            Validated log level string.

        Raises:
            ValueError: If log level is invalid.
        """
        if "level" in logging_config:
            level = str(logging_config["level"]).upper()
            if level not in self.VALID_LOG_LEVELS:
                raise ValueError(
                    f"Invalid log_level: {logging_config['level']}. "
                    f"Must be one of: {', '.join(self.VALID_LOG_LEVELS)}"
                )
            return level

        # Default to DEBUG
        return "DEBUG"

    def get_discord_token(self) -> str:
        """Get Discord token from environment variable.

        The token must be provided via the DISCORD_TOKEN environment variable.
        It is never stored in the configuration file for security reasons.

        Returns:
            Discord bot token string.

        Raises:
            ValueError: If DISCORD_TOKEN environment variable is not set.
        """
        token = os.environ.get("DISCORD_TOKEN")
        if not token:
            raise ValueError(
                "DISCORD_TOKEN environment variable must be set. "
                "The Discord token cannot be stored in the configuration file."
            )
        return token

    def get_channel_id(self) -> int:
        """Get target channel ID from validated config.

        Returns:
            Target Discord channel ID as integer.

        Raises:
            RuntimeError: If configuration has not been loaded.
        """
        self._ensure_loaded()
        return self._validated_config.discord_channel_id

    def get_source_file_path(self) -> Path:
        """Get path to source text file from validated config.

        Returns:
            Path object pointing to the source text file.

        Raises:
            RuntimeError: If configuration has not been loaded.
            FileNotFoundError: If the source file does not exist.
        """
        self._ensure_loaded()
        file_path = self._validated_config.source_file_path
        if not file_path.exists():
            raise FileNotFoundError(f"Source file does not exist: {file_path}")
        return file_path

    def get_skip_header(self) -> bool:
        """Get header skip setting from validated config.

        Returns:
            True to skip Project Gutenberg header sections, False otherwise.

        Raises:
            RuntimeError: If configuration has not been loaded.
        """
        self._ensure_loaded()
        return self._validated_config.skip_header

    def get_skip_footer(self) -> bool:
        """Get footer skip setting from validated config.

        Returns:
            True to skip Project Gutenberg footer markers, False otherwise.

        Raises:
            RuntimeError: If configuration has not been loaded.
        """
        self._ensure_loaded()
        return self._validated_config.skip_footer

    def get_start_line(self) -> int:
        """Get start line number from validated config.

        Returns:
            Start reading from this 1-based line number.

        Raises:
            RuntimeError: If configuration has not been loaded.
        """
        self._ensure_loaded()
        return self._validated_config.start_line

    def get_end_line(self) -> Optional[int]:
        """Get end line number from validated config.

        Returns:
            Stop reading at this 1-based line number, or None to read to end.

        Raises:
            RuntimeError: If configuration has not been loaded.
        """
        self._ensure_loaded()
        return self._validated_config.end_line

    def get_injection_mode(self) -> str:
        """Get injection mode from validated config.

        Returns:
            Injection mode string: "line", "paragraph", or "character_scene".

        Raises:
            RuntimeError: If configuration has not been loaded.
        """
        self._ensure_loaded()
        return self._validated_config.injection_mode

    def get_interval_seconds(self) -> int:
        """Get injection interval in seconds from validated config.

        Returns:
            Base seconds between injections (e.g., 180 = 3 minutes).

        Raises:
            RuntimeError: If configuration has not been loaded.
        """
        self._ensure_loaded()
        return self._validated_config.interval_seconds

    def get_randomization_seconds(self) -> int:
        """Get scheduling randomization from validated config.

        Returns:
            ± variance in seconds (0 = exact timing).

        Raises:
            RuntimeError: If configuration has not been loaded.
        """
        self._ensure_loaded()
        return self._validated_config.randomization_seconds

    def get_log_level(self) -> str:
        """Get logging level from validated config.

        Returns:
            Logging level string (DEBUG/INFO/WARNING/ERROR).

        Raises:
            RuntimeError: If configuration has not been loaded.
        """
        self._ensure_loaded()
        return self._validated_config.log_level

    def get_log_file(self) -> str:
        """Get log file path from validated config.

        Returns:
            Path string for the debug log file.

        Raises:
            RuntimeError: If configuration has not been loaded.
        """
        self._ensure_loaded()
        return self._validated_config.log_file

    def _ensure_loaded(self) -> None:
        """Ensure configuration has been loaded.

        Raises:
            RuntimeError: If configuration has not been loaded.
        """
        if self._validated_config is None:
            raise RuntimeError("Configuration not loaded. Call load() first.")


def load_config(path: str) -> ConfigData:
    """Load and validate configuration from file.

    Args:
        path: Path to YAML or JSON configuration file.

    Returns:
        Validated ConfigData object with all values.

    Raises:
        FileNotFoundError: If config file does not exist.
        ValueError: If required fields are missing or invalid.
        TypeError: If config format is invalid (not YAML/JSON).
    """
    loader = ConfigLoader(path)
    return loader.load()


def get_discord_token() -> str:
    """Get Discord token from environment variable.

    Returns:
        Discord bot token string.

    Raises:
        ValueError: If DISCORD_TOKEN environment variable is not set.
    """
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise ValueError(
            "DISCORD_TOKEN environment variable must be set. "
            "The Discord token cannot be stored in the configuration file."
        )
    return token


def get_channel_id() -> int:
    """Get target channel ID from configuration.

    Returns:
        Target Discord channel ID as integer.
    """
    return ConfigLoader("config.yaml").get_channel_id()


def get_source_file_path() -> Path:
    """Get path to source text file from configuration.

    Returns:
        Path object pointing to the source text file.
    """
    return ConfigLoader("config.yaml").get_source_file_path()


def get_interval_seconds() -> int:
    """Get injection interval in seconds from configuration.

    Returns:
        Base seconds between injections.
    """
    return ConfigLoader("config.yaml").get_interval_seconds()
