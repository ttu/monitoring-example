# Logging Standards - Technical Reference

> **Note**: For an introduction to structured logging and trace correlation, see [06_LOGGING_AND_CORRELATION.md](06_LOGGING_AND_CORRELATION.md).
> This document provides **detailed technical specifications** and deep-dive information.

## Log Level Standards

All services follow a consistent log level hierarchy:

### Log Levels by Severity

| Level | Python | Go (Zap) | C# (Serilog) | Node.js (Pino) | When to Use |
|-------|--------|----------|--------------|----------------|-------------|
| **DEBUG** | `logging.DEBUG` | `Debug()` | `Debug` | `debug` | Detailed information for diagnosing problems. Never in production. |
| **INFO** | `logging.INFO` | `Info()` | `Information` | `info` | Confirmation that things are working as expected. Normal operations. |
| **WARNING** | `logging.WARNING` | `Warn()` | `Warning` | `warn` | Something unexpected happened, but the application can continue. |
| **ERROR** | `logging.ERROR` | `Error()` | `Error` | `error` | A serious problem occurred. The function/request failed. |
| **CRITICAL/FATAL** | `logging.CRITICAL` | `Fatal()` | `Fatal` | `fatal` | Application cannot continue. Immediate action required. |

### Default Log Levels by Environment

- **Development**: `DEBUG` or `INFO`
- **Staging**: `INFO`
- **Production**: `INFO`

## Structured Logging Field Specifications

### Required Fields (All Services)

| Field | Type | Format | Description |
|-------|------|--------|-------------|
| `timestamp` | String | ISO 8601 | `2025-10-19T12:00:00.000Z` |
| `level` | String | Upper case | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `FATAL` |
| `msg` | String | Plain text | Human-readable message |
| `service` | String | Kebab case | Service identifier (e.g., `main-service`) |

### Optional/Contextual Fields

| Field | Type | When to Include | Example |
|-------|------|----------------|---------|
| `trace_id` | String (32 hex) | When OpenTelemetry context available | `4bf92f3577b34da6a3ce929d0e0e4736` |
| `span_id` | String (16 hex) | When OpenTelemetry context available | `00f067aa0ba902b7` |
| `user_id` | String | For user-specific operations | `user-123` |
| `request_id` | String | For HTTP requests | `req-789` |
| `error` | String | ERROR/FATAL levels only | Exception message |
| `stack_trace` | String | ERROR/FATAL levels only | Full stack trace |
| `duration_ms` | Number | For timed operations | `123` |
| `http_method` | String | HTTP requests | `POST`, `GET`, etc. |
| `http_path` | String | HTTP requests | `/api/orders` |
| `http_status` | Number | HTTP responses | `200`, `404`, `500` |
| `order_id` | String | Order operations | `ORD-12345` |
| `payment_id` | String | Payment operations | `PAY-67890` |
| `country` | String | Geographic operations | `US`, `GB`, `DE` |

## Service-Specific Configuration

### Python (main-service)

Location: `services/main-service/logging_config.py`

```python
import logging
from pythonjsonlogger import jsonlogger

# Log level: INFO
root_logger.setLevel(logging.INFO)

# Library noise reduction
logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
```

**Usage:**
```python
logger = logging.getLogger(__name__)
logger.info("Order created", extra={"order_id": order.id, "user_id": user.id})
logger.error("Payment failed", extra={"error": str(e), "payment_id": payment_id})
```

### Go (payments-service)

Location: `services/payments-service/logging/logging.go`

```go
// Uses zap with production config
config := zap.NewProductionConfig()
config.EncoderConfig.TimeKey = "timestamp"
config.EncoderConfig.MessageKey = "msg"
config.EncoderConfig.LevelKey = "level"
```

**Usage:**
```go
logging.Info("Payment processed",
    zap.String("payment_id", paymentID),
    zap.String("country", country),
    zap.Float64("amount", amount))

logging.Error("Payment provider error",
    zap.Error(err),
    zap.String("provider", providerName))
```

### C# (promotions-service)

Location: `services/promotions-service/Program.cs`

```csharp
// Uses Serilog with compact JSON formatter
Log.Logger = new LoggerConfiguration()
    .Enrich.FromLogContext()
    .Enrich.WithProperty("service", "promotions-service")
    .WriteTo.Console(new CompactJsonFormatter())
    .CreateLogger();
```

**Usage:**
```csharp
Log.Information("Promotion checked for {UserId}", userId);
Log.Error(ex, "Failed to apply promotion {PromotionId}", promotionId);
```

### Node.js (external services)

Location: `services/external/*/index.js`

```javascript
// Uses pino for structured logging
const logger = require('pino')({
    level: process.env.LOG_LEVEL || 'info',
    formatters: {
        level: (label) => { return { level: label } }
    }
});
```

**Usage:**
```javascript
logger.info({ user_id, order_id }, 'Order recorded');
logger.error({ error: err.message, status: err.status }, 'Failed to process');
```

## Log-Based Alerting

### Loki Recording Rules

Log metrics are recorded in Loki for alerting. See `loki-rules.yaml`:

- `log:errors:rate5m` - Error log rate by service
- `log:warnings:rate5m` - Warning log rate by service
- `log:fatal:rate5m` - Fatal/critical log rate by service
- `log:error_ratio:rate5m` - Error percentage by service

### Alert Rules

Configured in `loki-rules.yaml` and `prometheus-alerts.yml`:

| Alert | Condition | Severity | Description |
|-------|-----------|----------|-------------|
| `HighErrorLogRate` | > 1 error/s for 5m | Warning | Service logging excessive errors |
| `FatalErrorsDetected` | > 0 fatal/s for 1m | Critical | Fatal errors detected |
| `HighErrorLogRatio` | > 5% errors for 10m | Warning | High percentage of logs are errors |
| `ServiceNotLogging` | 0 logs for 5m | Warning | Service stopped logging (may be down) |
| `LogVolumeSpikeDetected` | 5x avg for 5m | Warning | Unusual log volume (potential issue loop) |

## LogQL Query Examples

### Basic Filtering

```logql
# All logs from a service
{service_name="main-service"}

# Filter by log level
{service_name="main-service"} | json | level="ERROR"

# Multiple label filters
{service_name="payments-service", level="ERROR"}

# Text search (case-insensitive)
{service_name="main-service"} |= "checkout"

# Exclude text
{service_name="main-service"} != "health"
```

### JSON Field Extraction and Filtering

```logql
# Find logs for specific user
{service_name="main-service"} | json | user_id="user-123"

# Find errors with payment_id present
{service_name="payments-service"} | json | level="ERROR" | payment_id != ""

# Find slow operations
{service_name="main-service"} | json | duration_ms > 1000

# Find specific trace
{job="otel-collector"} | json | trace_id="4bf92f3577b34da6a3ce929d0e0e4736"
```

### Aggregations and Metrics from Logs

```logql
# Count logs per service (rate over 5m)
sum by (service_name) (rate({job="otel-collector"}[5m]))

# Error rate by service
sum by (service_name) (
    rate({job="otel-collector"} | json | level="ERROR" [5m])
)

# 95th percentile of duration
quantile_over_time(0.95,
    {service_name="main-service"}
    | json
    | unwrap duration_ms [5m]
)

# Count errors by country
sum by (country) (
    count_over_time(
        {service_name="payments-service"}
        | json
        | status="failed" [5m]
    )
)
```

### Pattern Matching

```logql
# Regex matching (case-insensitive)
{service_name="main-service"}
| json
| msg =~ "(?i)payment.*failed"

# Multi-stage pipeline
{service_name="main-service"}
| json
| level="ERROR"
| line_format "{{.timestamp}} [{{.service}}] {{.msg}} - {{.error}}"

# Time-based filtering
{service_name="main-service"}
| json
| __timestamp__ > now() - 1h
```

## Best Practices and Anti-Patterns

### DO ✅

- **Use structured logging** with consistent field names across all services
- **Include trace context** (trace_id, span_id) when available for correlation
- **Log errors with full context**: error message, stack trace, relevant IDs (order_id, user_id, etc.)
- **Use appropriate log levels**: Reserve ERROR for actual failures, not informational events
- **Include duration_ms** for operations that may be slow
- **Sanitize sensitive data**: Never log passwords, tokens, credit cards, API keys
- **Be concise and actionable**: Log messages should clearly indicate what happened and why
- **Use log level per module**: Reduce noise from chatty libraries
- **Include business context**: user_id, order_id, country help with debugging

### DON'T ❌

- **Don't log PII** (personally identifiable information) without anonymization
- **Don't log in tight loops** without rate limiting (causes log volume spikes)
- **Don't use DEBUG level in production** (significant performance impact)
- **Don't log sensitive credentials** (passwords, API keys, tokens)
- **Don't log full request/response bodies** (use DEBUG mode only if necessary)
- **Avoid string concatenation** in log messages (use structured fields instead)
- **Don't log excessive payloads**: Summarize large objects (log size, not content)
- **Don't use wrong log levels**: `ERROR` for user login is incorrect; use `INFO`

## Language-Specific Best Practices

### Python - Extra Context Pattern

```python
# ✅ Good: Structured with extra dict
logger.info("Order created successfully",
    extra={
        "order_id": order_id,
        "user_id": user_id,
        "total_amount": total,
        "duration_ms": duration
    })

# ❌ Bad: String interpolation
logger.info(f"Order created: {order_id}")
```

### Go - Zap Structured Fields

```go
// ✅ Good: Typed fields
logging.Info("Payment processed",
    zap.String("payment_id", paymentID),
    zap.Float64("amount", amount),
    zap.String("country", country))

// ❌ Bad: Concatenated string
log.Printf("Payment %s processed for %f", paymentID, amount)
```

### C# - Serilog Message Templates

```csharp
// ✅ Good: Message template with placeholders
Log.Information("Order {OrderId} created for user {UserId}", orderId, userId);

// ❌ Bad: String interpolation
Log.Information($"Order {orderId} created for user {userId}");
```

### Node.js - Pino Object Syntax

```javascript
// ✅ Good: Object first, message second
logger.info({ order_id, user_id, amount }, 'Order created');

// ❌ Bad: String concatenation
logger.info(`Order ${order_id} created`);
```

## Troubleshooting Logging Issues

### No logs appearing in Loki

**Diagnostic steps:**

1. Check OTEL Collector is running and healthy:
   ```bash
   docker-compose ps otel-collector
   curl http://localhost:13133  # Health endpoint
   ```

2. Verify OTEL Collector receiving logs:
   ```bash
   docker-compose logs otel-collector | grep -i loki
   # Should see: "Logs exported successfully"
   ```

3. Check service logs are JSON formatted:
   ```bash
   docker-compose logs main-service | head -5
   # Should see JSON objects, not plain text
   ```

4. Verify OTEL Collector config exports to Loki:
   ```yaml
   # In otel-collector-config.yaml
   exporters:
     loki:
       endpoint: "http://loki:3100/loki/api/v1/push"
   ```

5. Check Loki is accepting data:
   ```bash
   docker-compose logs loki | grep -i ingester
   ```

### High log volume / Log volume spike

**Symptoms:**
- Loki ingestion limits exceeded
- `HighLogVolumeSpikeDetected` alert firing
- Service logs show "rate limit exceeded"

**Common causes:**
1. Debug logs enabled in production
2. Log loops (error handlers logging errors)
3. High-frequency log statements in tight loops
4. External service failures causing retry storms

**Solutions:**

```python
# Reduce noisy library logging
logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)

# Add rate limiting to noisy statements
from time import time
last_log = 0
if time() - last_log > 60:  # Log once per minute
    logger.warning("Still processing...")
    last_log = time()
```

**Loki ingestion limits** (`loki.yaml`):
```yaml
limits_config:
  ingestion_rate_mb: 10  # MB per second
  ingestion_burst_size_mb: 20
  per_stream_rate_limit: 5MB
```

### Alerts not firing

**Diagnostic steps:**

1. Verify Loki recording rules are loaded:
   ```bash
   docker-compose logs loki | grep -i ruler
   # Should see: "ruler: recording rules loaded"
   ```

2. Check Alertmanager connection in `loki.yaml`:
   ```yaml
   ruler:
     alertmanager_url: http://alertmanager:9093
   ```

3. Test LogQL query manually in Grafana Explore:
   ```logql
   sum by (service_name) (
       rate({job="otel-collector"} | json | level="ERROR" [5m])
   )
   ```

4. Verify alert expression syntax in `prometheus-alerts.yml`:
   ```yaml
   - alert: HighErrorLogRate
     expr: log:errors:rate5m > 1  # Correct recording rule reference
   ```

5. Check Alertmanager is receiving alerts:
   ```bash
   curl http://localhost:9093/api/v2/alerts | jq
   ```

## Related Documentation

- **[06_LOGGING_AND_CORRELATION.md](06_LOGGING_AND_CORRELATION.md)**: Introduction to structured logging and trace correlation
- **[ARCHITECTURE.md](ARCHITECTURE.md)**: Overall system architecture
- **[prometheus-alerts.yml](../prometheus-alerts.yml)**: All alert rules
- **[loki-rules.yaml](../loki-rules.yaml)**: Log-based metrics and alerts (if configured)
- **[otel-collector-config.yaml](../otel-collector-config.yaml)**: OTEL Collector log processing pipeline
