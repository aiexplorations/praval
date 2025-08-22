FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -e .

# Install additional dependencies for storage demo
RUN pip install --no-cache-dir \
    asyncpg \
    redis \
    boto3 \
    qdrant-client \
    psycopg2-binary \
    python-dotenv \
    requests

# Create required directories
RUN mkdir -p /app/logs /app/storage

# Copy demo scripts and make executable
COPY examples/docker-examples/010-unified-storage/run-storage-demo.sh /app/run-storage-demo.sh
RUN chmod +x /app/run-storage-demo.sh

# Copy the containerized storage demo
COPY examples/docker-examples/010-unified-storage/unified_storage_containerized.py /app/unified_storage_containerized.py

# Expose port for health checks
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# Default command
CMD ["./run-storage-demo.sh"]