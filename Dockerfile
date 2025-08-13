# Multi-stage Dockerfile for Harris County Property Lookup Tool
# This provides flexibility for different deployment scenarios

# ============================================
# Stage 1: Data Builder (Optional)
# Use this stage to download and process data
# ============================================
FROM python:3.13-slim AS data-builder

# Install system dependencies for data processing
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy data processing scripts
COPY download_extract.py .
COPY extract_data.py .

# Create necessary directories
RUN mkdir -p downloads extracted data text_files

# Download and process data (this takes ~10 minutes)
# Comment out these lines if you want to mount data as volume instead
# RUN python download_extract.py
# RUN python extract_data.py

# ============================================
# Stage 2: Runtime Environment
# ============================================
FROM python:3.13-slim AS runtime

# Install system dependencies
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# Create app user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY extract_data.py .
COPY run.py .
COPY docker_run.py .
COPY test_docker.py .
COPY templates/ templates/
COPY static/ static/

# Copy enhancement scripts (optional)
COPY add_property_ratings.py .
COPY add_residential_estimates.py .
COPY add_simple_ratings.py .

# Create necessary directories with proper permissions
RUN mkdir -p data downloads extracted Exports logs text_files && \
    chown -R appuser:appuser /app

# Copy database from builder stage (if built during Docker build)
# COPY --from=data-builder /app/data/database.sqlite data/

# Switch to non-root user
USER appuser

# Environment variables
ENV PYTHONPATH=/app
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000', timeout=5)" || exit 1

# Default command
CMD ["python", "docker_run.py"]
