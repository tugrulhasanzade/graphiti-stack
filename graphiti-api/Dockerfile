# Multi-stage build for smaller image
FROM python:3.11-slim AS builder

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

# Create non-root user (security best practice)
RUN useradd -m -u 1000 graphiti && \
    mkdir -p /app && \
    chown -R graphiti:graphiti /app

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder --chown=graphiti:graphiti /root/.local /home/graphiti/.local

# Copy application code
COPY --chown=graphiti:graphiti . .

# Set PATH to include user packages
ENV PATH=/home/graphiti/.local/bin:$PATH

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port (documentation only, Coolify handles actual exposure)
EXPOSE 8000

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
