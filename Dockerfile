# Finance Feedback Engine 2.0 - Production Dockerfile
FROM python:3.12-slim AS base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create app user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/data/decisions \
             /app/data/benchmarks \
             /app/data/refactoring \
             /app/data/optimization \
             /app/data/logs \
    && chown -R appuser:appuser /app

# Install package in editable mode
RUN pip install -e .

# Switch to non-root user
USER appuser

# Expose ports
# 8000: FastAPI application
# 9090: Prometheus metrics
EXPOSE 8000 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command: run API server
CMD ["uvicorn", "finance_feedback_engine.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
