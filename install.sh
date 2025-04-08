#!/bin/bash
# Followarr Installation Script

set -e

echo -e "\033[36m🚀 Followarr Installation Script\033[0m"
echo -e "\033[36m================================\033[0m\n"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "\033[31m❌ Docker is not installed. Please install Docker first.\033[0m"
    echo -e "\033[33mVisit https://docs.docker.com/get-docker/ for installation instructions.\033[0m"
    exit 1
fi

# Check for Docker Compose (both formats)
DOCKER_COMPOSE_CMD=""
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
    echo -e "\033[32m✅ Using Docker Compose V2 (docker compose)\033[0m"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
    echo -e "\033[32m✅ Using Docker Compose V1 (docker-compose)\033[0m"
else
    echo -e "\033[31m❌ Docker Compose is not installed. Please install Docker Compose first.\033[0m"
    echo -e "\033[33mVisit https://docs.docker.com/compose/install/ for installation instructions.\033[0m"
    exit 1
fi

echo -e "\n\033[32m✅ Docker and Docker Compose are installed\033[0m\n"

# Create necessary directories
echo -e "\033[36m📁 Creating directories...\033[0m"
mkdir -p data logs config

# Handle .env file
ENV_EDITED=false
if [ ! -f .env ]; then
    echo -e "\033[36m📝 Creating .env file from template...\033[0m"
    cp .env.example .env
    echo -e "\033[33m⚠️  Please edit the .env file with your configuration\033[0m"
    read -p "   Would you like to edit the .env file now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if command -v nano &> /dev/null; then
            nano .env
        else
            vi .env
        fi
        ENV_EDITED=true
    fi
else
    echo -e "\033[32m✅ .env file already exists\033[0m"
    # Check if .env is using default values
    if grep -q "your_discord_bot_token_here" .env || grep -q "your_tvdb_api_key_here" .env; then
        echo -e "\033[33m⚠️  Your .env file contains default values that need to be updated\033[0m"
        read -p "   Would you like to edit the .env file now? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            if command -v nano &> /dev/null; then
                nano .env
            else
                vi .env
            fi
            ENV_EDITED=true
        fi
    fi
fi

# Only proceed with Docker operations if .env is properly configured
if [ "$ENV_EDITED" = true ] || (! grep -q "your_discord_bot_token_here" .env && ! grep -q "your_tvdb_api_key_here" .env); then
    echo -e "\n\033[36m🐳 Building Docker image...\033[0m"
    $DOCKER_COMPOSE_CMD build

    echo -e "\033[36m🚀 Starting Followarr...\033[0m"
    $DOCKER_COMPOSE_CMD up -d

    echo -e "\n\033[32m✅ Installation complete!\033[0m"
    echo -e "\033[36m📝 Check the logs with: $DOCKER_COMPOSE_CMD logs -f\033[0m"
    echo -e "\033[36m🛑 Stop the bot with: $DOCKER_COMPOSE_CMD down\033[0m"
    echo -e "\n\033[33m🔧 Don't forget to configure your Tautulli webhook!\033[0m"
    echo -e "\033[33m   URL: http://followarr:3000/webhook/tautulli\033[0m"
else
    echo -e "\n\033[31m❌ Installation aborted. Please configure your .env file before proceeding.\033[0m"
    exit 1
fi 