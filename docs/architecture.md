# Discord Text Feed Bot - Architecture Documentation

## Overview

A Python-based Discord bot using `discord.py` that reads lines from a user-provided text file and injects them into a configurable Discord channel at a configurable rate. The primary use case is to generate test messages for another bot that summarizes daily discussions in a channel.

---

## Requirements

### Core Functionality
- **Injection Rate**: Configurable base interval with optional randomization (± seconds) specified in config file
- **Channel Configuration**: Target Discord channel ID specified in config file
- **Book Selection**: User provides a UTF-8 encoded text file containing the source content (e.g., Project Gutenberg eBooks)
- **Output Format**: Raw text lines only, no additional formatting or metadata
- **Content Filtering**: Optional skip of header/footer sections (Project Gutenberg markers, table of contents, etc.)
- **Injection Mode**: Support for different grouping strategies:
  - `line`: Inject each line individually (default)
  - `paragraph`: Group consecutive non-empty lines into paragraphs before injecting
  - `character_scene` (play mode): Group dialogue by character and stage directions separately
- **State Persistence**: Track and save the current injection position to survive bot restarts
- **Message Limits**: Ensure no injected content exceeds Discord's 2000-character limit
- **Debug Logging**: Log operational events (what actions are being performed) without logging actual content

---

## System Architecture

### Components

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│   Config File   │─────>│  Configuration   │─────>│    Bot Core     │
│   (YAML/JSON)   │      │   Loader         │      │                 │
└─────────────────┘      └──────────────────┘      └─────────────────┘
                                                          │
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│  Source Text    │─────>│   File Reader    │─────>│  Message Queue  │
│     (TXT)       │      │                  │      │                 │
└─────────────────┘      └──────────────────┘      └─────────────────┘
                                                          │
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│   Debug Logger  │<─────│    Scheduler     │<─────│  Discord Client │
│                 │      │                  │      │                 │
└─────────────────┘      └──────────────────┘      └─────────────────┘
```

### Data Flow

1. **Configuration Loading**: Bot loads configuration from file on startup
2. **Source File Reading**: Reads the provided text file and splits into lines
3. **Message Queue**: Lines are queued for injection with index tracking
4. **Scheduler**: Runs at configured intervals (with optional randomization ±N seconds), dequeues next line
5. **Discord Send**: Sends raw line to target channel
6. **State Update**: Updates local state file with the new position index
7. **Debug Logging**: Logs operational events (line number sent, success/failure)

---

## Configuration Structure

### Config File Format (YAML recommended)

```yaml
# discord-textfeed-bot.yaml
discord:
  channel_id: "123456789012345678"

source:
  file_path: "./books/test_book.txt"
  skip_header: true          # Skip Project Gutenberg header/license sections
  skip_footer: true          # Skip Project Gutenberg footer markers
  start_line: 30             # Optional: Start reading from line number (skips headers)
  end_line: null             # Optional: Stop at line number (null = read to end)
  injection_mode: "line"     # Options: "line", "paragraph", "character_scene"

schedule:
  interval_seconds: 180      # Base seconds between injections (e.g., 3 minutes)
  randomization_seconds: 30  # Optional: ± variance in scheduling (0 = exact timing)

logging:
  level: "DEBUG"
  file: "./logs/debug.log"
```

### Environment Variables (Required for Sensitive Data)

| Variable | Description | Priority |
|----------|-------------|----------|
| `DISCORD_TOKEN` | Discord bot token - **required**, not in config file | High |

### Configuration Options

| Option | Type | Description | Default |
|--------|------|-------------|---------|
| `discord.channel_id` | string | Target Discord channel ID | Required |
| `source.file_path` | string | Path to source text file | Required |
| `source.skip_header` | boolean | Skip Project Gutenberg header sections | true |
| `source.skip_footer` | boolean | Skip Project Gutenberg footer markers | true |
| `source.start_line` | integer | Start reading from line number (1-based) | 30 |
| `source.end_line` | integer/None | Stop at line number (None = read to end) | None |
| `source.injection_mode` | string | Grouping strategy: "line", "paragraph", or "character_scene" | "line" |
| `schedule.interval_seconds` | integer | Base seconds between injections | 180 (3 min) |
| `schedule.randomization_seconds` | integer | ± variance in scheduling (0 = exact timing) | 0 |
| `logging.level` | string | Logging level (DEBUG/INFO/WARNING/ERROR) | DEBUG |
| `logging.file` | string | Path to debug log file | ./logs/debug.log |

**Security Note**: The Discord token is provided exclusively via the `DISCORD_TOKEN` environment variable. It is never stored in the config file, preventing accidental exposure when sharing code or committing to version control.

---

## File Structure

```
discord-textfeed-bot/
├── docs/
│   └── architecture.md
├── logs/
│   └── debug.log
├── config.yaml
├── src/
│   ├── __init__.py
│   ├── bot.py              # Main Discord bot entry point
│   ├── config_loader.py    # Configuration management
│   ├── file_reader.py      # Source text file reading
│   ├── message_queue.py    # Line queue management
│   └── scheduler.py        # Interval-based scheduling
├── requirements.txt
└── README.md
```

---

## Module Details

### 1. config_loader.py - Configuration Management

**Responsibilities:**
- Load configuration from YAML/JSON file
- Validate required fields (token, channel_id, file_path)
- Provide type-safe access to configuration values
- Support environment variable overrides for sensitive data

**Key Functions:**
```python
def load_config(path: str) -> ConfigData:
    """Load and validate configuration from file."""

def get_discord_token() -> str:
    """Get Discord token (supports env override)."""

def get_channel_id() -> int:
    """Get target channel ID."""

def get_source_file_path() -> Path:
    """Get path to source text file."""

def get_interval_seconds() -> int:
    """Get injection interval in seconds."""
```

### 2. file_reader.py - Source Text File Reading

**Responsibilities:**
- Read UTF-8 encoded text file
- Split content into individual lines
- Handle line endings (CRLF, LF)
- Filter out header/footer sections (Project Gutenberg markers, license text, etc.)
- Support configurable start/end line ranges
- Group content based on injection mode:
  - `line`: Return individual lines as-is
  - `paragraph`: Group consecutive non-empty lines into paragraphs
  - `character_scene` (play): Separate character names from dialogue and stage directions
- Return list of content units ready for injection

**Key Functions:**
```python
def read_source_file(path: Path, skip_header: bool = True, skip_footer: bool = True,
                     start_line: int = 30, end_line: Optional[int] = None,
                     injection_mode: str = "line") -> List[str]:
    """Read and parse source text file with optional filtering and grouping."""

def get_content_count(lines: List[str]) -> int:
    """Return total number of content units available after processing."""
```

### 3. message_queue.py - Content Queue Management

**Responsibilities:**
- Maintain queue of content unit indices to send (supports line/paragraph/character_scene modes)
- Track current position in source file
- Persist position to disk (e.g., `.state.json`) to recover gracefully after restarts
- Handle wraparound when reaching end of file
- Async-safe operations for concurrent access within the asyncio event loop
- Enforce Discord's 2000-character limit on content units
- Provide total count and progress tracking

**Key Functions:**
```python
class MessageQueue:
    def __init__(self, content_units: List[str]):
        """Initialize with list of content units (lines/paragraphs/scenes)."""
    
    def get_next_index(self) -> int:
        """Get index of next content unit to send (thread-safe)."""
    
    def reset_position(self):
        """Reset queue position to start after completion."""
    
    def get_total_units(self) -> int:
        """Return total content units in queue."""
```

### 4. scheduler.py - Interval-Based Scheduling

**Responsibilities:**
- Run at configured intervals using asyncio with optional randomization
- Coordinate with message queue for next content unit
- Handle graceful shutdown on bot close
- Log operational events (not content)
- Support multi-line injection when needed (e.g., paragraphs sent as single message)

**Key Functions:**
```python
class InjectionScheduler:
    def __init__(self, interval_seconds: int, randomization_seconds: int = 0, queue: MessageQueue):
        """Initialize scheduler with base interval and optional randomization."""
    
    async def start(self):
        """Start the injection loop with randomized intervals."""
    
    async def stop(self):
        """Stop the injection loop gracefully."""

async def inject_content(index: int, content_unit: str) -> bool:
    """Send a single content unit to Discord channel. Logs operation only."""
```

### 5. bot.py - Main Discord Bot Entry Point

**Responsibilities:**
- Initialize Discord client with intents
- Load configuration on startup
- Start file reader and message queue
- Start scheduler loop
- Handle graceful shutdown (SIGINT, SIGTERM)
- Log startup/shutdown events

**Key Functions:**
```python
async def main():
    """Main entry point for the bot."""
    
def run_bot():
    """Entry point that handles signal handling."""
```

---

## Logging Strategy

### Debug Logging (Operational Events Only)

The bot logs operational information without exposing actual content:

**Logged Events:**
- Bot startup/shutdown
- Configuration loaded successfully
- Source file read: X lines available
- Line injection attempt (line number, success/failure)
- Queue position updates
- Scheduler interval changes
- Errors and exceptions

**NOT Logged:**
- Actual line content from source file
- User messages or channel names containing sensitive data

### Log Levels

| Level | Usage |
|-------|-------|
| DEBUG | Detailed operational info (line numbers, queue state) |
| INFO | Key events (startup, shutdown, successful injections) |
| WARNING | Non-fatal issues (file not found, rate limiting) |
| ERROR | Errors that prevent operation |

---

## Error Handling

### Expected Errors

1. **Discord API Rate Limiting**: Implement exponential backoff
2. **Source File Not Found**: Log error and exit gracefully
3. **Invalid Channel ID**: Attempt to fetch channel, log if fails
4. **Empty Source File**: Exit with warning (no lines to send)

### Error Recovery

- Non-fatal errors: Log and continue on next interval
- Fatal errors: Log, attempt restart after delay, then exit
- All errors logged to debug file for troubleshooting

---

## Security Considerations

1. **Token Storage**: Discord token MUST be provided exclusively via the `DISCORD_TOKEN` environment variable.
2. **No Token in Config**: The configuration file must never contain the token to prevent accidental version control leaks.
3. **No Content Logging**: Actual text content never written to logs or files
4. **File Permissions**: Config and log files should have restricted permissions

---

## Testing Strategy

### Unit Tests
- Configuration loading with various formats
- File reading with different encodings/line endings
- Message queue operations (thread safety)
- Scheduler interval accuracy

### Integration Tests
- Bot connects to Discord server
- Messages sent to correct channel
- Interval timing is accurate
- Graceful shutdown works correctly

---

## Deployment Considerations

1. **Environment Variables**: Use `.env` file for sensitive configuration (DISCORD_TOKEN)
2. **Process Management**: Run with `systemd`, `supervisor`, or similar
3. **Log Rotation**: Implement log rotation to prevent disk space issues
4. **Health Checks**: Monitor process uptime and recent injection success rate

### Container Deployment (Podman/Docker)

The bot is designed to run in a container for improved security and portability. A [`Containerfile`](../Containerfile) is provided at the project root.

**Build:**
```bash
podman build -t discord-textfeed-bot .
```

**Run with environment variable:**
```bash
podman run -d \
  --name textfeed-bot \
  -e DISCORD_TOKEN="your_token_here" \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/logs:/app/logs \
  discord-textfeed-bot
```

**Run with .env file:**
```bash
podman run -d \
  --name textfeed-bot \
  --env-file=.env \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/logs:/app/logs \
  discord-textfeed-bot
```

**Container Configuration:**
- Non-root user (`appuser`) for security
- Read-only config file mount
- Writable logs directory
- No exposed ports (headless service)
- Python 3.12 slim base image
- Health check included

**Podman Pod Example (with volume mounts):**
```bash
podman run -d \
  --name textfeed-bot \
  --env-file=.env \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/logs:/app/logs \
  discord-textfeed-bot
```

**Podman Pod with Source File Volume:**
```bash
podman run -d \
  --name textfeed-bot \
  --env-file=.env \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/books/test_book.txt:/app/books/test_book.txt:ro \
  discord-textfeed-bot
```

---

## Future Enhancements (Optional)

- Multiple source files with rotation
- Command-line arguments for override values
- REST API endpoint to control bot remotely
- Statistics dashboard showing injection history
- Support for Project Gutenberg API instead of local file

---

## Implementation Notes

1. Use `discord.py` version 2.x (async/await based)
2. Python 3.9+ required for type hints and f-strings
3. Use `pyyaml` or `toml` for configuration parsing
4. Use `logging` module with file handler for debug output
5. All async operations should be properly awaited
