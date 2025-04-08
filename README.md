# 📺 Followarr

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Discord](https://img.shields.io/badge/Discord-Bot-7289DA.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Docker](https://img.shields.io/badge/Docker-Available-2496ED.svg)

A Discord bot that integrates with Tautulli to notify users about new episodes of their favorite TV shows.  
Get notifications when new episodes are added to your media server!

</div>

---

## ✨ Features

### Discord Commands
- 🔔 `/follow <show name>`
  - Follow a TV show to receive notifications
  - Rich embed with show details:
    - Show poster
    - Overview
    - Network info
    - First aired date
    - Current status

- 🚫 `/unfollow <show name>`
  - Unfollow a TV show
  - Confirmation message with show details
  - Visual feedback with show poster

- 📋 `/list`
  - View all your followed shows
  - Clean, organized display

- 📅 `/calendar`
  - View upcoming episodes for your followed shows
  - Organized by month and date
  - Summary of total episodes
  - Next episode information
  - Statistics about your followed shows

### Notifications
Receive detailed Discord DMs when new episodes are available:
- 🆕 Show title and episode info
- 📺 Season and episode numbers
- 📝 Episode summary
- 📅 Air date
- 🖼️ Show poster from TVDB
- 📊 Show status
- ⌚ Timestamp

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+ (for manual installation)
- Discord Bot Token
- TVDB API Key
- Tautulli instance with API access
- Docker (for Docker installation)

### 🤖 Discord Bot Setup

1. Visit the [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a "New Application"
3. Navigate to the "Bot" section:
   ```
   ✓ Add Bot
   ✓ Enable MESSAGE CONTENT INTENT
   ✓ Enable SERVER MEMBERS INTENT
   ```
4. Get your bot token (keep this secret!)

5. Configure OAuth2:
   - Required Scopes:
     ```
     • bot
     • applications.commands
     ```
   - Required Permissions:
     ```
     • Send Messages
     • Send Messages in Threads
     • Embed Links
     • Read Messages/View Channels
     • Use Slash Commands
     ```

---

## 📦 Installation

### Quick Install with Docker (Recommended)

The easiest way to install Followarr is using Docker. We provide installation scripts for both Linux/macOS and Windows:

#### Linux/macOS
```bash
# Download the installation script
curl -sSL https://raw.githubusercontent.com/d3v1l1989/Followarr/main/install.sh -o install.sh

# Make it executable
chmod +x install.sh

# Run the installation script
./install.sh
```

#### Windows
```powershell
# Download the installation script
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/d3v1l1989/Followarr/main/install.ps1" -OutFile "install.ps1"

# Run the installation script
.\install.ps1
```

The installation script will:
1. Check if Docker is installed
2. Create necessary directories
3. Set up the .env file from the template
4. **Offer to open the .env file for editing** (or you can edit it later)
5. Pull the Docker image
6. Start the container

### Manual Docker Installation

1. Clone the repository:
```bash
git clone https://github.com/d3v1l1989/Followarr.git
cd Followarr
```

2. Set up environment:
```bash
cp .env.example .env
mkdir -p data logs config
```

3. Configure `.env`:
```env
# Discord Configuration
DISCORD_BOT_TOKEN=YourToken
DISCORD_CHANNEL_ID=YourChannelId

# API Keys
TVDB_API_KEY=YourTVDBKey
TAUTULLI_API_KEY=YourTautulliKey

# URLs and Ports
TAUTULLI_URL=http://your-tautulli-server:8181
DATABASE_URL=sqlite:///data/followarr.db
WEBHOOK_SERVER_PORT=3000

# Docker Settings
TZ=Your/Timezone
UID=1000
GID=1000
```

4. Launch with Docker:
```bash
docker-compose up -d
```

### Manual Installation (Without Docker)

1. Install requirements:
```bash
pip install -r requirements.txt
```

2. Run the bot:
```bash
python -m src.bot
```

---

## 🔧 Configuration

### Environment Variables

The bot requires several environment variables to be set in the `.env` file:

| Variable | Description | Required |
|----------|-------------|----------|
| `DISCORD_BOT_TOKEN` | Your Discord bot token | Yes |
| `DISCORD_CHANNEL_ID` | The Discord channel ID for notifications | Yes |
| `TVDB_API_KEY` | Your TVDB API key | Yes |
| `TAUTULLI_API_KEY` | Your Tautulli API key | Yes |
| `TAUTULLI_URL` | URL of your Tautulli instance | Yes |
| `DATABASE_URL` | SQLite database URL | No (defaults to `sqlite:///data/followarr.db`) |
| `WEBHOOK_SERVER_PORT` | Port for the webhook server | No (defaults to `3000`) |
| `TZ` | Your timezone | No (defaults to `UTC`) |
| `UID` | User ID for Docker | No (defaults to `1000`) |
| `GID` | Group ID for Docker | No (defaults to `1000`) |

### Tautulli Webhook Setup

1. In Tautulli Settings → Notification Agents:
2. Add new Webhook agent
3. Configure URL:
   ```
   Docker: http://followarr:3000/webhook/tautulli
   Local:  http://your-server-ip:3000/webhook/tautulli
   ```
4. Enable "Recently Added" notifications

### Docker Network (Optional)

Add Tautulli to the same network:
```yaml
services:
  tautulli:
    networks:
      - followarr-net

networks:
  followarr-net:
    external: true
```

---

## 🧪 Testing

### Command Testing
Test basic functionality:

1. `/follow <show name>` - Try following a show
2. `/list` - Check your followed shows
3. `/calendar` - View upcoming episodes
4. `/unfollow <show name>` - Unfollow a show

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

## Calendar Feature

The `/calendar` command provides a comprehensive view of upcoming episodes:

- 📅 Monthly view of upcoming episodes
- 📺 Show name and episode details
- 📊 Statistics about your followed shows
- ⏰ Next episode information
- 📈 Overview of total episodes and shows

The calendar is organized by date and only shows months with upcoming episodes, keeping the output clean and focused on relevant information.

## Testing

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
docker-compose logs -f
```

## License

MIT License - See [LICENSE](LICENSE) for details 