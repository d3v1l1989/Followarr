# Followarr

A Discord bot that integrates with Tautulli to notify users about new episodes of their favorite TV shows. Users can follow/unfollow shows and receive notifications when new episodes are added to their media server.

## Features

- `/follow <show name>` - Follow a TV show to receive notifications
- `/unfollow <show name>` - Unfollow a TV show
- `/list` - List all shows you're following
- Automatic notifications when new episodes are added
- Integration with Tautulli for media server monitoring
- TVDB integration for show information

## Requirements

- Python 3.11+
- Discord Bot Token
- TVDB API Key
- Tautulli instance with API access
- Docker (optional)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/d3v1l1989/Followarr.git
cd Followarr
```

2. Copy the example environment file:
```bash
cp .env.example .env
```

3. Set up environment variables:
```bash
# Get your user and group IDs (for Docker)
echo "UID=$(id -u)" >> .env
echo "GID=$(id -g)" >> .env

# Set your timezone (example for Belgrade)
echo "TZ=Europe/Belgrade" >> .env
```

4. Create necessary directories:
```bash
mkdir -p data logs
```

5. Fill in the remaining environment variables in `.env`:
- `DISCORD_BOT_TOKEN` - Your Discord bot token
- `DISCORD_CHANNEL_ID` - Channel ID for notifications
- `TVDB_API_KEY` - Your TVDB API key
- `TAUTULLI_URL` - URL to your Tautulli instance
- `TAUTULLI_API_KEY` - Your Tautulli API key

## Running the Bot

### Using Docker (Recommended)

```bash
docker-compose up -d
```

### Without Docker

1. Install requirements:
```bash
pip install -r requirements.txt
```

2. Run the bot:
```bash
python -m src.bot
```

## Configuration

The `.env` file contains all necessary configuration:

```env
# Discord Bot Configuration
DISCORD_BOT_TOKEN=YourDiscordBotToken
DISCORD_CHANNEL_ID=YourDiscordChannelId

# TVDB API Configuration
TVDB_API_KEY=YourTVDBApiKey

# Tautulli Configuration
TAUTULLI_URL=http://your-tautulli-server:8181
TAUTULLI_API_KEY=YourTautulliApiKey

# Database Configuration
DATABASE_URL=sqlite:///data/followarr.db

# Webhook Server Configuration
WEBHOOK_SERVER_PORT=3000

# Docker Configuration
TZ=UTC  # Set your timezone (e.g., Europe/Belgrade)
UID=1000  # Your user ID
GID=1000  # Your group ID
```

## Setting up Tautulli Webhooks

1. In Tautulli, go to Settings -> Notification Agents
2. Add a new Webhook agent
3. Set the Webhook URL to: `http://your-server:3000/webhook/tautulli`
4. Enable notifications for "Recently Added"

## Docker Volumes

The bot uses two Docker volumes:
- `./data:/app/data` - Stores the SQLite database
- `./logs:/app/logs` - Stores application logs

## License

MIT License - See [LICENSE](LICENSE) for details 