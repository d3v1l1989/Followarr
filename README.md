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

## Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the "Bot" section:
   - Click "Add Bot"
   - Under "Privileged Gateway Intents", enable:
     - MESSAGE CONTENT INTENT
     - SERVER MEMBERS INTENT
   - Click "Reset Token" to get your bot token (save this for `.env`)

4. Go to OAuth2 -> URL Generator:
   - Select these scopes:
     - `bot`
     - `applications.commands`
   - Select these bot permissions:
     - `Send Messages`
     - `Send Messages in Threads`
     - `Embed Links`
     - `Read Messages/View Channels`
     - `Use Slash Commands`
   - Copy the generated URL and use it to add the bot to your server

5. Get your Channel ID:
   - Enable Developer Mode in Discord:
     - Discord Settings -> App Settings -> Advanced -> Developer Mode
   - Right-click on the channel you want to use
   - Click "Copy ID"
   - Save this ID for `.env`

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
```env
# Discord Bot Configuration
DISCORD_BOT_TOKEN=YourDiscordBotToken    # From Discord Developer Portal
DISCORD_CHANNEL_ID=YourDiscordChannelId  # Right-click channel -> Copy ID

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

## Setting up Tautulli Webhooks

1. In Tautulli, go to Settings -> Notification Agents
2. Add a new Webhook agent
3. Set the Webhook URL:
   - If Tautulli is running in the same Docker network: `http://followarr:3000/webhook/tautulli`
   - If Tautulli is running outside Docker: `http://your-server-ip:3000/webhook/tautulli`
4. Enable notifications for "Recently Added"

## Docker Network Configuration

If you're running Tautulli in Docker as well, you can add it to the same network for easier communication:

```yaml
# In your Tautulli docker-compose.yml
services:
  tautulli:
    # ... other Tautulli configuration ...
    networks:
      - followarr-net

networks:
  followarr-net:
    external: true
```

## Notifications

When a new episode is added to your media server, subscribers will receive a Discord DM containing:

- 🆕 Show title and notification
- 📺 Episode number and title
- 📝 Episode summary (if available)
- 📅 Air date (if available)
- 🎥 Video quality (if available)
- ⏱️ Episode duration
- 🖼️ Show thumbnail (if available)
- Timestamp of when the episode was added

## License

MIT License - See [LICENSE](LICENSE) for details 