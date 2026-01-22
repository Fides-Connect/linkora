# Production Dockerfile for ai-assistant
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libssl-dev \
    pkg-config \
    libopus-dev \
    libvpx-dev \
    libsrtp2-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/secrets && \
    chown -R appuser:appuser /app

WORKDIR /app

# Copy pyproject and source for dependency caching and install package
COPY --chown=appuser:appuser pyproject.toml .
COPY --chown=appuser:appuser src/ ./src/
RUN pip install --no-cache-dir .

# Copy application source code
COPY --chown=appuser:appuser main.py .

# Switch to non-root user
USER appuser

# Expose WebRTC signaling port
EXPOSE 8080

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Run the application
CMD ["python", "main.py"]
