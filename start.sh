#!/bin/bash

set -e

echo "=================================="
echo "WebStore Monitoring Example"
echo "=================================="
echo ""

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "Error: docker-compose is not installed"
    echo "Please install Docker and Docker Compose first"
    exit 1
fi

echo "Starting all services..."
docker-compose up -d

echo ""
echo "Waiting for services to be ready..."
sleep 5

# Wait for main service
echo -n "Waiting for main service..."
max_attempts=30
attempt=0
while ! curl -s http://localhost:8000/health > /dev/null 2>&1; do
    echo -n "."
    sleep 2
    attempt=$((attempt + 1))
    if [ $attempt -ge $max_attempts ]; then
        echo ""
        echo "Warning: Main service is taking longer than expected to start"
        break
    fi
done
echo " Ready!"

echo ""
echo "=================================="
echo "✓ Services are starting!"
echo "=================================="
echo ""
echo "Access the application:"
echo "  • WebStore Frontend:  http://localhost:3001"
echo "  • Main API:           http://localhost:8000"
echo "  • Grafana:            http://localhost:3000"
echo "  • Prometheus:         http://localhost:9090"
echo "  • Loki:               http://localhost:3100"
echo "  • Alertmanager:       http://localhost:9093"
echo "  • Pyroscope:          http://localhost:4040"
echo ""
echo "Authentication tokens (for API):"
echo "  • user-token-123"
echo "  • admin-token-456"
echo "  • test-token-789"
echo ""
echo "To generate traffic:"
echo "  cd scripts && python3 generate-traffic.py"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f"
echo ""
echo "To stop everything:"
echo "  docker-compose down"
echo ""
echo "For more commands, see README.md or run: make help"
echo "=================================="
