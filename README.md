# 📺 Followarr

<div align="center">
<img src="docs/screenshots/followarr.png" alt="Followarr Logo" width="300"/>

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Discord](https://img.shields.io/badge/Discord-Bot-7289DA.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Docker](https://img.shields.io/badge/Docker-Available_on_GHCR-2496ED.svg)

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

This section guides you through setting up Followarr.

### Prerequisites

- Discord Bot Token (See setup below)
- TVDB API Key ([Get one here](https://thetvdb.com/subscribe))
- Tautulli instance with API access enabled
- Docker and Docker Compose installed

### 🤖 Discord Bot Setup

1.  Visit the [Discord Developer Portal](https://discord.com/developers/applications).
2.  Create a "New Application" and give it a name (e.g., Followarr).
3.  Navigate to the "Bot" tab.
4.  Click "Add Bot" and confirm.
5.  **Enable Required Intents:**
    *   Under "Privileged Gateway Intents", enable:
        *   `MESSAGE CONTENT INTENT`
        *   `SERVER MEMBERS INTENT` (May be needed depending on future features or specific server setups)
6.  **Copy Your Bot Token:** Click "Reset Token" (and confirm) to view and copy your bot token. **Treat this like a password!** You'll need it for the `.env` configuration.
7.  **Invite the Bot:** Go to the "OAuth2" -> "URL Generator" tab.
    *   Select the `bot` and `applications.commands` scopes.
    *   Under "Bot Permissions", select:
        *   `Send Messages`
        *   `Embed Links`
        *   `Read Message History` (To process commands)
    *   Copy the generated URL and paste it into your browser to invite the bot to your server.

### 🐳 Docker Installation

Followarr is best installed using Docker and the official image from GitHub Container Registry (ghcr.io).

This is the recommended method to install Followarr.

1.  **Create a Directory:**
    ```bash
    mkdir followarr
    cd followarr
    ```

2.  **Create `docker-compose.yml`:**
    Create a file named `docker-compose.yml` in the `followarr` directory and paste the following content:

    ```yaml
    services:
      followarr:
        image: ghcr.io/d3v1l1989/followarr:edge # Use :edge for latest dev, or a version tag like :v1.0.0
        container_name: followarr
        restart: unless-stopped
        environment:
          - TZ=${TZ:-UTC}
        env_file:
          - .env
        volumes:
          # Use named volumes to store persistent data
          - followarr-data:/app/data # Stores database
          - followarr-logs:/app/logs # Stores log files
        ports:
          # Exposes the webhook port (default 3000)
          - "${WEBHOOK_SERVER_PORT:-3000}:3000" 
        # Optional: Run as a specific user/group
        user: "${UID:-1000}:${GID:-1000}" 
        healthcheck:
          # Checks if the webhook server is responsive
          test: ["CMD", "curl", "-f", "http://localhost:${WEBHOOK_SERVER_PORT:-3000}/health"]
          interval: 30s
          timeout: 10s
          retries: 3
          start_period: 10s
        logging:
          # Configure Docker log rotation
          driver: "json-file"
          options:
            max-size: "10m"
            max-file: "3"
        networks:
          - followarr-net # Connect to the dedicated network

    networks:
      followarr-net:
        driver: bridge # Default bridge network

    # Define the named volumes used by the service
    volumes:
      followarr-data:
      followarr-logs:
    ```

3.  **Create and Configure `.env` File:**
    Create a file named `.env` in the `followarr` directory and paste the following content. **Then, edit this file with your actual settings (BOT TOKEN, TVDB KEY, etc.).**

    ```env
    # Discord Bot Configuration
    DISCORD_BOT_TOKEN=YourDiscordBotToken
    DISCORD_CHANNEL_ID=YourDiscordChannelId # Channel ID where bot might post updates (future use)

    # TVDB API Configuration
    TVDB_API_KEY=YourTVDBApiKey

    # Tautulli Configuration
    TAUTULLI_URL=http://your-tautulli-server:8181 # URL to access Tautulli
    TAUTULLI_API_KEY=YourTautulliApiKey

    # Database Configuration (uses SQLite by default)
    DATABASE_URL=sqlite:///data/followarr.db

    # Webhook Server Configuration
    WEBHOOK_SERVER_PORT=3000 # Port the internal webhook server listens on

    # Logging Configuration
    LOG_LEVEL=INFO  # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL

    # Docker Configuration
    TZ=UTC  # Set your timezone (e.g., Europe/Belgrade)
    UID=1000  # Your user ID on the host (run 'id -u')
    GID=1000  # Your group ID on the host (run 'id -g')
    ```
    *This is a crucial step! Fill in all required variables.* 

4.  **Start Followarr:**
    ```bash
    docker compose up -d
    ```
    This will pull the `ghcr.io/d3v1l1989/followarr:edge` image (latest development build) and start the container.

5.  **(Optional) Use a Specific Version:** To use a stable release, edit `docker-compose.yml` (the file you created in Step 2) and change the image tag from `:edge` to a specific version, like `:v1.0.0`, before running `docker compose up -d`.

### ⚙️ Post-Installation Configuration

*   **Database & Logs:** Followarr uses Docker named volumes (`followarr-data` and `followarr-logs`) by default to store the database and logs. These are managed by Docker and persist even if the container is removed.
*   **Tautulli Webhook:** Configure Tautulli to send webhook notifications to Followarr for new episodes (see details below).

#### Tautulli Webhook Setup

1.  In Tautulli **Settings** → **Notification Agents**.
2.  Click **Add a new notification agent** → **Webhook**.
3.  Configure the **Webhook URL**:
    *   If Followarr and Tautulli are on the **same Docker bridge network**: `http://followarr:3000/webhook/tautulli` (uses Docker DNS)
    *   If Followarr is on the host or different network: `http://<followarr_host_ip>:3000/webhook/tautulli` (replace `<followarr_host_ip>` with the IP address of the machine running Followarr).
4.  Under **Triggers**, select `Recently Added`.
5.  Under **Conditions**, you might want to add a condition like `Media Type is episode` to only trigger for TV shows.
6.  In the **Data** section under **Recently Added**:
    *   For JSON Headers:
        ```json
        {
            "Content-Type": "application/json"
        }
        ```
    *   For JSON Data:
        ```json
        {
            "event": "media.added",
            "media_type": "episode",
            "grandparent_title": "{show_name}",
            "parent_media_index": "{season_num}",
            "media_index": "{episode_num}",
            "title": "{episode_name}",
            "originally_available_at": "{air_date}",
            "summary": "{summary}"
        }
        ```
7.  Save the notification agent.

#### Docker Network (If Tautulli is also in Docker)

For Tautulli to reach Followarr using the `http://followarr:3000` URL, both containers must be on the same custom Docker network. Ensure your Tautulli `docker-compose.yml` connects it to the `followarr-net` network defined in Followarr's `docker-compose.yml`.

Example snippet for Tautulli's `docker-compose.yml`:
```yaml
services:
  tautulli:
    # ... other Tautulli config ...
    networks:
      - followarr-net # Add this line
      # - other_networks...

networks:
  followarr-net:
    external: true # Connect to the existing network created by Followarr
  # other_networks: ...
```
*Remember to restart Tautulli after modifying its compose file.* 

*   **Restart Followarr (e.g., after `.env` changes):**
    ```bash
    # Navigate to your followarr directory
    docker compose restart followarr
    ```
*   **View Volume Data (Advanced):** You can inspect the data stored in the named volumes using Docker commands if needed (e.g., `docker volume inspect followarr_followarr-data`).

## 🔧 Advanced Configuration

### Environment Variables

The bot requires several environment variables to be set in the `.env` file:

| Variable              | Description                                       | Required | Default Value                    |
|-----------------------|---------------------------------------------------|----------|----------------------------------|
| `DISCORD_BOT_TOKEN`   | Your Discord bot token                            | Yes      | -                                |
| `DISCORD_CHANNEL_ID`  | Discord channel ID for potential future updates   | Yes      | -                                |
| `TVDB_API_KEY`        | Your TVDB API key                                 | Yes      | -                                |
| `TAUTULLI_API_KEY`    | Your Tautulli API key                             | Yes      | -                                |
| `TAUTULLI_URL`        | URL of your Tautulli instance                     | Yes      | -                                |
| `DATABASE_URL`        | SQLite database URL                               | No       | `sqlite:///data/followarr.db`  |
| `WEBHOOK_SERVER_PORT` | Internal port for the webhook server              | No       | `3000`                           |
| `LOG_LEVEL`           | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) | No | `INFO` |
| `TZ`                  | Your timezone (e.g., `Europe/Belgrade`)             | No       | `UTC`                            |
| `UID`                 | User ID for Docker container process              | No       | `1000`                           |
| `GID`                 | Group ID for Docker container process             | No       | `1000`                           |

## 🤝 Support

- [GitHub Issues](https://github.com/d3v1l1989/Followarr/issues)

## Screenshots

Here are some screenshots of the bot in action:

### Calendar Command
<img src="docs/screenshots/calendar.png" alt="Calendar Command" width="300"/>

_View upcoming episodes for your followed shows_

### Follow Command
<img src="docs/screenshots/follow.png" alt="Follow Command" width="450"/>

_Follow a new TV show_

### Unfollow Command
<img src="docs/screenshots/unfollow.png" alt="Unfollow Command" width="450"/>

_Unfollow a TV show_

### List Command
<img src="docs/screenshots/list.png" alt="List Command" width="300"/>

_View all your followed shows_

### Episode Notification
<img src="docs/screenshots/notification.png" alt="Episode Notification" width="450"/>

_Receive notifications for new episodes_

## 👨‍💻 Development

### 🚀 Release Process (for Maintainers)

Followarr uses GitHub Actions to automatically build and publish Docker images to GitHub Container Registry (ghcr.io).

1. **Push to `main` branch:** Automatically builds and pushes the `ghcr.io/d3v1l1989/followarr:edge` image.
2. **Create and push a Git tag (e.g., `v1.0.1`):**
   ```bash
   git tag -a v1.0.1 -m "Release v1.0.1"
   git push origin v1.0.1
   ```
   This automatically builds and pushes the versioned image `ghcr.io/d3v1l1989/followarr:v1.0.1`.

Users can pull specific versions by changing the image tag in their `docker-compose.yml` (e.g., `ghcr.io/d3v1l1989/followarr:v1.0.1`).

### 🔄 Versioning

Followarr uses semantic versioning (MAJOR.MINOR.PATCH):
- MAJOR: Breaking changes
- MINOR: New features, backward compatible
- PATCH: Bug fixes, backward compatible

## 📸 Image Credits

- Followarr logo by PuksThePirate

## ☕ Support the Project

If you find Followarr useful and would like to support its development, you can buy me a coffee at [ko-fi.com/d3v1l1989](https://ko-fi.com/d3v1l1989). Your support helps keep the project maintained and free for everyone!

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.