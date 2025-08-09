# Multi-stage Dockerfile for Praval agents with memory capabilities

FROM python:3.11-slim as builder

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY pyproject.toml ./
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r praval && useradd -r -g praval praval

# Set working directory
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY src/ ./src/
COPY examples/ ./examples/

# Create necessary directories
RUN mkdir -p /app/logs /app/agent_states /app/data && \
    chown -R praval:praval /app

# Switch to non-root user
USER praval

# Environment variables
ENV PYTHONPATH=/app/src
ENV PRAVAL_LOG_LEVEL=INFO
ENV QDRANT_URL=http://localhost:6333

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from praval.memory import MemoryManager; m = MemoryManager(); print('healthy' if m.health_check()['short_term_memory'] else exit(1))"

# Default command (can be overridden)
CMD ["python", "-m", "praval.examples.memory_demo"]

# Labels for metadata
LABEL maintainer="Praval Team"
LABEL description="Praval AI Agents with Qdrant Memory Integration"
LABEL version="1.0.0"