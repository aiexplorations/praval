FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -e .

# Install additional dependencies for memory system
RUN pip install --no-cache-dir \
    qdrant-client \
    sentence-transformers \
    python-dotenv

# Create logs directory
RUN mkdir -p /app/logs

# Copy the demo script and make it executable
COPY examples/docker-examples/005-memory-agents/run-memory-demo.sh /app/run-memory-demo.sh
RUN chmod +x /app/run-memory-demo.sh

# Copy the enhanced example
COPY examples/docker-examples/005-memory-agents/memory_agents_containerized.py /app/memory_agents_containerized.py

# Expose port for monitoring/health checks
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# Default command
CMD ["./run-memory-demo.sh"]