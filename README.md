# Discord Text Feed Bot

A Python-based Discord bot that reads lines from a user-provided text file and injects them into a configurable Discord channel at a configurable rate. The primary use case is to generate test messages for another bot that summarizes daily discussions in a channel.

## Features

- **Configurable Injection Rate**: Set base interval with optional randomization (±N seconds)
- **Channel Configuration**: Target Discord channel ID specified in config file
- **Book Selection**: User provides a UTF-8 encoded text file containing the source content (e.g., Project Gutenberg eBooks)
- **Output Format**: Raw text lines only, no additional formatting or metadata
- **Content Filtering**: Optional skip of header/footer sections (Project Gutenberg markers, table of contents, etc.)
- **Injection Modes**:
  - `line`: Inject each line individually (default)
  - `paragraph`: Group consecutive non-empty lines into paragraphs before injecting
  - `character_scene` (play mode): Group dialogue by character and stage directions separately
- **State Persistence**: Track and save the current injection position to survive bot restarts
- **Message Limits**: Ensures no injected content exceeds Discord's 2000-character limit
- **Debug Logging**: Logs operational events without logging actual content

## Installation

### Prerequisites

- Python 3.9 or higher
- pip (Python package manager)

### Install Dependencies

```bash
pip install -r requirements.txt
```

The required packages are:
- `discord.py>=2.3.0` - Discord bot library
- `pyyaml>=6.0` - YAML configuration parsing
- `python-dotenv>=1.0.0` - Environment variable management

## Configuration

### 1. Set Environment Variable

Create a `.env` file in the project root:

```bash
cp .env.example .env
# Edit .env and add your Discord token
echo "DISCORD_TOKEN=your_bot_token_here" >> .env
```

**Important**: Never commit your `.env` file to version control. The bot token is required but never stored in the config file for security reasons.

### 2. Configure Bot

Edit `config.yaml`:

```yaml
# Discord Text Feed Bot Configuration

discord:
  # Target Discord channel ID (required)
  channel_id: "123456789012345678"

source:
  # Path to the source text file (relative or absolute path)
  file_path: "./books/test_book.txt"
  
  # Skip Project Gutenberg header sections (license, title page, etc.)
  skip_header: true
  
  # Skip Project Gutenberg footer markers
  skip_footer: true
  
  # Start reading from line number (1-based). Default is 30 to skip PG headers.
  start_line: 30
  
  # Optional: Stop at this line number. Set to null or omit to read to end.
  end_line: null
  
  # Injection mode - how content is grouped before sending:
  # "line"    - Send each line individually (default)
  # "paragraph" - Group consecutive non-empty lines into paragraphs
  # "character_scene" - Separate character names from dialogue and stage directions (for plays)
  injection_mode: "line"

schedule:
  # Base seconds between injections (e.g., 180 = 3 minutes)
  interval_seconds: 180
  
  # Optional: ± variance in scheduling (0 = exact timing)
  randomization_seconds: 30

logging:
  # Logging level: DEBUG, INFO, WARNING, or ERROR
  level: "DEBUG"
  
  # Path to the debug log file
  file: "./logs/debug.log"
```

### Configuration Options Summary

| Option | Type | Description | Default |
|--------|------|-------------|---------|
| `discord.channel_id` | string | Target Discord channel ID (required) | - |
| `source.file_path` | string | Path to source text file (required) | - |
| `source.skip_header` | boolean | Skip Project Gutenberg header sections | true |
| `source.skip_footer` | boolean | Skip Project Gutenberg footer markers | true |
| `source.start_line` | integer | Start reading from line number (1-based) | 30 |
| `source.end_line` | integer/None | Stop at line number (None = read to end) | None |
| `source.injection_mode` | string | Grouping strategy: "line", "paragraph", or "character_scene" | "line" |
| `schedule.interval_seconds` | integer | Base seconds between injections | 180 |
| `schedule.randomization_seconds` | integer | ± variance in scheduling (0 = exact timing) | 0 |
| `logging.level` | string | Logging level (DEBUG/INFO/WARNING/ERROR) | DEBUG |
| `logging.file` | string | Path to debug log file | ./logs/debug.log |

## Usage

### Running the Bot Locally

```bash
python src/bot.py
```

The bot will:
1. Load configuration from `config.yaml`
2. Read the source text file specified in config
3. Connect to Discord using the token from `.env`
4. Start injecting content at the configured interval

### Graceful Shutdown

Press `Ctrl+C` or send SIGTERM to gracefully shut down the bot. The current position will be saved before exit.

### Running with Podman/Docker

```bash
# Build the container
podman build -t discord-textfeed-bot .

# Run with environment variable and volume mounts
podman run -d \
  --name textfeed-bot \
  -e DISCORD_TOKEN="your_token_here" \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/logs:/app/logs \
  discord-textfeed-bot

# Run with .env file
podman run -d \
  --name textfeed-bot \
  --env-file=.env \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/logs:/app/logs \
  discord-textfeed-bot
```

## Project Structure

```
discord-textfeed-bot/
├── docs/
│   └── architecture.md      # Architecture documentation
├── logs/                    # Debug log files (created at runtime)
│   └── debug.log
├── config.yaml             # Bot configuration
├── .env.example            # Template for environment variables
├── requirements.txt        # Python dependencies
├── Containerfile           # Podman/Docker build file
├── README.md               # This file
└── src/
    ├── __init__.py         # Package initialization
    ├── bot.py              # Main Discord bot entry point
    ├── config_loader.py    # Configuration management
    ├── file_reader.py      # Source text file reading
    ├── message_queue.py    # Line queue management
    └── scheduler.py        # Interval-based scheduling
```

## Logging

The bot logs operational events to the specified log file (default: `./logs/debug.log`). Logged events include:

- Bot startup/shutdown
- Configuration loaded successfully
- Source file read count
- Line injection attempts (line number, success/failure)
- Queue position updates
- Scheduler interval changes
- Errors and exceptions

**Note**: Actual content from the source file is never logged for security reasons.

## Error Handling

The bot handles common errors gracefully:

| Error | Behavior |
|-------|----------|
| Discord API Rate Limiting | Exponential backoff, continues on next interval |
| Source File Not Found | Logs error and exits gracefully |
| Invalid Channel ID | Attempts to fetch channel, logs failure if it fails |
| Empty Source File | Exits with warning (no lines to send) |

## Security Considerations

1. **Token Storage**: Discord token MUST be provided exclusively via the `DISCORD_TOKEN` environment variable. It is never stored in the config file.
2. **No Content Logging**: Actual text content never written to logs or files.
3. **File Permissions**: Config and log files should have restricted permissions (e.g., `chmod 600`).

## Testing

Unit tests can be run with:

```bash
python -m pytest tests/ -v
```

## License

See [LICENSE](LICENSE) file for details.

## Future Enhancements

- Multiple source files with rotation
- Command-line arguments for override values
- REST API endpoint to control bot remotely
- Statistics dashboard showing injection history
- Support for Project Gutenberg API instead of local file
