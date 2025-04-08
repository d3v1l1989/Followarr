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

# Copy .env.example to .env if it doesn't exist
if [ ! -f .env ]; then
    echo -e "\033[36m📝 Creating .env file from template...\033[0m"
    cp .env.example .env
    echo -e "\033[33m⚠️  Please edit the .env file with your configuration\033[0m"
    echo -e "\033[33m   You can do this now or later\033[0m"
    read -p "   Would you like to edit the .env file now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if command -v nano &> /dev/null; then
            echo "Opening .env file with nano..."
            nano .env
        elif command -v vim &> /dev/null; then
            echo "Opening .env file with vim..."
            vim .env
        else
            echo "❌ No suitable text editor found. Please edit .env manually."
        fi
    fi
else
    echo -e "\033[32m✅ .env file already exists\033[0m"
fi

# Ask if user wants to edit the .env file now
read -p "Would you like to edit the .env file now? (y/n): " edit_env
if [[ $edit_env == "y" || $edit_env == "Y" ]]; then
    # Check for common text editors
    if command -v nano &> /dev/null; then
        echo "Opening .env file with nano..."
        nano .env
    elif command -v vim &> /dev/null; then
        echo "Opening .env file with vim..."
        vim .env
    else
        echo "No common text editor found. Please edit the .env file manually."
        echo "You can use any text editor to edit the file at: $(pwd)/.env"
    fi
else
    echo "You can edit the .env file later using any text editor."
    echo "The file is located at: $(pwd)/.env"
fi

echo -e "\n\033[36m🐳 Building Docker image...\033[0m"
$DOCKER_COMPOSE_CMD build

echo -e "\033[36m🚀 Starting Followarr...\033[0m"
$DOCKER_COMPOSE_CMD up -d

# Check if the container is running
if [ "$(docker ps -q -f name=followarr)" ]; then
    echo "✅ Followarr is now running!"
    echo ""
    echo "📝 Next steps:"
    echo "1. Make sure your .env file is properly configured with your Discord bot token, TVDB API key, and Tautulli settings"
    echo "2. If you edited the .env file, restart the container with: $DOCKER_COMPOSE_CMD restart"
    echo "3. Check the logs with: $DOCKER_COMPOSE_CMD logs -f"
    echo ""
    echo "🔗 For more information, visit: https://github.com/d3v1l1989/Followarr"
else
    echo "❌ Failed to start Followarr. Check the logs with: $DOCKER_COMPOSE_CMD logs"
    exit 1
fi

echo
echo -e "\033[32m✅ Installation complete!\033[0m"
echo -e "\033[36m📝 Check the logs with: $DOCKER_COMPOSE_CMD logs -f\033[0m"
echo -e "\033[36m🛑 Stop the bot with: $DOCKER_COMPOSE_CMD down\033[0m"
echo
echo -e "\033[33m🔧 Don't forget to configure your Tautulli webhook!\033[0m"
echo -e "\033[33m   URL: http://followarr:3000/webhook/tautulli\033[0m" 