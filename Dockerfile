FROM python:3.11-slim

WORKDIR /app

# Create non-root user
RUN groupadd -r botuser && useradd -r -g botuser botuser

# Create necessary directories
RUN mkdir -p /app/data /app/logs && \
    chown -R botuser:botuser /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

# Switch to non-root user
USER botuser

CMD ["python", "src/bot.py"] 