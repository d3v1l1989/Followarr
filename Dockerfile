FROM python:3.11-slim

# Define standard UID/GID for the app user, matching common practice and compose default
ARG UID=1000
ARG GID=1000

# Create group and user with specified/default UID/GID first
# Create the group with the specified GID
RUN if getent group ${GID}; then echo "Group ${GID} exists"; else groupadd -g ${GID} appgroup; fi && \
    # Create the user with the specified UID and GID, creating home directory
    useradd --system --create-home --uid ${UID} --gid ${GID} appuser

# Install system dependencies including SQLite and build tools in one layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    libsqlite3-0 \
    gcc \
    python3-dev \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY --chown=appuser:appgroup requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY --chown=appuser:appgroup . .

# Create/ensure ownership of data and logs directories (even though named volumes are used,
# internal permissions within the container base layer matter for the mount point)
RUN mkdir -p /app/data /app/logs && \
    chown -R appuser:appgroup /app/data /app/logs

# Set environment variables
ENV PYTHONPATH=/app

# Switch to the non-root user
USER appuser

# Command to run the application
CMD ["python", "run.py"] 