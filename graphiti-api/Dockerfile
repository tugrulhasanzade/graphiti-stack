# Python slim image (no external dependencies needed)
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Create non-root user (security best practice)
RUN useradd -m -u 1000 graphiti && \
    chown -R graphiti:graphiti /app

# Copy requirements first for layer caching
COPY --chown=graphiti:graphiti requirements.txt .

# Install Python dependencies (no build tools needed for pure Python packages)
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=graphiti:graphiti . .

# Switch to non-root user
USER graphiti

# Health check endpoint using Python (no curl needed)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

# Expose port (documentation only, Coolify handles actual exposure)
EXPOSE 8000

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
