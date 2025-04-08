#!/bin/bash
# Followarr Installation Script

set -e

echo "🚀 Followarr Installation Script"
echo "================================"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    echo "Visit https://docs.docker.com/get-docker/ for installation instructions."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    echo "Visit https://docs.docker.com/compose/install/ for installation instructions."
    exit 1
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p data logs config

# Check if .env file exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✅ Created .env file. Please edit it with your configuration."
    else
        echo "❌ .env.example file not found. Please create a .env file manually."
        exit 1
    fi
else
    echo "✅ .env file already exists."
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

# Pull the Docker image
echo "🐳 Pulling Followarr Docker image..."
docker-compose pull

# Start the container
echo "🚀 Starting Followarr..."
docker-compose up -d

# Check if the container is running
if [ "$(docker ps -q -f name=followarr)" ]; then
    echo "✅ Followarr is now running!"
    echo ""
    echo "📝 Next steps:"
    echo "1. Make sure your .env file is properly configured with your Discord bot token, TVDB API key, and Tautulli settings"
    echo "2. If you edited the .env file, restart the container with: docker-compose restart"
    echo "3. Check the logs with: docker-compose logs -f"
    echo ""
    echo "🔗 For more information, visit: https://github.com/d3v1l1989/Followarr"
else
    echo "❌ Failed to start Followarr. Check the logs with: docker-compose logs"
    exit 1
fi 