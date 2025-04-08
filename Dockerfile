# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Define standard UID/GID for the app user
ARG UID=1000
ARG GID=1000

# Set the working directory in the container
WORKDIR /app

# Install system dependencies (if any) - uncomment if needed
# RUN apt-get update && apt-get install -y --no-install-recommends some-package && rm -rf /var/lib/apt/lists/*

# Create a non-root user and group first
RUN groupadd -g ${GID} appgroup && \
    useradd -u ${UID} -g appgroup -s /bin/sh -m appuser

# Create app directories 
RUN mkdir /app/data /app/logs

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
# Copy application code first, then set permissions
COPY --chown=appuser:appgroup . .

# Ensure the data and logs directories are owned by the appuser
# (Redundant if --chown works correctly, but explicit for safety)
RUN chown -R appuser:appgroup /app/data /app/logs

# Set environment variables
ENV PYTHONPATH=/app

# Switch to the non-root user
USER appuser

# Command to run the application
CMD ["python", "run.py"] 