# Followarr Release Script for Windows
param(
    [Parameter(Mandatory=$true)]
    [string]$Version
)

# Colors for output
$Red = [System.ConsoleColor]::Red
$Green = [System.ConsoleColor]::Green
$Yellow = [System.ConsoleColor]::Yellow

# Function to check if a command exists
function Test-Command($cmd) {
    return [bool](Get-Command -Name $cmd -ErrorAction SilentlyContinue)
}

# Check if Docker is installed
if (-not (Test-Command docker)) {
    Write-Host "Error: Docker is not installed." -ForegroundColor $Red
    Write-Host "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
}

# Check if git is installed
if (-not (Test-Command git)) {
    Write-Host "Error: Git is not installed." -ForegroundColor $Red
    Write-Host "Please install Git first: https://git-scm.com/downloads"
    exit 1
}

# Check if we're in a git repository
if (-not (Test-Path .git)) {
    Write-Host "Error: Not a git repository." -ForegroundColor $Red
    Write-Host "Please run this script from the root of the Followarr repository."
    exit 1
}

# Check if there are uncommitted changes
$status = git status --porcelain
if ($status) {
    Write-Host "Error: You have uncommitted changes." -ForegroundColor $Red
    Write-Host "Please commit or stash your changes before releasing."
    exit 1
}

# Create git tag
Write-Host "Creating git tag v$Version..." -ForegroundColor $Green
git tag -a "v$Version" -m "Release v$Version"
git push origin "v$Version"

# Build Docker images
Write-Host "Building Docker images..." -ForegroundColor $Green
docker build -t "d3v1l1989/followarr:$Version" .
docker tag "d3v1l1989/followarr:$Version" d3v1l1989/followarr:latest

# Push Docker images
Write-Host "Pushing Docker images..." -ForegroundColor $Green
docker push "d3v1l1989/followarr:$Version"
docker push d3v1l1989/followarr:latest

Write-Host "`nRelease v$Version completed successfully!" -ForegroundColor $Green
Write-Host "Users can update by running:" -ForegroundColor $Yellow
Write-Host "  docker compose pull"
Write-Host "  docker compose up -d" 