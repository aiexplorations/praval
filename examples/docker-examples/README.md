# Praval Containerized Examples

This directory contains production-ready containerized examples that demonstrate Praval's capabilities with external services and infrastructure.

## Available Examples

### 005-memory-agents
**Memory-Enabled Agents with Qdrant Vector Database**

Demonstrates persistent agent memory using Qdrant vector storage for knowledge retention across interactions.

**Services:**
- Qdrant vector database for long-term memory
- Praval agents with memory persistence
- Health monitoring and logging

**Run:**
```bash
cd 005-memory-agents
docker-compose up
```

**Features:**
- 🧠 Persistent memory across agent sessions
- 📊 Knowledge accumulation and pattern recognition
- 🔄 Multi-agent memory sharing
- 🎯 Learning adaptation based on memory
- 📈 Memory analytics and insights

---

### 010-unified-storage
**Unified Storage System with Multiple Backends**

Complete demonstration of Praval's unified storage capabilities with PostgreSQL, Redis, MinIO S3, and Qdrant.

**Services:**
- PostgreSQL (relational data)
- Redis (caching and key-value)
- MinIO (S3-compatible object storage)
- Qdrant (vector search)
- Praval agents with storage integration

**Run:**
```bash
cd 010-unified-storage
docker-compose up
```

**Features:**
- 🗄️ Multi-backend storage (PostgreSQL, Redis, S3, Qdrant, FileSystem)
- 🤖 Multi-agent storage workflows
- 📊 Smart storage selection
- 📝 Cross-storage data operations
- 📈 Business analytics pipeline
- 🔄 Data references for efficient sharing

---

## Prerequisites

- Docker and Docker Compose
- Environment variables (copy from `.env.example`)

## Environment Configuration

Create a `.env` file in each example directory:

```bash
# Required for LLM-enabled agents
OPENAI_API_KEY=your_openai_key_here

# Optional: Custom configuration
PRAVAL_LOG_LEVEL=INFO
```

## Quick Start

1. **Choose an example:**
   ```bash
   cd examples/docker-examples/005-memory-agents
   # OR
   cd examples/docker-examples/010-unified-storage
   ```

2. **Set up environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Start the demo:**
   ```bash
   docker-compose up
   ```

4. **Monitor logs:**
   ```bash
   # In another terminal
   docker-compose logs -f praval-memory-demo
   # OR
   docker-compose logs -f praval-storage-demo
   ```

## Service Ports

### Memory Agents (005)
- **Qdrant**: http://localhost:6333 (vector database UI)
- **Praval App**: http://localhost:8080 (health check)

### Unified Storage (010)
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379  
- **MinIO S3**: http://localhost:9000 (admin UI: minioadmin/minioadmin)
- **Qdrant**: http://localhost:6333 (vector database UI)
- **Praval App**: http://localhost:8081 (health check)

## Monitoring and Debugging

### View Application Logs
```bash
# Real-time logs
docker-compose logs -f <service-name>

# Stored logs
docker exec <container-id> cat /app/logs/praval-memory.log
docker exec <container-id> cat /app/logs/praval-storage.log
```

### Inspect Storage Data

**PostgreSQL:**
```bash
docker exec -it <postgres-container> psql -U praval -d praval
```

**Redis:**
```bash  
docker exec -it <redis-container> redis-cli
```

**MinIO S3:**
Visit http://localhost:9000 (login: minioadmin/minioadmin)

**Qdrant:**
Visit http://localhost:6333/dashboard

**FileSystem:**
```bash
docker exec <container> ls -la /app/storage/
```

## Architecture

### Memory Agents Architecture
```
┌─────────────────────────────────────┐
│           Praval Agents             │
│  (Learning, Teaching, Reflection)   │
├─────────────────────────────────────┤
│         Memory Manager              │
│   (Short-term + Long-term)          │
├─────────────────────────────────────┤
│        Qdrant Vector DB             │
│     (Persistent Memory)             │
└─────────────────────────────────────┘
```

### Unified Storage Architecture
```
┌─────────────────────────────────────────────────────────┐
│                  Praval Agents                          │
│     (Collector, Analyst, Reporter)                     │
├─────────────────────────────────────────────────────────┤
│               Storage Registry                          │
├─────────────────────────────────────────────────────────┤
│ PostgreSQL │  Redis  │  MinIO  │ Qdrant │ FileSystem │
│(Relational)│(Cache)  │(Objects)│(Vector)│  (Files)   │
└─────────────────────────────────────────────────────────┘
```

## Development

### Adding New Examples

1. **Create directory structure:**
   ```bash
   mkdir examples/docker-examples/YOUR_EXAMPLE
   ```

2. **Required files:**
   - `docker-compose.yml` - Service definitions
   - `Dockerfile` - Application container
   - `run-YOUR_EXAMPLE.sh` - Entry point script  
   - `YOUR_EXAMPLE_containerized.py` - Enhanced example
   - `.env.example` - Environment template

3. **Follow patterns:**
   - Health checks for all services
   - Logging to `/app/logs/`
   - Environment-based configuration
   - Graceful error handling
   - Volume persistence for data

### Testing Examples

```bash
# Build without cache
docker-compose build --no-cache

# Run with specific services
docker-compose up postgres redis

# Clean up
docker-compose down -v  # Remove volumes too
```

## Troubleshooting

### Common Issues

**Service startup order:**
- Services have health checks and dependencies
- Allow 1-2 minutes for full stack startup
- Check logs: `docker-compose logs <service>`

**Port conflicts:**
- Modify port mappings in docker-compose.yml
- Check for existing services: `lsof -i :6333`

**Memory/disk space:**
- Ensure sufficient Docker resources
- Clean up: `docker system prune -a`

**API key issues:**
- Verify .env file exists and has correct keys
- Check environment: `docker exec <container> env | grep API`

### Getting Help

1. **Check logs:** `docker-compose logs -f`
2. **Inspect containers:** `docker exec -it <container> bash`
3. **Health checks:** Visit health endpoints
4. **GitHub Issues:** https://github.com/your-org/praval/issues

## Production Deployment

These examples are designed for development and demonstration. For production:

1. **Security:**
   - Use secrets management
   - Enable TLS/SSL
   - Network isolation
   - Access controls

2. **Scaling:**
   - Horizontal agent scaling
   - Load balancing
   - Database clustering
   - Monitoring

3. **Persistence:**
   - Named volumes
   - Backup strategies
   - Data retention policies

## Contributing

When adding new containerized examples:

1. Follow the established patterns
2. Include comprehensive documentation
3. Add environment templates
4. Test across platforms
5. Update this README

---

*These examples demonstrate Praval's production capabilities with real infrastructure components. They showcase how simple agents can collaborate to create sophisticated, persistent intelligent systems.*