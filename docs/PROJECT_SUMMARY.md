# Project Summary - Quick Reference

> **Note**: For a structured learning path and detailed guides, start with [00_LEARNING_PATH.md](00_LEARNING_PATH.md).
> This document provides a **high-level feature checklist** and quick reference links.

## Overview

WebStore is a **production-ready demonstration** of modern observability practices using OpenTelemetry and the Grafana Stack across a polyglot microservices e-commerce application.

## Technology Stack

### Application Services (7)
- **Frontend**: React 18 + Grafana Faro (RUM)
- **Main Service**: Python 3.11 + FastAPI
- **Payments Service**: Go 1.23 + Gin
- **Promotions Service**: .NET 8 + ASP.NET Core
- **External Services**: Node.js 18 + Express (3 services)

### Observability Stack (8)
- **Collection**: OpenTelemetry Collector
- **Metrics**: Prometheus
- **Traces**: Grafana Tempo
- **Logs**: Grafana Loki
- **Profiling**: Grafana Pyroscope
- **Alerting**: Prometheus Alertmanager
- **Visualization**: Grafana
- **Container Metrics**: cAdvisor

### Infrastructure
- **Database**: PostgreSQL 15
- **Cache**: Redis 7
- **Orchestration**: Docker Compose

## Feature Checklist

### ✅ Core Observability Features

- [x] **OpenTelemetry instrumentation** (Python, Go, C#, Node.js)
- [x] **Distributed tracing** with W3C Trace Context
- [x] **Custom business metrics** (cart additions, checkouts, payments)
- [x] **Structured logging** with trace correlation
- [x] **Real User Monitoring (RUM)** with Grafana Faro
- [x] **Continuous profiling** with Pyroscope
- [x] **Pure OTLP push architecture** (vendor-neutral)
- [x] **Tail sampling** in OTEL Collector
- [x] **Metrics exemplars** (link from metrics to traces)

### ✅ Alerting & SLO Tracking

- [x] **18 alert rules** (service health, resource, business, SLO)
- [x] **SLO tracking** (availability, latency, payment success)
- [x] **Error budget monitoring**
- [x] **Multi-burn-rate alerting**
- [x] **Team-based alert routing**
- [x] **Alertmanager integration**

### ✅ Dashboards & Visualization

- [x] **7 Grafana dashboards** pre-configured
  - WebStore Overview
  - SLO Tracking & Error Budgets
  - Service Health & Dependencies
  - HTTP Metrics
  - Logs Explorer
  - System Metrics
- [x] **Auto-provisioned data sources**
- [x] **Service dependency graphs**

### ✅ Realistic Simulation

- [x] **Geographic distribution** (7 countries with varying failure rates)
- [x] **External service failures** (payment provider, CRM, inventory)
- [x] **Country-specific payment failures** (5-15% by region)
- [x] **Random external API errors** (400, 404, 500, 503, 429)
- [x] **Traffic generation scripts** (single-user and continuous)

### ✅ Best Practices Demonstrated

- [x] **Multi-stage Docker builds** (Go, C#, React)
- [x] **Health checks with dependencies**
- [x] **Volume persistence**
- [x] **Environment configuration**
- [x] **Security best practices** (token-based auth)
- [x] **Polyglot architecture**

## Quick Start

```bash
# 1. Start all services
./start.sh

# 2. Generate traffic
cd scripts
python3 generate-traffic.py --users 5 --duration 60

# 3. Open Grafana
open http://localhost:3000
# Default credentials: admin/admin
```

## Key Endpoints

| Service | Port | URL |
|---------|------|-----|
| **Application** | | |
| Frontend | 3001 | http://localhost:3001 |
| Main API | 8000 | http://localhost:8000 |
| Payments API | 8081 | http://localhost:8081 |
| Promotions API | 8082 | http://localhost:8082 |
| **Observability** | | |
| Grafana | 3000 | http://localhost:3000 |
| Prometheus | 9090 | http://localhost:9090 |
| Alertmanager | 9093 | http://localhost:9093 |
| **Infrastructure** | | |
| PostgreSQL | 5432 | localhost:5432 |
| Redis | 6379 | localhost:6379 |

## Learning Resources

### Numbered Guides (Recommended Learning Path)

1. **[00_LEARNING_PATH.md](00_LEARNING_PATH.md)** - Start here
2. **[01_GETTING_STARTED.md](01_GETTING_STARTED.md)** - Setup and first run
3. **[02_ARCHITECTURE_OVERVIEW.md](02_ARCHITECTURE_OVERVIEW.md)** - System design
4. **[03_OPENTELEMETRY_INSTRUMENTATION.md](03_OPENTELEMETRY_INSTRUMENTATION.md)** - OTel implementation
5. **[04_METRICS_AND_EXEMPLARS.md](04_METRICS_AND_EXEMPLARS.md)** - Business metrics
6. **[05_DISTRIBUTED_TRACING.md](05_DISTRIBUTED_TRACING.md)** - Traces and spans
7. **[06_LOGGING_AND_CORRELATION.md](06_LOGGING_AND_CORRELATION.md)** - Structured logging
8. **[07_ALERTING_AND_SLOS.md](07_ALERTING_AND_SLOS.md)** - SLO tracking
9. **[08_DOCKER_AND_DEPLOYMENT.md](08_DOCKER_AND_DEPLOYMENT.md)** - Containerization
10. **[09_TROUBLESHOOTING.md](09_TROUBLESHOOTING.md)** - Common issues

### Technical Reference Documents

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Deep technical architecture
- **[LOGGING_STANDARDS.md](LOGGING_STANDARDS.md)** - Logging specifications
- **[HEALTH_CHECK_ARCHITECTURE.md](HEALTH_CHECK_ARCHITECTURE.md)** - Health check details
- **[REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md)** - Evolution history

### Configuration Files

- **[docker-compose.yml](../docker-compose.yml)** - Service orchestration
- **[otel-collector-config.yaml](../otel-collector-config.yaml)** - OTEL Collector setup
- **[prometheus.yml](../prometheus.yml)** - Metrics collection
- **[prometheus-alerts.yml](../prometheus-alerts.yml)** - Alert rules
- **[tempo.yaml](../tempo.yaml)** - Trace storage
- **[loki.yaml](../loki.yaml)** - Log aggregation

## System Requirements

### Minimum
- Docker Desktop with 8GB RAM
- 4 CPU cores
- 20GB disk space

### Recommended
- Docker Desktop with 16GB RAM
- 8 CPU cores
- 50GB disk space (SSD preferred)

## Common Commands

```bash
# Using Makefile
make start          # Start all services
make stop           # Stop all services
make logs           # View logs
make traffic        # Generate traffic
make health         # Health check
make clean          # Remove all data

# Using docker-compose directly
docker-compose up -d                    # Start
docker-compose down                     # Stop
docker-compose logs -f main-service     # View logs
docker-compose ps                       # Service status
docker-compose restart main-service     # Restart service
```

## What You Can Observe

### Metrics (Prometheus)
- Business metrics: cart additions, checkouts, payment rates
- Service metrics: request rates, latencies, error rates
- Infrastructure metrics: database, Redis, container resources

### Traces (Tempo)
- Complete request flows across all services
- Service dependency graphs
- Error propagation tracking
- Performance bottleneck identification

### Logs (Loki)
- Structured JSON logs with trace correlation
- LogQL queries for filtering and aggregation
- Error log analysis by service/country

### Profiles (Pyroscope)
- CPU usage flame graphs
- Memory allocation tracking
- Function-level performance

### Frontend (Faro)
- Real user monitoring
- Page load times
- JavaScript errors
- User interactions

## Use Cases

Perfect for:
- Learning OpenTelemetry and Grafana Stack
- Demonstrating observability to teams
- Testing observability tools
- Understanding distributed tracing
- Training on monitoring best practices
- Prototyping observability solutions
- Conference talks and workshops

---

**Everything you need for a complete observability demonstration!**

For detailed learning, start with [00_LEARNING_PATH.md](00_LEARNING_PATH.md).
