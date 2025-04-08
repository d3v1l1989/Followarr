# Colors for output
$Red = [System.ConsoleColor]::Red
$Green = [System.ConsoleColor]::Green
$Yellow = [System.ConsoleColor]::Yellow

Write-Host "Starting Followarr installation..." -ForegroundColor $Green

# Check if Docker is installed
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Docker is not installed." -ForegroundColor $Red
    Write-Host "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
}

# Check for docker-compose or docker compose
$DOCKER_COMPOSE_CMD = ""
if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
    $DOCKER_COMPOSE_CMD = "docker-compose"
} elseif (docker compose version 2>$null) {
    $DOCKER_COMPOSE_CMD = "docker compose"
} else {
    Write-Host "Error: Neither docker-compose nor docker compose is available." -ForegroundColor $Red
    Write-Host "Please install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
}

# Create necessary directories
New-Item -ItemType Directory -Force -Path data, logs | Out-Null

# Create .env file if it doesn't exist
if (-not (Test-Path .env)) {
    Write-Host "Creating .env file..." -ForegroundColor $Yellow
    Copy-Item .env.example .env
    Write-Host "Please edit the .env file with your configuration." -ForegroundColor $Yellow
    Write-Host "You can do this now or later by editing the .env file." -ForegroundColor $Yellow
    Write-Host "Required variables:" -ForegroundColor $Yellow
    Write-Host "  - DISCORD_BOT_TOKEN: Your Discord bot token"
    Write-Host "  - DISCORD_CHANNEL_ID: Your Discord channel ID"
    Write-Host "  - TVDB_API_KEY: Your TVDB API key"
    Write-Host "  - TAUTULLI_URL: Your Tautulli server URL"
    Write-Host "  - TAUTULLI_API_KEY: Your Tautulli API key"
    
    # Ask if user wants to edit .env now
    $response = Read-Host "Do you want to edit the .env file now? (y/n)"
    if ($response -eq 'y') {
        notepad .env
    } else {
        Write-Host "You can edit the .env file later." -ForegroundColor $Yellow
        Write-Host "The bot will check for required variables when it starts." -ForegroundColor $Yellow
    }
}

# Pull the latest image
Write-Host "Pulling latest Followarr image..." -ForegroundColor $Green
Invoke-Expression "$DOCKER_COMPOSE_CMD pull"

# Start the container
Write-Host "Starting Followarr..." -ForegroundColor $Green
Invoke-Expression "$DOCKER_COMPOSE_CMD up -d"

Write-Host "Installation complete!" -ForegroundColor $Green
Write-Host "If you haven't configured your .env file yet, please do so now." -ForegroundColor $Yellow
Write-Host "You can edit the .env file and then restart the bot with:" -ForegroundColor $Yellow
Write-Host "  $DOCKER_COMPOSE_CMD restart"
Write-Host "To view the logs:" -ForegroundColor $Yellow
Write-Host "  $DOCKER_COMPOSE_CMD logs -f"
Write-Host "To stop the bot:" -ForegroundColor $Yellow
Write-Host "  $DOCKER_COMPOSE_CMD down"

Write-Host "`nDon't forget to configure your Tautulli webhook!" -ForegroundColor $Yellow
Write-Host "  URL: http://followarr:3000/webhook/tautulli" -ForegroundColor $Yellow 