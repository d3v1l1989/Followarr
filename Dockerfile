FROM python:3.11-slim

WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libffi-dev && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r botuser && useradd -r -g botuser botuser

# Create necessary directories
RUN mkdir -p /app/data /app/logs && \
    chown -R botuser:botuser /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the source files
COPY src/*.py .

# Switch to non-root user
USER botuser

# Run the bot
CMD ["python", "bot.py"] 