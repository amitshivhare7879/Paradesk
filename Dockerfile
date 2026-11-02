# =============================================================================
# Paradesk Core Engine - Production Dockerfile
# Optimized for IIT Madras Paradox '27 Ground Operations Portal
# =============================================================================

FROM python:3.12-slim as base

# Set environment variables for Python in container
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000 \
    HOST=0.0.0.0

WORKDIR /app

# Install system utilities if needed for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first for caching layers
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source and templates
COPY app.py .
COPY templates/ ./templates/

# Create a non-root system user for security compliance
RUN useradd -m -u 10001 paradesk && \
    mkdir -p /app/data && \
    chown -R paradesk:paradesk /app

USER paradesk

# Default SQLite database path in container (can be mounted via volume)
ENV DB_PATH=/app/data/paradesk.db

EXPOSE 8000

# Docker Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start Uvicorn production server
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

