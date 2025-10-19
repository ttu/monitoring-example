# Docker and Deployment

**Reading time**: 16 minutes

Learn how the monitoring example is containerized, configured, and deployed using Docker Compose with best practices for multi-language microservices.

## Table of Contents

- [Docker Compose Architecture](#docker-compose-architecture)
- [Multi-Stage Builds](#multi-stage-builds)
- [Environment Configuration](#environment-configuration)
- [Health Checks and Dependencies](#health-checks-and-dependencies)
- [Networking](#networking)
- [Volume Management](#volume-management)
- [Common Commands](#common-commands)

## Docker Compose Architecture

The project uses **Docker Compose** to orchestrate 15 containers across application services and observability infrastructure.

### Service Overview

**File**: `docker-compose.yml`

```yaml
version: '3.9'

services:
  # Infrastructure (3)
  - postgres          # Database
  - redis            # Cache
  - otel-collector   # Telemetry hub

  # Observability Stack (8)
  - prometheus       # Metrics storage
  - tempo            # Traces storage
  - loki             # Logs storage
  - pyroscope        # Profiling
  - alertmanager     # Alert routing
  - cadvisor         # Container metrics
  - grafana          # Visualization

  # Application Services (7)
  - main-service     # Python/FastAPI
  - payments-service # Go
  - promotions-service # C#/.NET
  - payment-provider # Node.js
  - crm-system       # Node.js
  - inventory-system # Node.js
  - frontend         # React
```

### Service Dependencies

The stack has a clear dependency hierarchy:

```
Level 1: Infrastructure
  ├─ postgres
  ├─ redis
  └─ otel-collector
      └─ depends on: prometheus, tempo, loki

Level 2: Observability
  ├─ prometheus
  ├─ tempo
  ├─ loki
  ├─ pyroscope
  └─ alertmanager

Level 3: Visualization
  └─ grafana
      └─ depends on: prometheus, tempo, loki, pyroscope

Level 4: Application Services
  ├─ main-service
  │   └─ depends on: postgres, redis, otel-collector
  ├─ payments-service
  │   └─ depends on: otel-collector
  ├─ promotions-service
  │   └─ depends on: otel-collector
  └─ external services
      └─ depend on: otel-collector

Level 5: Frontend
  └─ frontend
      └─ depends on: main-service
```

### Port Mapping

All services expose ports on localhost:

| Service | Port | Purpose |
|---------|------|---------|
| **Application** | | |
| frontend | 3001 | React UI |
| main-service | 8000 | FastAPI REST API |
| payments-service | 8081 | Go payment API |
| promotions-service | 8082 | C# promotions API |
| **Infrastructure** | | |
| postgres | 5432 | PostgreSQL |
| redis | 6379 | Redis cache |
| **Observability** | | |
| grafana | 3000 | Grafana UI |
| prometheus | 9090 | Prometheus UI |
| tempo | 3200 | Tempo API |
| loki | 3100 | Loki API |
| alertmanager | 9093 | Alertmanager UI |
| otel-collector | 4317 (gRPC), 4318 (HTTP) | OTLP receivers |
| cadvisor | 8080 | Container metrics |

## Multi-Stage Builds

Multi-stage builds optimize image size and security by separating build dependencies from runtime.

### Go Service (Payments Service)

**File**: `services/payments-service/Dockerfile`

```dockerfile
# Stage 1: Build
FROM golang:1.23-alpine AS builder

WORKDIR /app

# Copy dependency files and download
COPY go.mod go.sum ./
RUN go mod download

# Copy source and build
COPY . .
RUN go build -o payments-service main.go

# Stage 2: Runtime
FROM alpine:latest

WORKDIR /app

# Copy only the compiled binary
COPY --from=builder /app/payments-service .

EXPOSE 8081

CMD ["./payments-service"]
```

**Benefits**:
- **Smaller image**: ~15MB vs ~300MB (without multi-stage)
- **Faster deployment**: Less to transfer and start
- **More secure**: No build tools or source code in final image
- **Build cache**: `go mod download` layer is cached

### C# Service (Promotions Service)

**File**: `services/promotions-service/Dockerfile`

```dockerfile
# Stage 1: Build
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build

WORKDIR /src
COPY ["PromotionsService.csproj", "./"]
RUN dotnet restore

COPY . .
RUN dotnet publish -c Release -o /app/publish

# Stage 2: Runtime
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime

WORKDIR /app
COPY --from=build /app/publish .

EXPOSE 8082

ENTRYPOINT ["dotnet", "PromotionsService.dll"]
```

**Benefits**:
- **SDK vs Runtime**: Build with full SDK, run with minimal runtime
- **Layer caching**: NuGet packages cached in restore layer
- **Size reduction**: ~200MB vs ~700MB

### Python Service (Main Service)

**File**: `services/main-service/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy and install dependencies first (for caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

CMD ["python", "main.py"]
```

**Why single-stage?**
- Python is interpreted (no compilation step needed)
- Dependencies are installed with pip
- Could use multi-stage to build wheels separately for production

**Production optimization** (optional):
```dockerfile
FROM python:3.11-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

FROM python:3.11-slim

WORKDIR /app
COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache /wheels/*

COPY . .
CMD ["python", "main.py"]
```

### Node.js Services (External Services)

**File**: `services/external/payment-provider/Dockerfile`

```dockerfile
FROM node:18-alpine

WORKDIR /app

# Install dependencies (cached layer)
COPY package*.json ./
RUN npm ci --only=production

# Copy application
COPY . .

EXPOSE 3001

CMD ["node", "index.js"]
```

**Why npm ci?**
- `npm ci` is faster and more reliable than `npm install`
- Uses `package-lock.json` for exact versions
- Cleans `node_modules` before install

### Frontend (React)

**File**: `frontend/Dockerfile`

```dockerfile
# Stage 1: Build React app
FROM node:18-alpine AS build

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:alpine

COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

**Benefits**:
- **Static build**: React app compiled to static files
- **Efficient serving**: nginx is much lighter than Node.js
- **Size**: ~25MB vs ~200MB (if using Node to serve)

## Environment Configuration

Services are configured via environment variables in `docker-compose.yml`.

### OpenTelemetry Configuration

Every instrumented service needs these variables:

```yaml
main-service:
  environment:
    - OTEL_SERVICE_NAME=main-service
    - OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
    - OTEL_EXPORTER_OTLP_INSECURE=true
```

**Variables**:
- `OTEL_SERVICE_NAME`: Identifies service in traces/metrics
- `OTEL_EXPORTER_OTLP_ENDPOINT`: Where to send telemetry
- `OTEL_EXPORTER_OTLP_INSECURE`: Use HTTP instead of HTTPS (dev only)

### Database Configuration

```yaml
postgres:
  environment:
    POSTGRES_DB: webstore
    POSTGRES_USER: webstore
    POSTGRES_PASSWORD: webstore123

main-service:
  environment:
    - DATABASE_URL=postgresql://webstore:webstore123@postgres:5432/webstore
```

**Note**: Use Docker Compose service names (`postgres`) not `localhost`.

### Service Discovery

Services communicate using Docker Compose service names:

```yaml
main-service:
  environment:
    - PAYMENTS_SERVICE_URL=http://payments-service:8081
    - PROMOTIONS_SERVICE_URL=http://promotions-service:8082
    - PAYMENT_PROVIDER_URL=http://payment-provider:3001
    - CRM_SYSTEM_URL=http://crm-system:3002
    - INVENTORY_SYSTEM_URL=http://inventory-system:3003
```

Docker's internal DNS resolves these names to container IPs.

### Using .env File (Optional)

For sensitive data or deployment-specific config:

**Create `.env` file**:
```bash
# Database
POSTGRES_PASSWORD=secure_password_here

# OpenTelemetry
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317

# External APIs
PAYMENT_PROVIDER_API_KEY=key_here
```

**Reference in docker-compose.yml**:
```yaml
postgres:
  environment:
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
```

**Load and start**:
```bash
docker-compose --env-file .env up -d
```

## Health Checks and Dependencies

Health checks ensure services are ready before dependent services start.

### Defining Health Checks

```yaml
postgres:
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U webstore"]
    interval: 10s    # Check every 10 seconds
    timeout: 5s      # Fail if takes > 5 seconds
    retries: 5       # Try 5 times before marking unhealthy
```

**Common health check commands**:

| Service | Health Check |
|---------|-------------|
| PostgreSQL | `pg_isready -U webstore` |
| Redis | `redis-cli ping` |
| HTTP service | `curl -f http://localhost:8000/health` |
| Prometheus | `curl -f http://localhost:9090/-/ready` |
| Loki | `curl -f http://localhost:3100/ready` |

### Dependency Management

Services can wait for dependencies to be healthy:

```yaml
main-service:
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
    otel-collector:
      condition: service_started
```

**Conditions**:
- `service_started`: Container started (default)
- `service_healthy`: Health check passing
- `service_completed_successfully`: Container exited with 0

### Startup Order

With health checks and dependencies:

```
1. postgres starts
   ├─ Health check: pg_isready
   └─ After 5-10s: HEALTHY

2. redis starts
   ├─ Health check: redis-cli ping
   └─ After 2-3s: HEALTHY

3. otel-collector starts (no health check, immediate)

4. main-service starts
   └─ Waits for postgres and redis to be HEALTHY
   └─ Then starts
```

### Health Check Script

**File**: `health-check.sh`

Verifies the entire observability stack:

```bash
#!/bin/bash

echo "1. Testing metric flow..."
curl -X POST http://localhost:8000/cart/add \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer user-token-123" \
  -d '{"product_id": 3, "quantity": 1}'

echo "2. Checking OTEL Collector..."
curl -s http://localhost:8889/metrics | grep -c "webstore_cart_additions"

echo "3. Checking Prometheus..."
curl -s 'http://localhost:9090/api/v1/query?query=webstore_cart_additions_total'

echo "4. Checking Tempo..."
curl -s http://localhost:3200/ready

echo "5. Checking Loki..."
curl -s http://localhost:3100/ready
```

**Run it**:
```bash
./health-check.sh
```

## Networking

Docker Compose creates a dedicated network for all services.

### Default Network

All services communicate via a bridge network named `{project}_default`:

```
monitoring-example_default
    ├─ main-service (172.18.0.5)
    ├─ payments-service (172.18.0.6)
    ├─ postgres (172.18.0.2)
    └─ ... (other services)
```

### Service Resolution

Docker's DNS resolves service names:

```python
# In main-service code
response = requests.get("http://payments-service:8081/health")
```

Docker DNS:
1. Resolves `payments-service` → `172.18.0.6`
2. Routes request internally
3. No external network hop

### Port Publishing

Services can be accessed from host machine:

```yaml
grafana:
  ports:
    - "3000:3000"  # host:container
```

- **`3000:3000`**: Bind container port 3000 to host port 3000
- **`3001:80`**: Bind container port 80 to host port 3001
- **No port mapping**: Service only accessible within Docker network

### Custom Networks (Optional)

For isolation, define custom networks:

```yaml
networks:
  frontend:
  backend:
  monitoring:

services:
  main-service:
    networks:
      - backend
      - monitoring

  postgres:
    networks:
      - backend  # Not accessible from frontend network

  frontend:
    networks:
      - frontend
      - monitoring
```

## Volume Management

Volumes persist data across container restarts and rebuilds.

### Defined Volumes

```yaml
volumes:
  postgres_data:      # Database data
  prometheus_data:    # Metrics
  tempo_data:         # Traces
  loki_data:          # Logs
  grafana_data:       # Dashboards, users
  alertmanager_data:  # Alert state
  pyroscope_data:     # Profiles
```

### Volume Mounting

```yaml
postgres:
  volumes:
    - postgres_data:/var/lib/postgresql/data  # Named volume

prometheus:
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml  # Bind mount (config)
    - prometheus_data:/prometheus  # Named volume (data)
```

**Volume types**:

1. **Named volume** (`postgres_data:/var/lib/postgresql/data`):
   - Managed by Docker
   - Persists across restarts
   - Survives `docker-compose down`

2. **Bind mount** (`./prometheus.yml:/etc/prometheus/prometheus.yml`):
   - Maps host file/directory
   - Changes reflected immediately
   - Good for configuration files

### Volume Commands

```bash
# List volumes
docker volume ls

# Inspect volume
docker volume inspect monitoring-example_postgres_data

# Remove all volumes (deletes data!)
docker-compose down -v

# Backup a volume
docker run --rm \
  -v monitoring-example_postgres_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/postgres-backup.tar.gz -C /data .

# Restore a volume
docker run --rm \
  -v monitoring-example_postgres_data:/data \
  -v $(pwd):/backup \
  alpine tar xzf /backup/postgres-backup.tar.gz -C /data
```

### Configuration Files as Bind Mounts

Many services mount config files from the host:

```yaml
otel-collector:
  volumes:
    - ./otel-collector-config.yaml:/etc/otel-collector-config.yaml

prometheus:
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml
    - ./prometheus-alerts.yml:/etc/prometheus/prometheus-alerts.yml

grafana:
  volumes:
    - ./grafana/provisioning:/etc/grafana/provisioning
    - ./grafana/dashboards:/var/lib/grafana/dashboards
```

**Benefits**:
- Edit config on host
- Restart container to reload
- No need to rebuild image

## Common Commands

### Starting and Stopping

```bash
# Start all services
docker-compose up -d

# Start specific service
docker-compose up -d main-service

# Stop all services (keeps data)
docker-compose down

# Stop and remove volumes (deletes all data!)
docker-compose down -v

# Stop specific service
docker-compose stop main-service

# Start stopped service
docker-compose start main-service

# Restart service
docker-compose restart main-service
```

### Building and Rebuilding

```bash
# Build all images
docker-compose build

# Build specific service
docker-compose build main-service

# Build with no cache (clean build)
docker-compose build --no-cache main-service

# Build and start
docker-compose up -d --build

# Rebuild and restart specific service
docker-compose up -d --build main-service
```

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f main-service

# Multiple services
docker-compose logs -f main-service payments-service

# Last 100 lines
docker-compose logs --tail=100 main-service

# With timestamps
docker-compose logs --timestamps main-service

# Since specific time
docker-compose logs --since 2025-10-19T10:00:00 main-service
```

### Inspecting Services

```bash
# List running services
docker-compose ps

# Detailed service info
docker-compose ps main-service

# Execute command in container
docker-compose exec main-service bash
docker-compose exec postgres psql -U webstore

# Check service health
docker-compose ps --format json | jq

# View resource usage
docker stats
```

### Scaling Services

```bash
# Run multiple instances
docker-compose up -d --scale main-service=3

# View instances
docker-compose ps main-service
```

**Note**: Requires load balancer for proper distribution.

### Cleaning Up

```bash
# Stop and remove containers
docker-compose down

# Remove containers, networks, and volumes
docker-compose down -v

# Remove everything including images
docker-compose down -v --rmi all

# Remove unused images
docker image prune -a

# Remove all stopped containers
docker container prune

# Remove all unused volumes
docker volume prune

# Full cleanup (CAUTION: removes everything)
docker system prune -a --volumes
```

### Troubleshooting Commands

```bash
# Check if services are running
docker-compose ps

# Check logs for errors
docker-compose logs main-service | grep -i error

# Inspect container
docker inspect monitoring-example-main-service-1

# Check network
docker network inspect monitoring-example_default

# Test connectivity between services
docker-compose exec main-service ping postgres

# Check port bindings
docker-compose port main-service 8000

# View environment variables
docker-compose exec main-service env

# Validate docker-compose.yml
docker-compose config

# Check resource constraints
docker-compose exec main-service cat /sys/fs/cgroup/memory/memory.limit_in_bytes
```

## Makefile Shortcuts

**File**: `Makefile`

The project includes common commands:

```bash
# Start everything
make start

# Stop everything
make stop

# View logs
make logs-main
make logs-payments

# Rebuild service
make rebuild-main

# Run tests
make test

# Health check
make health-check
```

## Production Considerations

### Security

For production deployments:

1. **Don't use default passwords**:
```yaml
postgres:
  environment:
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}  # From .env or secrets
```

2. **Don't expose unnecessary ports**:
```yaml
postgres:
  # Remove this in production:
  # ports:
  #   - "5432:5432"
```

3. **Use secrets management**:
```yaml
services:
  main-service:
    secrets:
      - db_password
      - api_key

secrets:
  db_password:
    external: true
  api_key:
    external: true
```

4. **Run as non-root user**:
```dockerfile
FROM python:3.11-slim

RUN useradd -m -u 1000 appuser
USER appuser

WORKDIR /app
...
```

### Resource Limits

Prevent containers from consuming all resources:

```yaml
main-service:
  deploy:
    resources:
      limits:
        cpus: '1.0'
        memory: 512M
      reservations:
        cpus: '0.5'
        memory: 256M
```

### Restart Policies

Automatically restart failed containers:

```yaml
main-service:
  restart: unless-stopped  # or: always, on-failure, no
```

## Related Documentation

- **[docker-compose.yml](../docker-compose.yml)**: Complete service definitions
- **[01_GETTING_STARTED.md](01_GETTING_STARTED.md)**: Quick start guide
- **[09_TROUBLESHOOTING.md](09_TROUBLESHOOTING.md)**: Common issues and solutions

## Summary

You learned:

- **Docker Compose architecture** with 15 containerized services
- **Multi-stage builds** for optimized images (Go, C#, Node.js, React)
- **Environment configuration** for service discovery and OpenTelemetry
- **Health checks and dependencies** for reliable startup
- **Networking** and service-to-service communication
- **Volume management** for data persistence
- **Common commands** for development and operations

**Key takeaways**:
1. Multi-stage builds reduce image size and improve security
2. Health checks ensure services start in correct order
3. Named volumes persist data across restarts
4. Service names work as DNS for inter-service communication
5. Bind mounts allow live config updates without rebuilds

---

**Next**: [Troubleshooting](09_TROUBLESHOOTING.md) →
