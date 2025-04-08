# Followarr Installation Script for Windows
Write-Host "🚀 Followarr Installation Script" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is installed
try {
    $dockerVersion = docker --version
    Write-Host "✅ Docker is installed: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker is not installed. Please install Docker Desktop for Windows first." -ForegroundColor Red
    Write-Host "Visit https://docs.docker.com/desktop/windows/install/ for installation instructions." -ForegroundColor Yellow
    exit 1
}

# Check if Docker Compose is installed
try {
    $composeVersion = docker-compose --version
    Write-Host "✅ Docker Compose is installed: $composeVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker Compose is not installed. Please install Docker Desktop for Windows first." -ForegroundColor Red
    Write-Host "Visit https://docs.docker.com/desktop/windows/install/ for installation instructions." -ForegroundColor Yellow
    exit 1
}

# Create necessary directories
Write-Host "📁 Creating necessary directories..." -ForegroundColor Cyan
if (-not (Test-Path -Path "data")) { New-Item -ItemType Directory -Path "data" | Out-Null }
if (-not (Test-Path -Path "logs")) { New-Item -ItemType Directory -Path "logs" | Out-Null }
if (-not (Test-Path -Path "config")) { New-Item -ItemType Directory -Path "config" | Out-Null }

# Check if .env file exists
if (-not (Test-Path -Path ".env")) {
    Write-Host "📝 Creating .env file from template..." -ForegroundColor Cyan
    if (Test-Path -Path ".env.example") {
        Copy-Item -Path ".env.example" -Destination ".env"
        Write-Host "✅ Created .env file. Please edit it with your configuration." -ForegroundColor Green
    } else {
        Write-Host "❌ .env.example file not found. Please create a .env file manually." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "✅ .env file already exists." -ForegroundColor Green
}

# Pull the Docker image
Write-Host "🐳 Pulling Followarr Docker image..." -ForegroundColor Cyan
docker-compose pull

# Start the container
Write-Host "🚀 Starting Followarr..." -ForegroundColor Cyan
docker-compose up -d

# Check if the container is running
$containerRunning = docker ps -q -f name=followarr
if ($containerRunning) {
    Write-Host "✅ Followarr is now running!" -ForegroundColor Green
    Write-Host ""
    Write-Host "📝 Next steps:" -ForegroundColor Cyan
    Write-Host "1. Edit the .env file with your Discord bot token, TVDB API key, and Tautulli settings" -ForegroundColor Yellow
    Write-Host "2. Restart the container with: docker-compose restart" -ForegroundColor Yellow
    Write-Host "3. Check the logs with: docker-compose logs -f" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "🔗 For more information, visit: https://github.com/d3v1l1989/Followarr" -ForegroundColor Cyan
} else {
    Write-Host "❌ Failed to start Followarr. Check the logs with: docker-compose logs" -ForegroundColor Red
    exit 1
} 