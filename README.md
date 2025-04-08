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
git clone https://github.com/yourusername/Followarr.git
cd Followarr
```

2. Copy the example environment file and fill in your values:
```bash
cp .env.example .env
```

3. Run with Docker:
```bash
docker-compose up -d
```

Or run directly with Python:
```bash
pip install -r requirements.txt
python -m src.bot
```

## Configuration

Create a `.env` file with the following variables:

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
```

## Setting up Tautulli Webhooks

1. In Tautulli, go to Settings -> Notification Agents
2. Add a new Webhook agent
3. Set the Webhook URL to: `http://your-server:3000/webhook/tautulli`
4. Enable notifications for "Recently Added"

## License

MIT License - See [LICENSE](LICENSE) for details 