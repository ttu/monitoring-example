# Architecture - Technical Reference

> **Note**: For an introduction to the architecture, see [02_ARCHITECTURE_OVERVIEW.md](02_ARCHITECTURE_OVERVIEW.md).
> This document provides **detailed technical specifications**, evolution journey, and deep-dive information.

## Application Overview

**WebStore** is an e-commerce platform that has evolved from a monolithic architecture to a microservices-based system.

### Evolution Journey

**Phase 1: Monolithic Application**
- Originally built as a single FastAPI service handling all e-commerce functionality
- Direct integration with third-party services (payment providers, CRM, inventory management)
- All business logic, payment processing, and promotional features in one codebase
- Direct database and Redis access from the monolith

**Phase 2: Payment Service Extraction**
- Payment processing logic extracted into a dedicated **Payments Service** (Go)
- Motivations:
  - Isolate payment processing for PCI compliance
  - Enable independent scaling of payment workloads
  - Use Go's performance for high-throughput payment transactions
  - Separate deployment lifecycle for critical payment features

**Phase 3: Promotions Service Addition**
- New promotional and pricing features added as **Promotions Service** (.NET)
- Built as a greenfield service to:
  - Implement complex promotional logic (discounts, campaigns, loyalty programs)
  - Demonstrate polyglot architecture capabilities
  - Enable A/B testing of promotional strategies without affecting core services
  - Showcase .NET observability integration

**Current Architecture: Distributed Microservices**
- **Main Service** (Python/FastAPI): Core e-commerce logic, cart management, order processing
- **Payments Service** (Go): Payment transaction processing, provider integration
- **Promotions Service** (.NET): Promotional campaigns, discount calculations
- **External Services** (Node.js): Mock third-party integrations (payment provider, CRM, inventory)

This architecture demonstrates modern observability practices across a polyglot microservices ecosystem, with each service instrumented using OpenTelemetry for distributed tracing, metrics, and structured logging.

**For detailed system diagrams and data flows, see [02_ARCHITECTURE_OVERVIEW.md](02_ARCHITECTURE_OVERVIEW.md).**

### Metrics Flow (Recommended Pattern)

**Services → OTLP Collector → Prometheus**

1. **Services push metrics** via OTLP/gRPC (port 4317) to the collector
2. **OTLP Collector** exposes Prometheus exporter endpoint (:8889/metrics)
3. **Prometheus scrapes** the collector endpoint every 15s (pull-based)

**Why this pattern?**
- ✅ **Prometheus-native**: Leverages Prometheus's pull-based design
- ✅ **No duplicates**: Single ingestion path
- ✅ **Better performance**: Efficient scraping vs. remote write
- ✅ **Easier debugging**: Can curl :8889/metrics to inspect
- ✅ **OpenTelemetry best practice**: Collector acts as metrics aggregation point

**NOT USED: Remote Write** (push-based)
- ❌ Would create duplicate metrics (both scrape + push)
- ❌ Only needed when Prometheus can't reach collector
- ❌ More complex architecture

## Technical Specifications

### Service Instrumentation Details

All **internal services** use **pure OpenTelemetry** for both tracing and metrics, pushing telemetry via OTLP protocol.

### Main Service (FastAPI - Python)
- **Tracing**: `opentelemetry-instrumentation-fastapi` - Auto-instruments HTTP requests, routes
- **Metrics**: OpenTelemetry Metrics API - Custom business metrics
- **Instrumentation**: FastAPI, SQLAlchemy, Redis, HTTPX
- **Export**: OTLP/gRPC → OTEL Collector (port 4317)
- **Custom Metrics**:
  - `webstore.cart.additions` (Counter)
  - `webstore.checkouts` (Counter)
  - `webstore.checkout.amount` (Histogram)
  - `webstore.payment.duration` (Histogram)

### Payments Service (Go)
- **Tracing**: `go.opentelemetry.io/contrib/instrumentation/github.com/gin-gonic/gin/otelgin` - Auto-instruments Gin routes
- **Metrics**: OpenTelemetry Metrics API with OTLP exporter
- **Instrumentation**: HTTP client (otelhttp), Gin framework
- **Export**: OTLP/gRPC → OTEL Collector (port 4317)
- **Custom Metrics**:
  - `payments_processed_total` (Counter) - Payment transactions by country, method, status
  - `payment_amount_usd` (Histogram) - Payment amounts in USD
  - `external_payment_provider_duration_seconds` (Histogram) - External API call latency
  - `http_server_duration_milliseconds` (Histogram) - HTTP request duration via custom middleware

### Promotions Service (C# .NET)
- **Tracing**: `OpenTelemetry.Instrumentation.AspNetCore` - Auto-instruments ASP.NET Core
- **Metrics**: ASP.NET Core built-in metrics via OpenTelemetry
- **Logging**: Serilog with CompactJsonFormatter - Structured JSON logs with message templates
- **Export**: OTLP/gRPC → OTEL Collector (port 4317)

## Structured Logging

All services use **structured logging** with JSON output for correlation with traces and metrics:

### Main Service (Python)
- **Library**: `python-json-logger` with custom formatter
- **Format**: JSON with trace context extraction
- **Fields**: `level`, `msg`, `timestamp`, `service`, `trace_id`, `span_id`, business context
- **Example**:
  ```json
  {"level": "info", "msg": "Processing checkout", "trace_id": "abc123", "user_id": "user_1", "amount": 99.99}
  ```

### Payments Service (Go)
- **Library**: `uber/zap` with structured fields
- **Format**: JSON with trace context helper
- **Fields**: `level`, `msg`, `timestamp`, `service`, `trace_id`, `span_id`, business context
- **Example**:
  ```json
  {"level": "info", "msg": "Processing payment", "trace_id": "abc123", "user_id": "user_1", "amount": 99.99}
  ```

### Promotions Service (C#)
- **Library**: Serilog with `CompactJsonFormatter`
- **Format**: Serilog message templates (structured logging best practice for .NET)
- **Fields**: `@t` (timestamp), `@mt` (message template), `@l` (level), properties from placeholders
- **Example**:
  ```json
  {"@t": "2024-01-01T12:00:00Z", "@mt": "Checking promotions for user {UserId}", "UserId": "user_1"}
  ```
- **Note**: Message templates like `"Processing {OrderId}"` ARE the correct structured logging approach in Serilog - placeholders become separate JSON properties

### External Services (Node.js)
- **Library**: Pino - Fast JSON logger
- **Format**: JSON with structured fields
- **Fields**: `level`, `msg`, `time`, `service`, business context
- **Example**:
  ```json
  {"level": "info", "msg": "Stock check", "product_id": "123", "quantity": 5, "country": "US"}
  ```

### Log Correlation
All logs include `trace_id` and `span_id` from OpenTelemetry context:
- ✅ Click trace_id in Loki → Jump to Tempo trace
- ✅ Click "Logs for this span" in Tempo → Jump to related logs
- ✅ Search logs by trace_id to follow request through all services

## External Services (Node.js)
- **No monitoring instrumentation** - These simulate third-party APIs
- External systems (payment-provider, crm-system, inventory-system) do not expose metrics or traces
- This maintains realistic behavior as you wouldn't have monitoring access to third-party services

**Key Architecture Pattern**:
1. **Push-based telemetry**: All metrics and traces pushed via OTLP (no scraping)
2. **Single pipeline**: OTLP → OTEL Collector → Prometheus/Tempo/Loki
3. **Vendor-neutral**: Pure OpenTelemetry implementation
4. **No dual collection**: Eliminated Prometheus client scraping
5. **Realistic external services**: Third-party APIs don't expose internal metrics

**For complete data flow diagrams, see [02_ARCHITECTURE_OVERVIEW.md](02_ARCHITECTURE_OVERVIEW.md#data-flow-complete-checkout-process).**

## Metrics Architecture: Pure OTLP Push

### Metrics Flow

```
┌─────────────────────┐
│  Main Service       │
│  (Python/FastAPI)   │
│                     │
│  OpenTelemetry      │
│  Metrics API        │
│  - Counter          │
│  - Histogram        │
└──────────┬──────────┘
           │ OTLP/gRPC
           │ Port 4317
           ▼
┌─────────────────────┐
│  OTEL Collector     │
│                     │
│  Receivers:         │
│  - OTLP gRPC        │
│                     │
│  Exporters:         │
│  - Prometheus (8889)│
│  - Tempo            │
│  - Loki             │
└──────────┬──────────┘
           │ HTTP scrape
           │ Port 8889
           ▼
┌─────────────────────┐
│  Prometheus         │
│                     │
│  Scrapes OTEL       │
│  Collector only     │
└─────────────────────┘
```

**Key Points**:
- ✅ No `/metrics` endpoints on services
- ✅ All metrics pushed via OTLP
- ✅ OTEL Collector aggregates and exports to Prometheus
- ✅ Single metrics pipeline
- ✅ Vendor-neutral (pure OpenTelemetry)

### External Services

External systems (payment-provider, crm-system, inventory-system) **do not expose metrics**:
- They simulate third-party APIs (Stripe, SendGrid, ShipStation, etc.)
- Real third-party services don't give you access to their internal metrics
- This maintains realistic behavior and clean architectural boundaries

## Key Metrics

### Business Metrics (Main Service)

| Metric | Type | Description | Labels |
|--------|------|-------------|--------|
| `webstore.cart.additions` | Counter | Items added to cart | country, product_id |
| `webstore.checkouts` | Counter | Completed checkouts | country, payment_method, status |
| `webstore.checkout.amount` | Histogram | Checkout amounts | country, payment_method |
| `webstore.payment.duration` | Histogram | Payment processing time | country, payment_method |

**Note**: Metrics use OpenTelemetry semantic naming (dot notation) and are pushed via OTLP.

### Infrastructure Metrics

- HTTP request duration
- HTTP request count
- Database connection pool
- Redis operations
- OpenTelemetry Collector metrics

## System Metrics (Hybrid Approach)

### Container Metrics via cAdvisor

For monitoring container resource usage (CPU, memory, network, disk), we use a **hybrid approach** combining mature Prometheus exporters with OpenTelemetry pipelines:

```
cAdvisor (8080) ──┐
                  ├──→ OTLP Collector (Prometheus Receiver) ──→ Prometheus Exporter (:8889) ──→ Prometheus ──→ Grafana
Services (OTLP) ──┘
```

**Why Hybrid?**
- ✅ **Best of both worlds**: Mature exporters (cAdvisor) + flexible OTel pipelines
- ✅ **Single pipeline**: All metrics flow through OTLP collector for consistent processing
- ✅ **Unified labels**: Resource processor adds consistent labels to all metrics
- ✅ **Future-proof**: Easy to add more exporters (node_exporter, redis_exporter, etc.)
- ✅ **No Prometheus config changes**: Prometheus only scrapes one endpoint (OTLP collector:8889)

**Container Metrics Collected:**
- `container_cpu_usage_seconds_total` - CPU usage per container
- `container_memory_usage_bytes` - Memory usage per container
- `container_network_receive_bytes_total` - Network RX throughput
- `container_network_transmit_bytes_total` - Network TX throughput
- `container_fs_reads_bytes_total` - Filesystem read bytes
- `container_fs_writes_bytes_total` - Filesystem write bytes

**Alternative: Direct Prometheus Scraping (Without OTLP)**

If you prefer a simpler setup without the OTLP collector hybrid approach, you can configure Prometheus to scrape cAdvisor directly:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'cadvisor'
    static_configs:
      - targets: ['cadvisor:8080']
```

This approach:
- ✅ Simpler configuration (no OTLP collector involvement)
- ✅ Direct metrics path (fewer hops)
- ❌ No unified processing (metrics bypass OTLP collector processors)
- ❌ Inconsistent labels (no resource processor enrichment)
- ❌ Multiple scrape endpoints (Prometheus must scrape both cAdvisor + OTLP collector)

**Recommendation**: Use the hybrid approach (current implementation) for consistency and better maintainability.

**For trace context and service dependency details, see [02_ARCHITECTURE_OVERVIEW.md](02_ARCHITECTURE_OVERVIEW.md#trace-context-propagation).**

## Failure Scenarios

### Payment Provider Failures

| Country | Failure Rate | Common Errors |
|---------|--------------|---------------|
| US | 5% | 400, 500, 503 |
| UK | 7% | 400, 404, 500 |
| DE | 6% | 500, 503 |
| FR | 8% | 400, 500, 503, 429 |
| JP | 10% | 500, 503 |
| BR | 15% | 400, 404, 500, 503 |
| IN | 12% | 400, 500, 503 |

### CRM Service

- 8% global failure rate
- Errors: 400, 404, 500, 503

### Inventory Service

- 10% global failure rate
- Errors: 400, 404, 500, 503

## Security

### Authentication

- Token-based authentication using opaque tokens
- Hardcoded tokens for demo purposes:
  - `user-token-123`
  - `admin-token-456`
  - `test-token-789`

### Protected Endpoints

- `/cart/add` - Add items to cart
- `/cart` - View cart
- `/checkout` - Process checkout
- `/orders` - View order history

### Public Endpoints

- `/health` - Health check
- `/products` - List products
- `/products/{id}` - Product details

## Scaling Considerations

### Current Setup (Demo)

- Single instance of each service
- In-memory caching (Redis)
- Single database instance
- No load balancing

### Production Recommendations

1. **Horizontal Scaling**
   - Multiple instances behind load balancer
   - Session affinity for cart operations
   - Distributed caching with Redis Cluster

2. **Database**
   - Read replicas for product queries
   - Connection pooling
   - Database sharding by country

3. **Observability**
   - Sampling for high-volume traces
   - Metrics aggregation
   - Log filtering and indexing

4. **High Availability**
   - Multi-region deployment
   - Circuit breakers for external services
   - Fallback mechanisms

## OpenTelemetry Configuration

### Instrumentation Libraries

**Python (FastAPI)**
- `opentelemetry-instrumentation-fastapi`
- `opentelemetry-instrumentation-sqlalchemy`
- `opentelemetry-instrumentation-redis`
- `opentelemetry-instrumentation-httpx`

**Go**
- `go.opentelemetry.io/contrib/instrumentation/github.com/gin-gonic/gin/otelgin`
- `go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp`

**.NET**
- `OpenTelemetry.Instrumentation.AspNetCore`
- `OpenTelemetry.Instrumentation.Http`

**Node.js**
- `@opentelemetry/auto-instrumentations-node`

### Exporters

All services export to OpenTelemetry Collector:
- Endpoint: `http://otel-collector:4317`
- Protocol: OTLP/gRPC
- Insecure: true (demo only)

## Resource Requirements

### Minimum

- CPU: 4 cores
- RAM: 8 GB
- Disk: 20 GB

### Recommended

- CPU: 8 cores
- RAM: 16 GB
- Disk: 50 GB
- SSD for database and time-series data

## Ports Reference

| Service | Port | Protocol |
|---------|------|----------|
| Frontend | 3001 | HTTP |
| Main Service | 8000 | HTTP |
| Payments Service | 8081 | HTTP |
| Promotions Service | 8082 | HTTP |
| Payment Provider | 3001 | HTTP |
| CRM Service | 3002 | HTTP |
| Inventory Service | 3003 | HTTP |
| PostgreSQL | 5432 | TCP |
| Redis | 6379 | TCP |
| OTEL Collector (gRPC) | 4317 | gRPC |
| OTEL Collector (HTTP) | 4318 | HTTP |
| Prometheus | 9090 | HTTP |
| Alertmanager | 9093 | HTTP |
| Tempo | 3200 | HTTP |
| Loki | 3100 | HTTP |
| Pyroscope | 4040 | HTTP |
| Grafana | 3000 | HTTP |

## Development Workflow

1. **Make changes to service code**
2. **Rebuild specific service**: `docker-compose up -d --build <service-name>`
3. **View logs**: `docker-compose logs -f <service-name>`
4. **Generate traffic**: `cd scripts && python3 generate-traffic.py`
5. **Check metrics**: Open Grafana at http://localhost:3000
6. **Explore traces**: Use Grafana Explore with Tempo data source
7. **Query logs**: Use Grafana Explore with Loki data source

## Common Issues and Solutions

**For comprehensive troubleshooting, see [09_TROUBLESHOOTING.md](09_TROUBLESHOOTING.md).**

### Quick Diagnostic Commands

```bash
# Check all services
docker-compose ps

# Verify OTEL Collector
curl http://localhost:8888/metrics | grep otelcol_receiver

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets | jq

# Test telemetry pipeline
./health-check.sh
```

## Alerting & SLO Configuration

### Alert Rules

The system implements **18 alert rules** across three categories:

**Service Health Alerts:**
- `HighErrorRate`: >5% error rate for 5 minutes
- `HighPaymentFailureRate`: >10% payment failure rate
- `CriticalPaymentFailureRateByCountry`: >20% failure rate per country
- `HighLatencyP95`: P95 latency >2s for 10 minutes
- `HighLatencyP99`: P99 latency >5s for 10 minutes
- `SlowPaymentProcessing`: P95 payment duration >3s
- `ServiceDown`: Service unavailable for 2+ minutes
- `HighExternalServiceFailureRate`: >15% external service failures

**Resource Alerts:**
- `HighDatabaseConnectionUsage`: >80% connection pool utilization
- `HighRedisMemoryUsage`: >85% memory usage
- `OTELCollectorHighDropRate`: >5% span drop rate
- `OTELCollectorHighMemory`: >500MB memory usage

**Business Alerts:**
- `LowCheckoutConversionRate`: <10% conversion for 30 minutes
- `NoTrafficDetected`: No requests for 10 minutes
- `AbandonedCartsIncreasing`: >100 active carts

**SLO Violation Alerts:**
- `AvailabilitySLOBreach`: <99.9% availability (SLO: 99.9%)
- `LatencySLOBreach`: P95 latency >1s (SLO: 95% < 1s)
- `PaymentSLOBreach`: <90% payment success rate (SLO: >90%)

### Alert Routing

Alerts are routed by:
- **Severity**: critical, warning, info
- **Team**: platform, payments, business, observability
- **SLO**: availability, latency, payment_success

### Inhibition Rules

- Critical alerts suppress warning alerts for same service
- Service down alerts suppress high error rate alerts

### Service Level Objectives (SLOs)

**Availability SLO**: 99.9% uptime over 30 days
- Error budget: 43.2 minutes of downtime per month
- Burn rate tracking: 1h, 6h, 24h windows

**Latency SLO**: 95% of requests complete in <1s
- Measured using P95 latency
- Tracked per service and globally

**Payment Success SLO**: >90% payment success rate
- Measured over 1-hour rolling window
- Country-specific tracking available

### Grafana Dashboards

**WebStore Overview**:
- Business metrics (cart additions, checkouts)
- Country-specific performance
- Basic service health

**SLO Tracking & Error Budgets**:
- Real-time SLI measurements
- Error budget remaining and burn rate
- Multi-timeframe availability trends
- Latency percentile tracking
- Payment success by country

**Service Health & Dependencies**:
- Request rate (RPS) per service
- Error rate monitoring
- Latency percentiles (P50, P95, P99)
- Service status table
- External dependency health
- Database and Redis metrics
- Top endpoints by traffic

## Future Enhancements

- [ ] Kubernetes deployment manifests
- [ ] Helm charts
- [ ] OnCall integration
- [ ] Custom Grafana plugins
- [ ] Performance benchmarking
- [ ] Load testing scenarios
- [ ] Chaos engineering examples
- [ ] Enhanced trace sampling (value-based, user-based)
- [ ] Log-based alerts
- [ ] Security monitoring metrics
- [ ] Cost tracking metrics
