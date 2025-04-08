#!/bin/bash
# Followarr Installation Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Followarr installation...${NC}"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed.${NC}"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check for docker-compose or docker compose
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
else
    echo -e "${RED}Error: Neither docker-compose nor docker compose is available.${NC}"
    echo "Please install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

echo -e "\n\033[32m✅ Docker and Docker Compose are installed\033[0m\n"

# Create necessary directories
echo -e "\033[36m📁 Creating directories...\033[0m"
mkdir -p data logs config

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env file...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}Please edit the .env file with your configuration.${NC}"
    echo -e "${YELLOW}You can do this now or later by editing the .env file.${NC}"
    echo -e "${YELLOW}Required variables:${NC}"
    echo -e "  - DISCORD_BOT_TOKEN: Your Discord bot token"
    echo -e "  - DISCORD_CHANNEL_ID: Your Discord channel ID"
    echo -e "  - TVDB_API_KEY: Your TVDB API key"
    echo -e "  - TAUTULLI_URL: Your Tautulli server URL"
    echo -e "  - TAUTULLI_API_KEY: Your Tautulli API key"
    
    # Ask if user wants to edit .env now
    read -p "Do you want to edit the .env file now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if command -v nano &> /dev/null; then
            nano .env
        elif command -v vim &> /dev/null; then
            vim .env
        else
            echo -e "${YELLOW}No text editor found. Please edit .env manually.${NC}"
        fi
    else
        echo -e "${YELLOW}You can edit the .env file later.${NC}"
        echo -e "${YELLOW}The bot will check for required variables when it starts.${NC}"
    fi
fi

# Pull the latest image
echo -e "${GREEN}Pulling latest Followarr image...${NC}"
$DOCKER_COMPOSE_CMD pull

# Start the container
echo -e "${GREEN}Starting Followarr...${NC}"
$DOCKER_COMPOSE_CMD up -d

echo -e "${GREEN}Installation complete!${NC}"
echo -e "${YELLOW}If you haven't configured your .env file yet, please do so now.${NC}"
echo -e "${YELLOW}You can edit the .env file and then restart the bot with:${NC}"
echo -e "  $DOCKER_COMPOSE_CMD restart"
echo -e "${YELLOW}To view the logs:${NC}"
echo -e "  $DOCKER_COMPOSE_CMD logs -f"
echo -e "${YELLOW}To stop the bot:${NC}"
echo -e "  $DOCKER_COMPOSE_CMD down"

echo -e "\n\033[33m🔧 Don't forget to configure your Tautulli webhook!\033[0m"
echo -e "\033[33m   URL: http://followarr:3000/webhook/tautulli\033[0m" 