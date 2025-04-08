# Followarr

A Discord bot that integrates with Tautulli to notify users about new episodes of their favorite TV shows. Users can follow/unfollow shows and receive notifications when new episodes are added to their media server.

## Features

- `/follow <show name>` - Follow a TV show to receive notifications
  - Shows detailed information about the show
  - Includes show poster, overview, status, and network info
  - First aired date and current status
- `/unfollow <show name>` - Unfollow a TV show
  - Confirmation message with show details
  - Show poster and status included
- `/list` - List all shows you're following
- Rich notifications when new episodes are added:
  - Show poster from TVDB
  - Episode details (season, episode, title)
  - Episode summary
  - Air date
  - Show status
  - Direct message to followers

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
- 📅 Air date
- 🖼️ Show poster from TVDB
- 📊 Show status
- Timestamp of when the episode was added

The notifications use rich embeds with:
- Show posters from TVDB
- Color-coded status indicators
- Formatted timestamps
- Detailed episode information

## Testing

### Command Testing
You can test the bot's basic functionality using these commands:
1. `/follow <show name>` - Try following a show
2. `/list` - Verify the show appears in your list
3. `/unfollow <show name>` - Try unfollowing the show

### Notification Testing
To test the notification system:

1. Use the `/list` command in Discord to get the ID of a show you're following
2. Run the test notification script:
   ```bash
   python tests/test_notification.py <show_id>
   ```
   For example:
   ```bash
   python tests/test_notification.py 403245
   ```
3. You should receive a DM from the bot with the test notification

The test script simulates a webhook that would be sent when a new episode is added to your media server.

## Troubleshooting

### Common Issues
- If commands don't appear, try removing and re-adding the bot to your server
- If notifications aren't working, check your Discord privacy settings allow DMs from server members
- For webhook testing issues, ensure port 3000 is accessible if testing from outside Docker

### Logs
The bot provides detailed logging for troubleshooting:
```bash
docker compose logs -f
```

## License

MIT License - See [LICENSE](LICENSE) for details 