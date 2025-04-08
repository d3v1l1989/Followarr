#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if version argument is provided
if [ -z "$1" ]; then
    echo -e "${RED}Error: Version number is required${NC}"
    echo "Usage: ./release.sh <version>"
    echo "Example: ./release.sh 1.0.1"
    exit 1
fi

VERSION=$1

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed.${NC}"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo -e "${RED}Error: Git is not installed.${NC}"
    echo "Please install Git first: https://git-scm.com/downloads"
    exit 1
fi

# Check if we're in a git repository
if [ ! -d .git ]; then
    echo -e "${RED}Error: Not a git repository.${NC}"
    echo "Please run this script from the root of the Followarr repository."
    exit 1
fi

# Check if there are uncommitted changes
if [ -n "$(git status --porcelain)" ]; then
    echo -e "${RED}Error: You have uncommitted changes.${NC}"
    echo "Please commit or stash your changes before releasing."
    exit 1
fi

# Create git tag
echo -e "${GREEN}Creating git tag v${VERSION}...${NC}"
git tag -a "v${VERSION}" -m "Release v${VERSION}"
git push origin "v${VERSION}"

# Build Docker images
echo -e "${GREEN}Building Docker images...${NC}"
docker build -t "d3v1l1989/followarr:${VERSION}" .
docker tag "d3v1l1989/followarr:${VERSION}" d3v1l1989/followarr:latest

# Push Docker images
echo -e "${GREEN}Pushing Docker images...${NC}"
docker push "d3v1l1989/followarr:${VERSION}"
docker push d3v1l1989/followarr:latest

echo -e "\n${GREEN}Release v${VERSION} completed successfully!${NC}"
echo -e "${YELLOW}Users can update by running:${NC}"
echo "  docker compose pull"
echo "  docker compose up -d" 