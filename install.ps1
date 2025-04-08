# Followarr Installation Script for Windows
Write-Host "🚀 Followarr Installation Script" -ForegroundColor Cyan
Write-Host "================================`n"

# Check if Docker is installed
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Docker is not installed. Please install Docker first." -ForegroundColor Red
    Write-Host "Visit https://docs.docker.com/get-docker/ for installation instructions." -ForegroundColor Yellow
    exit 1
}

# Check for Docker Compose (both formats)
$dockerComposeCmd = $null
try {
    # First try docker compose subcommand
    $null = docker compose version 2>&1
    $dockerComposeCmd = "docker compose"
    Write-Host "✅ Using Docker Compose V2 (docker compose)" -ForegroundColor Green
} catch {
    try {
        # Then try docker-compose command
        $null = docker-compose --version 2>&1
        $dockerComposeCmd = "docker-compose"
        Write-Host "✅ Using Docker Compose V1 (docker-compose)" -ForegroundColor Green
    } catch {
        Write-Host "❌ Docker Compose is not installed. Please install Docker Compose first." -ForegroundColor Red
        Write-Host "Visit https://docs.docker.com/compose/install/ for installation instructions." -ForegroundColor Yellow
        exit 1
    }
}

Write-Host "`n✅ Docker and Docker Compose are installed`n" -ForegroundColor Green

# Create necessary directories
Write-Host "📁 Creating directories..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path data, logs, config | Out-Null

# Handle .env file
$envEdited = $false
if (-not (Test-Path .env)) {
    Write-Host "📝 Creating .env file from template..." -ForegroundColor Cyan
    Copy-Item .env.example .env
    Write-Host "⚠️  Please edit the .env file with your configuration" -ForegroundColor Yellow
    $editNow = Read-Host "   Would you like to edit the .env file now? (y/n)"
    if ($editNow -eq 'y') {
        notepad .env
        $envEdited = $true
    }
} else {
    Write-Host "✅ .env file already exists" -ForegroundColor Green
    # Check if .env is using default values
    $envContent = Get-Content .env -Raw
    if ($envContent -match "your_discord_bot_token_here" -or $envContent -match "your_tvdb_api_key_here") {
        Write-Host "⚠️  Your .env file contains default values that need to be updated" -ForegroundColor Yellow
        $editNow = Read-Host "   Would you like to edit the .env file now? (y/n)"
        if ($editNow -eq 'y') {
            notepad .env
            $envEdited = $true
        }
    }
}

# Only proceed with Docker operations if .env is properly configured
$envContent = Get-Content .env -Raw
if ($envEdited -or (-not ($envContent -match "your_discord_bot_token_here") -and -not ($envContent -match "your_tvdb_api_key_here"))) {
    Write-Host "`n🐳 Building Docker image..." -ForegroundColor Cyan
    Invoke-Expression "$dockerComposeCmd build"

    Write-Host "🚀 Starting Followarr..." -ForegroundColor Cyan
    Invoke-Expression "$dockerComposeCmd up -d"

    Write-Host "`n✅ Installation complete!" -ForegroundColor Green
    Write-Host "📝 Check the logs with: $dockerComposeCmd logs -f" -ForegroundColor Cyan
    Write-Host "🛑 Stop the bot with: $dockerComposeCmd down" -ForegroundColor Cyan
    Write-Host "`n🔧 Don't forget to configure your Tautulli webhook!" -ForegroundColor Yellow
    Write-Host "   URL: http://followarr:3000/webhook/tautulli" -ForegroundColor Yellow
} else {
    Write-Host "`n❌ Installation aborted. Please configure your .env file before proceeding." -ForegroundColor Red
    exit 1
} 