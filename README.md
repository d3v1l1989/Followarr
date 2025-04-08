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
- 🔔 `/follow <show name>` - Follow a TV show to receive notifications
- 🚫 `/unfollow <show name>` - Unfollow a TV show
- 📋 `/list` - View all your followed shows
- 📅 `/calendar` - View upcoming episodes for your followed shows

### Notifications
Receive detailed Discord DMs when new episodes are available:
- Show title, episode info, and summary
- Season and episode numbers
- Air date and show poster
- Show status and timestamp

---

## 🚀 Getting Started

### Prerequisites

- Discord Bot Token
- TVDB API Key
- Tautulli instance with API access
- Docker and Docker Compose

### 🤖 Discord Bot Setup

1. Visit the [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a "New Application" and add a bot
3. Enable required intents:
   ```
   ✓ MESSAGE CONTENT INTENT
   ✓ SERVER MEMBERS INTENT
   ```
4. Copy your bot token - you'll need it for the configuration

### 🐳 Docker Installation

1. Create a directory for Followarr and navigate to it:
   ```bash
   mkdir Followarr
   cd Followarr
   ```

2. Download the required files:
   ```bash
   # Download docker-compose.yml and .env.example
   curl -O https://raw.githubusercontent.com/d3v1l1989/Followarr/main/docker-compose.yml
   curl -O https://raw.githubusercontent.com/d3v1l1989/Followarr/main/.env.example
   
   # Download the installation script
   curl -O https://raw.githubusercontent.com/d3v1l1989/Followarr/main/install.sh  # For Linux/Mac
   # OR
   curl -O https://raw.githubusercontent.com/d3v1l1989/Followarr/main/install.ps1  # For Windows
   ```

3. Make the installation script executable (Linux/Mac only):
   ```bash
   chmod +x install.sh
   ```

4. Run the installation script:
   ```bash
   ./install.sh  # For Linux/Mac
   # OR
   .\install.ps1  # For Windows
   ```

5. Edit the `.env` file with your configuration:
   ```bash
   nano .env  # or use any text editor
   ```

6. The bot will automatically start after installation. You can check the logs with:
   ```bash
   docker compose logs -f
   ```

### 🔧 Configuration

Edit the `.env` file with your settings:

```env
# Discord Bot Configuration
DISCORD_BOT_TOKEN=your_discord_bot_token
DISCORD_CHANNEL_ID=your_discord_channel_id

# TVDB API Configuration
TVDB_API_KEY=your_tvdb_api_key

# Tautulli Configuration
TAUTULLI_URL=http://your-tautulli-server:8181
TAUTULLI_API_KEY=your_tautulli_api_key

# Webhook Server Configuration
WEBHOOK_SERVER_PORT=3000

# Logging Configuration
LOG_LEVEL=INFO
```

### 🔄 Updating

To update to the latest version:

```bash
docker compose pull
docker compose up -d
```

### 🛑 Stopping the Bot

```bash
docker compose down
```

### 📝 Viewing Logs

```bash
docker compose logs -f
```

### 🔄 Restarting

After making changes to the `.env` file:

```bash
docker compose restart
```

---

## 📦 Installation

### Quick Install with Docker (Recommended)

The easiest way to install Followarr is using Docker. We provide installation scripts for both Linux/macOS and Windows:

#### Linux/macOS
```bash
# Download and run the installation script
curl -sSL https://raw.githubusercontent.com/d3v1l1989/Followarr/main/install.sh -o install.sh
chmod +x install.sh
./install.sh
```

#### Windows
```powershell
# Download and run the installation script
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/d3v1l1989/Followarr/main/install.ps1" -OutFile "install.ps1"
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

3. Configure `.env` with your settings:
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

### Docker Network Configuration

**Important**: Make sure Followarr is on the same Docker network as your Tautulli container. If Tautulli is running in Docker, add it to the same network:

```yaml
services:
  tautulli:
    networks:
      - followarr-net

networks:
  followarr-net:
    external: true
```

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

## Screenshots

Here are some screenshots of the bot in action:

### Calendar Command
<img src="docs/screenshots/resized/calendar.png" alt="Calendar Command" width="300"/>

_View upcoming episodes for your followed shows_

### Follow Command
<img src="docs/screenshots/resized/follow.png" alt="Follow Command" width="450"/>

_Follow a new TV show_

### Unfollow Command
<img src="docs/screenshots/resized/unfollow.png" alt="Unfollow Command" width="450"/>

_Unfollow a TV show_

### List Command
<img src="docs/screenshots/resized/list.png" alt="List Command" width="300"/>

_View all your followed shows_

### Episode Notification
<img src="docs/screenshots/resized/notification.png" alt="Episode Notification" width="450"/>

_Receive notifications for new episodes_

## 👨‍💻 Development

### 🔄 Versioning

Followarr uses semantic versioning (MAJOR.MINOR.PATCH):
- MAJOR: Breaking changes
- MINOR: New features, backward compatible
- PATCH: Bug fixes, backward compatible