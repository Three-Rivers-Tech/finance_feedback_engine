# Finance Feedback Engine 2.0 - Production Dockerfile
# Multi-stage build for optimized image size and security

# =============================================================================
# Stage 1: Builder - Compile dependencies and install packages
# =============================================================================
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first for better layer caching
COPY pyproject.toml setup.py ./
COPY finance_feedback_engine/__init__.py finance_feedback_engine/__init__.py

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install package dependencies without the package itself
RUN pip install --upgrade pip setuptools wheel && \
    pip install -e . --no-deps

# Copy full application code
COPY . .

# Install the package in editable mode
RUN pip install -e .

# =============================================================================
# Stage 2: Runtime - Minimal production image
# =============================================================================
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Install only runtime dependencies (curl for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy application code from builder
COPY --from=builder /build /app

# Create necessary directories with proper permissions
RUN mkdir -p /app/data/decisions \
             /app/data/benchmarks \
             /app/data/refactoring \
             /app/data/optimization \
             /app/data/logs \
             /app/data/cache \
             /app/data/memory \
    && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose ports
# 8000: FastAPI application
# 9090: Prometheus metrics (served by FastAPI)
EXPOSE 8000 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command: run API server
# Use --workers 1 for single-instance (SQLite limitation)
CMD ["uvicorn", "finance_feedback_engine.api.app:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--log-level", "info"]
