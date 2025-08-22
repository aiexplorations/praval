#!/bin/bash

# Complete Praval Unified Storage Demo
# ====================================
# This script orchestrates the entire demo from start to finish:
# 1. Sets up all Docker containers
# 2. Runs the Python agent demo
# 3. Shows live logs and results
# 4. Provides cleanup options

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}========================================${NC}"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Cleanup function
cleanup() {
    print_step "Cleaning up containers..."
    docker-compose down -v 2>/dev/null || true
    print_success "Cleanup completed"
}

# Trap to cleanup on exit
trap cleanup EXIT

print_header "PRAVAL UNIFIED STORAGE SYSTEM DEMO"
echo -e "${YELLOW}This demo showcases multi-agent collaboration with:${NC}"
echo "  🐘 PostgreSQL (relational data)"
echo "  📦 Redis (caching & key-value)"
echo "  🪣 MinIO S3 (object storage)"
echo "  🔍 Qdrant (vector database)"
echo "  📁 FileSystem (local files)"
echo ""

# Step 1: Environment Check
print_step "Checking environment and prerequisites..."

# Check if .env exists
if [ ! -f ".env" ]; then
    print_warning ".env file not found, creating from template..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_warning "Please edit .env file and add your OPENAI_API_KEY, then run this script again"
        exit 1
    else
        print_error ".env.example not found"
        exit 1
    fi
fi

# Check for API key
if ! grep -q "OPENAI_API_KEY=sk-" .env 2>/dev/null; then
    print_warning "OPENAI_API_KEY not configured in .env file"
    print_warning "Demo will still run but LLM features may be limited"
fi

# Check Docker
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed"
    exit 1
fi

print_success "Environment check passed"
echo ""

# Step 2: Clean up any existing containers
print_step "Cleaning up any existing containers..."
docker-compose down -v 2>/dev/null || true
print_success "Previous containers cleaned up"
echo ""

# Step 3: Start storage services
print_header "STARTING STORAGE SERVICES"
print_step "Starting PostgreSQL, Redis, MinIO, and Qdrant..."

echo "Starting services in the background..."
docker-compose up -d postgres redis minio qdrant

print_step "Waiting for services to be healthy..."

# Wait for PostgreSQL
echo -n "🐘 PostgreSQL: "
timeout=60
count=0
while ! docker-compose exec -T postgres pg_isready -U praval -d praval -q 2>/dev/null; do
    echo -n "."
    sleep 2
    count=$((count + 2))
    if [ $count -ge $timeout ]; then
        print_error "PostgreSQL startup timeout"
        exit 1
    fi
done
print_success "Ready!"

# Wait for Redis  
echo -n "📦 Redis: "
count=0
while ! docker-compose exec -T redis redis-cli ping | grep -q PONG 2>/dev/null; do
    echo -n "."
    sleep 2
    count=$((count + 2))
    if [ $count -ge $timeout ]; then
        print_error "Redis startup timeout"
        exit 1
    fi
done
print_success "Ready!"

# Wait for MinIO
echo -n "🪣 MinIO: "
count=0
while ! curl -sf http://localhost:9000/minio/health/live >/dev/null 2>&1; do
    echo -n "."
    sleep 2
    count=$((count + 2))
    if [ $count -ge $timeout ]; then
        print_error "MinIO startup timeout"
        exit 1
    fi
done
print_success "Ready!"

# Wait for Qdrant (use readiness endpoint)
echo -n "🔍 Qdrant: "
count=0
while ! curl -sf http://localhost:6333/readyz >/dev/null 2>&1; do
    echo -n "."
    sleep 2
    count=$((count + 2))
    if [ $count -ge $timeout ]; then
        print_error "Qdrant startup timeout"
        exit 1
    fi
done
print_success "Ready!"

# Initialize MinIO bucket
print_step "Initializing MinIO bucket..."
docker-compose up -d minio-init
sleep 5
print_success "MinIO bucket initialized"

echo ""
print_success "All storage services are running!"

# Show service status
print_step "Service endpoints:"
echo "  🐘 PostgreSQL: localhost:5432"
echo "  📦 Redis: localhost:6379"  
echo "  🪣 MinIO: http://localhost:9000 (admin: minioadmin/minioadmin)"
echo "  🔍 Qdrant: http://localhost:6333"
echo ""

# Step 4: Run the Python demo
print_header "RUNNING PRAVAL AGENTS DEMO"
print_step "Building and starting the Praval agent container..."

# Create a temporary script that runs Python and captures output
cat > /tmp/run_demo_with_logs.sh << 'EOF'
#!/bin/bash
echo "🚀 Starting Praval Unified Storage Agents..."
echo "============================================="

cd /app

# Run the Python demo and capture output
python3 unified_storage_containerized.py 2>&1 | tee /app/logs/demo-output.log

echo ""
echo "📋 Demo completed! Output saved to /app/logs/demo-output.log"
echo ""

# Show final storage statistics
echo "📊 FINAL STORAGE STATISTICS:"
echo "=============================="

# PostgreSQL stats
echo "🐘 PostgreSQL Data:"
psql -h postgres -U praval -d praval -c "SELECT 'Customers: ' || COUNT(*) FROM business.customers;" -t 2>/dev/null || echo "  Could not query PostgreSQL"
psql -h postgres -U praval -d praval -c "SELECT 'Activities: ' || COUNT(*) FROM business.agent_activities;" -t 2>/dev/null || echo "  Could not query activities"

# Redis stats  
echo "📦 Redis Data:"
redis-cli -h redis -p 6379 info keyspace | grep -E "db[0-9]:" || echo "  No Redis keys found"

# Filesystem stats
echo "📁 FileSystem Data:"
echo "  Files created: $(find /app/storage -type f | wc -l 2>/dev/null)"
echo "  Data files: $(ls /app/storage/data/ 2>/dev/null | wc -l)"
echo "  Reports: $(ls /app/storage/reports/ 2>/dev/null | wc -l)"

echo ""
echo "🎯 Key Demo Features Demonstrated:"
echo "✅ Multi-agent storage collaboration"
echo "✅ Cross-storage data operations"
echo "✅ Smart storage selection"
echo "✅ Data persistence and retrieval"
echo "✅ Business analytics pipeline"
echo ""
EOF

# Copy the script into the container and run it
docker-compose run --rm -v /tmp/run_demo_with_logs.sh:/tmp/run_demo.sh praval-storage-demo bash /tmp/run_demo.sh

# Step 5: Show results and logs
print_header "DEMO RESULTS AND LOGS"

print_step "Extracting logs from container..."
# Get the container logs
CONTAINER_ID=$(docker-compose ps -q praval-storage-demo 2>/dev/null | head -1)

if [ -n "$CONTAINER_ID" ]; then
    print_step "Container logs:"
    echo -e "${CYAN}--- START CONTAINER LOGS ---${NC}"
    docker logs $CONTAINER_ID 2>/dev/null | tail -50
    echo -e "${CYAN}--- END CONTAINER LOGS ---${NC}"
fi

# Show created files
print_step "Files created during demo:"
docker-compose run --rm praval-storage-demo find /app/storage -type f -exec ls -la {} \; 2>/dev/null | head -20

# Show database contents
print_step "Database contents:"
echo "🐘 PostgreSQL customers:"
docker-compose exec -T postgres psql -U praval -d praval -c "SELECT name, industry, revenue FROM business.customers LIMIT 5;" 2>/dev/null || print_warning "Could not query PostgreSQL"

echo ""
echo "📦 Redis keys:"
docker-compose exec -T redis redis-cli keys "*" 2>/dev/null | head -10 || print_warning "Could not query Redis"

# Step 6: Show access information
print_header "ACCESS INFORMATION"
echo "The demo services are still running. You can access:"
echo ""
echo "🔍 Service UIs:"
echo "  • MinIO S3 Console: http://localhost:9000 (minioadmin/minioadmin)"
echo "  • Qdrant Dashboard: http://localhost:6333/dashboard"
echo ""
echo "💻 Command Line Access:"
echo "  • PostgreSQL: docker-compose exec postgres psql -U praval -d praval"
echo "  • Redis: docker-compose exec redis redis-cli"
echo "  • Container Shell: docker-compose exec praval-storage-demo bash"
echo ""
echo "📁 View Generated Files:"
echo "  • docker-compose exec praval-storage-demo ls -la /app/storage/data/"
echo "  • docker-compose exec praval-storage-demo ls -la /app/storage/reports/"
echo "  • docker-compose exec praval-storage-demo cat /app/logs/demo-output.log"
echo ""

# Step 7: Cleanup prompt
echo -e "${YELLOW}Demo completed successfully!${NC}"
echo ""
read -p "Would you like to stop and remove all containers? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_step "Stopping and removing containers..."
    docker-compose down -v
    print_success "All containers and volumes removed"
else
    print_step "Containers left running for inspection"
    print_step "To stop later, run: docker-compose down -v"
fi

echo ""
print_success "Praval Unified Storage Demo completed!"

# Clean up temp file
rm -f /tmp/run_demo_with_logs.sh