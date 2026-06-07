#!/usr/bin/env python3
"""Test script to preview the next messages that will be sent to Discord."""

import yaml
from pathlib import Path
from src.file_reader import FileReader


def load_config():
    """Load configuration from config.test.yaml."""
    config_path = Path("config.test.yaml")
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    # Load configuration
    config = load_config()
    
    source_path = Path(config["source"]["file_path"])
    
    if not source_path.exists():
        print(f"Source file not found: {source_path}")
        print("Please ensure the file exists at the specified path.")
        return
    
    # Read and group content using character_scene mode (from config)
    reader = FileReader(source_path)
    lines = reader.read(
        start_line=config["source"]["start_line"],
        end_line=config["source"]["end_line"],
    )
    
    injection_mode = config["source"]["injection_mode"]
    content_units = reader.group_by_injection_mode(lines, injection_mode)
    
    print(f"Total content units: {len(content_units)}")
    print("\nFirst 10 messages to send:")
    print("=" * 80)
    
    for i, unit in enumerate(content_units[:10]):
        print(f"\n--- Message {i + 1} ---")
        print(unit)


if __name__ == "__main__":
    main()
