# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WebStore is a polyglot microservices e-commerce application demonstrating modern observability practices. The architecture evolved from a Python monolith to distributed microservices (Python/FastAPI, Go, C#/.NET) with OpenTelemetry instrumentation, pushing all telemetry via OTLP to a unified collector.

**Key Architecture Pattern**: Pure OTLP push-based observability (no Prometheus client scraping). All services push metrics and traces via OTLP/gRPC (port 4317) → OpenTelemetry Collector → Prometheus/Tempo/Loki.

## Common Commands

### Development & Testing

```bash
# Start all services (takes 2-3 minutes to initialize)
docker-compose up -d
# or
make start
# or
./start.sh

# Stop services
docker-compose down
make stop

# Rebuild specific service after code changes
docker-compose up -d --build <service-name>

# View logs
docker-compose logs -f <service-name>
make logs-main          # Main service
make logs-payments      # Payments service
make logs-promotions    # Promotions service
make logs-otel          # OTEL Collector

# Generate traffic for testing
cd scripts && python3 generate-traffic.py --users 5 --duration 60
make traffic            # Light traffic
make traffic-heavy      # Heavy traffic

# Health checks
make health                               # Basic health check
./health-check-dependencies.sh            # Full dependency tracking
./health-check-dependencies.sh --json     # JSON output
```

### Service-Specific Development

**Python (main-service)**:
```bash
cd services/main-service
pip install -r requirements.txt
python main.py  # Runs on port 8000
```

**Go (payments-service)**:
```bash
cd services/payments-service
go mod download
go run main.go  # Runs on port 8081
```

**C# (promotions-service)**:
```bash
cd services/promotions-service
dotnet restore
dotnet run  # Runs on port 8082
```

**Frontend**:
```bash
cd frontend
npm install
npm start
```

## High-Level Architecture

### Service Communication Flow

```
Frontend → Main Service → PostgreSQL/Redis
                      ↓
                   ┌──────────────┬─────────────────┐
                   ↓              ↓                 ↓
          Payments Service  Promotions Service  External Services
                   ↓                           (payment-provider,
          Payment Provider                      crm-system,
                                                inventory-system)
```

**Critical Dependency**: Main service depends on PostgreSQL and Redis. Services can take 30-60 seconds to be fully ready on first start, especially the database.

### Observability Pipeline

All services use OpenTelemetry auto-instrumentation and push telemetry via **OTLP/gRPC (port 4317)** to the OpenTelemetry Collector:

```
Services (OTLP push) → OTEL Collector → Prometheus exporter (:8889)
                               ↓
                        Tempo (traces)
                        Loki (logs)

Prometheus ← scrapes OTEL Collector :8889 (NOT services)
```

**Important**: Services do NOT expose `/metrics` endpoints. All metrics flow through OTLP → Collector → Prometheus scrape. External services (payment-provider, crm-system, inventory-system) simulate third-party APIs and deliberately have NO monitoring instrumentation.

### Trace Context Propagation

All internal services propagate W3C Trace Context headers (`traceparent`). Traces span: Frontend (Faro) → Main Service → Payments/Promotions → External Services. Logs include `trace_id` and `span_id` for correlation.

### Structured Logging

All services use JSON structured logging with trace correlation:
- **Python**: `python-json-logger` with custom formatter
- **Go**: `uber/zap` with structured fields
- **C#**: `Serilog` with `CompactJsonFormatter` using message templates (e.g., `"Processing {OrderId}"`)
- **Node.js**: `Pino` with JSON output

See [LOGGING_STANDARDS.md](docs/LOGGING_STANDARDS.md) for complete standards and LogQL query examples.

## Trace Sampling Strategy

The OpenTelemetry Collector uses **value-based tail sampling** with 12 policies:
- Always sample: errors, high latency (>1s), critical endpoints (/api/orders, /api/payments/process, /cart/checkout)
- Business value: high-value transactions (>$1000), VIP users, geographic targeting
- Performance: slow database queries (>500ms), slow external calls (>2s)
- Probabilistic baseline: 10% of all other traces

Configuration: [otel-collector-config.yaml](otel-collector-config.yaml)
Details: [TRACE_SAMPLING_STRATEGY.md](docs/TRACE_SAMPLING_STRATEGY.md)

**Expected sampling rate**: ~30% overall (100% critical traces + 10% baseline), reducing storage by ~70%.

## macOS-Specific: Container Metrics

On macOS, cAdvisor cannot access Docker container names due to Docker Desktop virtualization. The System Metrics dashboard uses container ID hashes in queries.

**When container IDs change** (after `docker-compose down` or rebuild):

```bash
# Get current container IDs
docker ps --format '{{.Names}}: {{.ID}}' | grep monitoring-example

# Update grafana/dashboards/system-metrics.json
# Replace id=~".*/[old-hash].*" with id=~".*/[new-hash].*"
# Then restart Grafana
docker-compose restart grafana
```

**AI-assisted update**: The dashboard includes instructions for AI to automate this process. See README section "macOS-Specific: System Metrics Dashboard Shows 'No Data'".

## Health Check Architecture

The project includes layered health checks with dependency tracking:

**5 Layers**:
1. Core Infrastructure (PostgreSQL, Redis) - Critical
2. Observability (OTEL Collector, Prometheus, Tempo, Loki, Alertmanager, Grafana) - Non-critical
3. Core Services (main-service, payments-service, promotions-service) - Critical
4. External Services (payment-provider, crm-system, inventory-system) - Non-critical
5. Frontend - Non-critical

See [HEALTH_CHECK_ARCHITECTURE.md](docs/HEALTH_CHECK_ARCHITECTURE.md) for detailed dependency matrix and integration patterns.

## Failure Simulation

External services simulate realistic third-party behavior with country-specific failure rates:

| Country | Payment Failures |
|---------|-----------------|
| US | 5% |
| UK | 7% |
| DE | 6% |
| FR | 8% |
| JP | 10% |
| BR | 15% |
| IN | 12% |

CRM: 8% global failure, Inventory: 10% global failure. Random HTTP errors: 400, 404, 500, 503, 429.

## Alerting & SLOs

**18 alert rules** across 4 categories (service health, resource usage, business metrics, SLO violations).

**SLOs**:
- Availability: 99.9% uptime (43.2 min/month error budget)
- Latency: P95 < 1s
- Payment Success: >90%

Configuration: [prometheus-alerts.yml](prometheus-alerts.yml)
Routing: [alertmanager.yml](alertmanager.yml)

## Authentication

Demo uses hardcoded opaque tokens:
- `user-token-123`
- `admin-token-456`
- `test-token-789`

Protected endpoints: `/cart/add`, `/cart`, `/checkout`, `/orders`
Public endpoints: `/health`, `/products`, `/products/{id}`

## Key Metrics

**Business Metrics** (main-service):
- `webstore_cart_additions_total` - Cart additions by country, product
- `webstore_checkouts_total` - Checkouts by country, payment method, status
- `webstore_checkout_amount` - Checkout amounts (histogram)
- `webstore_active_carts` - Active shopping carts by country

**Payment Metrics** (payments-service):
- `payments_processed_total` - Payments by country, method, status
- `payment_amount_usd` - Payment amounts (histogram)
- `external_payment_provider_duration_seconds` - External API latency

**Note**: Metrics use OpenTelemetry semantic naming (dot notation) and are pushed via OTLP.

## Grafana Dashboards

Auto-provisioned dashboards in [grafana/dashboards/](grafana/dashboards/):
- **webstore-overview.json**: Business metrics, cart additions, checkout rates, country-specific performance
- **slo-tracking.json**: SLI measurements, error budgets, burn rates
- **service-health.json**: RPS, error rates, latency percentiles, dependency health
- **system-metrics.json**: Container CPU/memory (macOS requires container ID updates)

Access: http://localhost:3000 (anonymous access enabled)

## Important Constraints

1. **No Prometheus client scraping**: Services push metrics via OTLP only. Do NOT add Prometheus client libraries or `/metrics` endpoints.
2. **External services have no monitoring**: payment-provider, crm-system, inventory-system simulate third-party APIs and should NOT expose metrics/traces.
3. **Container startup time**: Services take 2-3 minutes to fully initialize, especially on first run. Wait before testing.
4. **macOS container IDs**: System metrics dashboard requires manual updates when containers are recreated on macOS.

## File Locations Reference

**Service code**:
- Main: `services/main-service/main.py`
- Payments: `services/payments-service/main.go`
- Promotions: `services/promotions-service/Program.cs`
- External: `services/external/{payment-provider,crm-system,inventory-system}/index.js`

**Configuration**:
- OTEL Collector: `otel-collector-config.yaml`
- Prometheus: `prometheus.yml`, `prometheus-alerts.yml`
- Loki: `loki.yaml`, `loki-rules.yaml`
- Alertmanager: `alertmanager.yml`

**Documentation**:
- Architecture details: `docs/ARCHITECTURE.md`
- Quick start: `docs/QUICKSTART.md`
- Health checks: `docs/HEALTH_CHECK_ARCHITECTURE.md`
- Logging standards: `docs/LOGGING_STANDARDS.md`
- Trace sampling: `docs/TRACE_SAMPLING_STRATEGY.md`

## Common Troubleshooting

**Services not starting**: Check logs with `docker-compose logs <service>`. Verify PostgreSQL is ready (can take 30-60s).

**No metrics in Prometheus**:
1. Check OTEL Collector is running and exporting: `curl http://localhost:8889/metrics`
2. Check Prometheus targets: http://localhost:9090/targets (otel-collector:8889 should be UP)

**No traces in Tempo**: Check OTEL Collector logs: `docker-compose logs otel-collector | grep TracesExporter`

**Dashboard shows "No data"**:
1. Generate traffic: `make traffic`
2. Wait 30-60s for metrics to be scraped
3. On macOS: Check if container IDs need updating (system-metrics dashboard)

**Port conflicts**: Another service is using required ports. Check with `lsof -i :<port>` and stop conflicting service or change ports in docker-compose.yml.
