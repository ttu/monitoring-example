.PHONY: help start stop restart logs clean traffic build install

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies locally (Python, Node.js, Go)
	@echo "Installing dependencies for all services..."
	@echo ""
	@echo "==> Installing Python dependencies (main-service)..."
	@cd services/main-service && pip install -r requirements.txt
	@echo ""
	@echo "==> Installing Node.js dependencies (external services)..."
	@cd services/external/payment-provider && npm install
	@cd services/external/crm-system && npm install
	@cd services/external/inventory-system && npm install
	@echo ""
	@echo "==> Installing Go dependencies (payments-service)..."
	@cd services/payments-service && go mod download
	@echo ""
	@echo "==> Installing .NET dependencies (promotions-service)..."
	@cd services/promotions-service && dotnet restore
	@echo ""
	@echo "==> Installing frontend dependencies..."
	@cd frontend && npm install
	@echo ""
	@echo "==> Installing traffic generator dependencies..."
	@pip install requests
	@echo ""
	@echo "✅ All dependencies installed successfully!"
	@echo ""
	@echo "You can now run services locally or use 'make start' for Docker."

start: ## Start all services
	docker-compose up -d
	@echo ""
	@echo "Services starting... Please wait 2-3 minutes for all services to be ready."
	@echo ""
	@echo "Access points:"
	@echo "  - WebStore Frontend: http://localhost:3001"
	@echo "  - Main API: http://localhost:8000"
	@echo "  - Grafana: http://localhost:3000"
	@echo "  - Prometheus: http://localhost:9090"
	@echo "  - Loki: http://localhost:3100"
	@echo "  - Alertmanager: http://localhost:9093"
	@echo "  - Pyroscope: http://localhost:4040"
	@echo ""

stop: ## Stop all services
	docker-compose down

restart: ## Restart all services
	docker-compose restart

logs: ## Show logs from all services
	docker-compose logs -f

logs-main: ## Show logs from main service
	docker-compose logs -f main-service

logs-payments: ## Show logs from payments service
	docker-compose logs -f payments-service

logs-promotions: ## Show logs from promotions service
	docker-compose logs -f promotions-service

logs-otel: ## Show logs from OpenTelemetry Collector
	docker-compose logs -f otel-collector

clean: ## Stop services and remove volumes
	docker-compose down -v
	@echo "All services stopped and data volumes removed"

build: ## Rebuild all services
	docker-compose build

rebuild: ## Rebuild and restart all services
	docker-compose up -d --build

traffic: ## Generate traffic (requires Python)
	@cd scripts && python3 generate-traffic.py --users 5 --duration 60

traffic-heavy: ## Generate heavy traffic
	@cd scripts && python3 generate-traffic.py --users 20 --duration 120

traffic-continuous: ## Start continuous traffic generation (Ctrl+C to stop)
	@cd scripts && python3 continuous-traffic.py

status: ## Show status of all services
	docker-compose ps

health: ## Check health of all services
	@echo "Checking service health..."
	@curl -s http://localhost:8000/health | jq . || echo "Main service not ready"
	@curl -s http://localhost:8081/health | jq . || echo "Payments service not ready"
	@curl -s http://localhost:8082/api/promotions/health | jq . || echo "Promotions service not ready"
	@curl -s http://localhost:3001/health | jq . || echo "Payment provider not ready"
	@curl -s http://localhost:3002/health | jq . || echo "CRM system not ready"
	@curl -s http://localhost:3003/health | jq . || echo "Inventory system not ready"
