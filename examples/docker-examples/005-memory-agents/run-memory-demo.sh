#!/bin/bash

# Praval Memory Agents Containerized Demo
# =======================================

set -e

echo "🧠 Starting Praval Memory Agents Demo with Qdrant"
echo "=================================================="

# Health check endpoint (simple HTTP server for Docker health check)
python3 -c "
import http.server
import socketserver
import threading
import time

class HealthHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{\"status\": \"healthy\", \"service\": \"praval-memory-demo\"}')
        else:
            self.send_response(404)
            self.end_headers()

def start_health_server():
    with socketserver.TCPServer(('', 8080), HealthHandler) as httpd:
        httpd.serve_forever()

# Start health check server in background
health_thread = threading.Thread(target=start_health_server, daemon=True)
health_thread.start()
print('🏥 Health check server started on port 8080')

# Small delay to ensure health server is ready
time.sleep(2)
" &

# Wait for Qdrant to be ready
echo "⏳ Waiting for Qdrant to be ready..."
while ! curl -f http://qdrant:6333/health > /dev/null 2>&1; do
    echo "   Qdrant not ready yet, waiting 5 seconds..."
    sleep 5
done

echo "✅ Qdrant is ready!"

# Display environment info
echo "🔧 Environment Configuration:"
echo "   Qdrant URL: ${QDRANT_URL}"
echo "   Collection: ${QDRANT_COLLECTION_NAME}"
echo "   OpenAI API: $([ -n "${OPENAI_API_KEY}" ] && echo "Configured" || echo "Not configured")"

# Create logs directory if it doesn't exist
mkdir -p /app/logs

# Start the memory agents demo
echo ""
echo "🚀 Starting Memory-Enabled Agents..."
echo "====================================="

# Run the memory demo with enhanced logging
python3 memory_agents_containerized.py 2>&1 | tee /app/logs/memory-demo.log

echo ""
echo "🎉 Demo completed!"
echo "📁 Logs saved to: /app/logs/memory-demo.log"

# Keep container running for inspection
echo "💡 Container will stay running for 5 minutes for log inspection..."
echo "   Access logs with: docker exec <container_id> cat /app/logs/memory-demo.log"
echo "   Or use: docker-compose logs praval-memory-demo"

sleep 300