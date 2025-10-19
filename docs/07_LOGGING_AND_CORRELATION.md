# Logging and Correlation

**Reading time**: 18 minutes

Learn how to implement structured logging with trace correlation across multiple programming languages and query logs effectively.

## Table of Contents

- [Introduction to Structured Logging](#introduction-to-structured-logging)
- [Trace-Log Correlation](#trace-log-correlation)
- [Language-Specific Implementation](#language-specific-implementation)
- [Querying Logs with LogQL](#querying-logs-with-logql)
- [Log Levels and Best Practices](#log-levels-and-best-practices)
- [Hands-On Exercise](#hands-on-exercise)

## Introduction to Structured Logging

**Structured logging** uses JSON format instead of plain text, making logs machine-readable and easier to query.

### Why Structured Logging?

**Traditional logging** (hard to parse):
```
2025-10-19 14:23:15 - Order 12345 created by user 789 with total $99.99
```

**Structured logging** (machine-readable):
```json
{
  "timestamp": "2025-10-19T14:23:15.000Z",
  "level": "INFO",
  "msg": "Order created successfully",
  "service": "main-service",
  "order_id": "12345",
  "user_id": "789",
  "total_amount": 99.99,
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7"
}
```

### Benefits

- **Queryable**: Filter by any field (`user_id`, `order_id`, etc.)
- **Correlated**: Link logs to traces via `trace_id`
- **Consistent**: Same structure across all services
- **Analyzable**: Easy to aggregate and visualize

## Trace-Log Correlation

The most powerful feature is linking logs to distributed traces using OpenTelemetry trace context.

### How It Works

When a request enters the system:

1. **OpenTelemetry creates a trace** with unique `trace_id`
2. **This trace_id propagates** through all service calls
3. **Logging frameworks inject trace_id** into every log entry
4. **You can jump from logs to traces** (and vice versa) in Grafana

### Example Flow

```
User Request
    ↓
trace_id: 4bf92f3577b34da6a3ce929d0e0e4736
    ↓
┌─────────────────────────────────────────┐
│ Main Service                            │
│ LOG: {"msg": "Processing checkout",     │
│       "trace_id": "4bf92f35...",        │
│       "order_id": "12345"}              │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Payments Service                        │
│ LOG: {"msg": "Payment processing",      │
│       "trace_id": "4bf92f35...",        │
│       "payment_id": "PAY-789"}          │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Payment Provider                        │
│ LOG: {"msg": "Payment failed",          │
│       "trace_id": "4bf92f35...",        │
│       "error": "Insufficient funds"}    │
└─────────────────────────────────────────┘
```

All three logs share the same `trace_id`, creating a complete story.

## Language-Specific Implementation

Our project demonstrates structured logging in 4 languages. Each uses best-in-class libraries with OpenTelemetry integration.

### Python (Main Service) - JSON Logger

**File**: `/services/main-service/logging_config.py`

Uses `python-json-logger` with custom formatter to inject trace context:

```python
from pythonjsonlogger import jsonlogger
from opentelemetry import trace

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter that includes trace context."""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)

        # Add trace context if available
        span = trace.get_current_span()
        if span and span.get_span_context().is_valid:
            ctx = span.get_span_context()
            log_record['trace_id'] = format(ctx.trace_id, '032x')
            log_record['span_id'] = format(ctx.span_id, '016x')

        # Add service name
        log_record['service'] = 'main-service'
```

**Usage in application code**:
```python
import logging

logger = logging.getLogger(__name__)

# Info with context
logger.info("Order created", extra={
    "order_id": order.id,
    "user_id": user_id,
    "total_amount": total
})

# Error with details
logger.error("Payment failed", extra={
    "error": str(e),
    "payment_id": payment_id,
    "retry_count": retry_count
})
```

**Key features**:
- Automatic trace_id injection
- ISO 8601 timestamps
- Configurable log levels per module
- Reduced noise from noisy libraries (uvicorn, httpx)

### Go (Payments Service) - Zap

**File**: `/services/payments-service/logging/logging.go`

Uses Uber's `zap` logger with production configuration:

```go
package logging

import (
    "go.opentelemetry.io/otel/trace"
    "go.uber.org/zap"
)

func InitLogger() error {
    config := zap.NewProductionConfig()
    config.EncoderConfig.TimeKey = "timestamp"
    config.EncoderConfig.EncodeTime = zapcore.ISO8601TimeEncoder
    config.EncoderConfig.MessageKey = "msg"
    config.EncoderConfig.LevelKey = "level"

    logger, err = config.Build(zap.AddCallerSkip(1))
    return err
}

func WithTraceContext(span trace.Span) *zap.Logger {
    if span.SpanContext().IsValid() {
        ctx := span.SpanContext()
        return logger.With(
            zap.String("trace_id", ctx.TraceID().String()),
            zap.String("span_id", ctx.SpanID().String()),
        )
    }
    return logger
}
```

**Usage in handlers**:
```go
import "go.uber.org/zap"

// Simple log
logging.Info("Payment processed",
    zap.String("payment_id", paymentID),
    zap.Float64("amount", amount),
    zap.String("country", country))

// Error with trace context
span := trace.SpanFromContext(ctx)
logger := logging.WithTraceContext(span)
logger.Error("Payment provider error",
    zap.Error(err),
    zap.String("provider", providerName))
```

**Key features**:
- Zero-allocation JSON encoding (high performance)
- Structured fields with type safety
- Production-optimized configuration
- Automatic trace context propagation

### C# (Promotions Service) - Serilog

**File**: `/services/promotions-service/Program.cs`

Uses Serilog with `CompactJsonFormatter`:

```csharp
using Serilog;
using Serilog.Formatting.Compact;

// Configure at startup
Log.Logger = new LoggerConfiguration()
    .Enrich.FromLogContext()
    .Enrich.WithProperty("service", "promotions-service")
    .WriteTo.Console(new CompactJsonFormatter())
    .CreateLogger();

builder.Host.UseSerilog();
```

**Usage in controllers**:
```csharp
// Structured properties with message template
Log.Information("Promotion applied for {UserId} with {PromotionId}",
    userId, promotionId);

// Error with exception
try
{
    await ApplyPromotion(promotionId);
}
catch (Exception ex)
{
    Log.Error(ex, "Failed to apply promotion {PromotionId} for user {UserId}",
        promotionId, userId);
}
```

**Key features**:
- Message templates with destructuring
- Automatic exception serialization
- LogContext enrichment (automatic trace_id via ASP.NET Core)
- Compact JSON output

### Node.js (External Services) - Pino

**File**: `/services/external/payment-provider/index.js`

Uses `pino` for high-performance logging:

```javascript
const pino = require('pino');

const logger = pino({
  formatters: {
    level: (label) => ({ level: label })
  },
  base: {
    service: 'payment-provider',
  },
  timestamp: pino.stdTimeFunctions.isoTime,
});
```

**Usage in routes**:
```javascript
// Info with structured data
logger.info({
    transaction_id: transactionId,
    amount,
    currency,
    country
}, 'Payment successful');

// Error logging
logger.error({
    amount,
    currency,
    country,
    status: error.status,
    error: error.message
}, 'Payment failed');
```

**Key features**:
- Extremely fast (faster than console.log)
- Child loggers for request context
- ISO timestamp formatting
- Automatic serialization of objects

## Querying Logs with LogQL

**LogQL** is Grafana Loki's query language, similar to PromQL for logs.

### Basic Queries

**Filter by service**:
```logql
{service_name="main-service"}
```

**Filter by multiple labels**:
```logql
{service_name="payments-service", level="ERROR"}
```

**Text search** (case-insensitive):
```logql
{service_name="main-service"} |= "checkout"
```

**Exclude text**:
```logql
{service_name="main-service"} != "health"
```

### JSON Field Extraction

Parse JSON logs and filter by fields:

```logql
# Find all logs with specific user_id
{service_name="main-service"}
| json
| user_id="user-123"

# Find errors with payment_id
{service_name="payments-service"}
| json
| level="ERROR"
| payment_id != ""

# Find slow operations (duration > 1000ms)
{service_name="main-service"}
| json
| duration_ms > 1000
```

### Aggregations and Metrics

**Count logs per service**:
```logql
sum by (service_name) (
    rate({job="otel-collector"}[5m])
)
```

**Error rate**:
```logql
sum by (service_name) (
    rate({job="otel-collector"} | json | level="ERROR" [5m])
)
```

**95th percentile of duration**:
```logql
quantile_over_time(0.95,
    {service_name="main-service"}
    | json
    | unwrap duration_ms [5m]
)
```

### Trace Correlation Queries

**Find all logs for a specific trace**:
```logql
{job="otel-collector"}
| json
| trace_id="4bf92f3577b34da6a3ce929d0e0e4736"
```

**Find errors with their traces**:
```logql
{service_name="payments-service"}
| json
| level="ERROR"
| trace_id != ""
```

### Advanced Patterns

**Pattern matching**:
```logql
{service_name="main-service"}
| json
| msg =~ "(?i)payment.*failed"  # Regex: case-insensitive
```

**Multi-stage pipeline**:
```logql
{service_name="main-service"}
| json
| level="ERROR"
| line_format "{{.timestamp}} [{{.service}}] {{.msg}} - {{.error}}"
```

**Time-based filtering**:
```logql
{service_name="main-service"}
| json
| __timestamp__ > now() - 1h
```

## Log Levels and Best Practices

### Standard Log Levels

Follow consistent standards across all services:

| Level | When to Use | Example |
|-------|-------------|---------|
| **DEBUG** | Development only, detailed diagnostics | Variable values, loop iterations |
| **INFO** | Normal operations, key events | Request started, order created, payment successful |
| **WARNING** | Unexpected but recoverable | Retry attempted, cache miss, deprecated API used |
| **ERROR** | Request/operation failed | Payment failed, database error, external API down |
| **FATAL** | Application cannot continue | Database unavailable, config missing, startup failed |

### Best Practices

#### ✅ DO

**1. Use structured fields**:
```python
# Good
logger.info("Order created", extra={"order_id": 12345, "user_id": 789})

# Bad
logger.info(f"Order 12345 created by user 789")
```

**2. Include trace context**:
```python
# Automatically included with our setup
logger.info("Processing payment")  # Includes trace_id, span_id
```

**3. Log errors with context**:
```python
# Good
logger.error("Payment failed", extra={
    "error": str(e),
    "payment_id": payment_id,
    "amount": amount,
    "country": country
})
```

**4. Use appropriate log levels**:
```python
logger.info("User logged in")        # ✓ Normal operation
logger.warning("Cache miss")          # ✓ Unexpected but OK
logger.error("Payment failed")        # ✓ Request failed
```

#### ❌ DON'T

**1. Don't log sensitive data**:
```python
# Never do this!
logger.info(f"User password: {password}")
logger.info(f"Credit card: {cc_number}")
logger.info(f"API key: {api_key}")
```

**2. Don't log in tight loops**:
```python
# Bad - generates too many logs
for item in items:
    logger.debug(f"Processing item {item.id}")

# Good - log summary
logger.info("Processing batch", extra={"item_count": len(items)})
```

**3. Don't use wrong log levels**:
```python
logger.error("User logged in")    # ✗ Not an error!
logger.debug("Payment failed")    # ✗ Should be ERROR
```

**4. Don't log huge payloads**:
```python
# Bad
logger.info(f"Response: {huge_json_response}")

# Good
logger.info("Request completed", extra={
    "status": response.status_code,
    "size_bytes": len(response.content)
})
```

### Reducing Noisy Logs

Configure logging levels per module:

**Python**:
```python
# Silence noisy libraries
logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
```

**Go**:
```go
// Use zap's sampling to reduce high-frequency logs
sampledLogger := logger.WithOptions(zap.WrapCore(func(core zapcore.Core) zapcore.Core {
    return zapcore.NewSamplerWithOptions(core, time.Second, 100, 10)
}))
```

## Hands-On Exercise

### Exercise 1: Find a Failed Payment

**Goal**: Use logs to investigate a failed payment and find the trace.

1. **Generate some traffic**:
```bash
cd scripts
python3 generate-traffic.py --users 3 --duration 30
```

2. **Open Grafana**: http://localhost:3000
   - Navigate to **Explore**
   - Select **Loki** data source

3. **Query failed payments**:
```logql
{service_name="payments-service"}
| json
| status="failed"
```

4. **Find the trace_id** in the log entry

5. **Jump to trace**:
   - Copy the `trace_id` value
   - Switch data source to **Tempo**
   - Search by Trace ID
   - View the complete trace

### Exercise 2: Analyze Error Patterns

**Goal**: Find which country has the most payment failures.

1. **Query payment failures by country**:
```logql
sum by (country) (
    count_over_time(
        {service_name="payments-service"}
        | json
        | status="failed" [5m]
    )
)
```

2. **Visualize over time**:
```logql
sum by (country) (
    rate({service_name="payments-service"}
        | json
        | status="failed" [1m])
)
```

3. **Find specific error messages**:
```logql
{service_name="payment-provider"}
| json
| level="error"
```

### Exercise 3: Monitor Service Health

**Goal**: Check if all services are logging correctly.

1. **Query log volume by service**:
```logql
sum by (service_name) (
    rate({job="otel-collector"}[1m])
)
```

2. **Find services with errors**:
```logql
sum by (service_name) (
    rate({job="otel-collector"} | json | level="ERROR" [5m])
)
```

3. **Calculate error ratio**:
```logql
sum by (service_name) (
    rate({job="otel-collector"} | json | level="ERROR" [5m])
)
/
sum by (service_name) (
    rate({job="otel-collector"}[5m])
)
```

### Exercise 4: Debug Slow Requests

**Goal**: Find slow operations using duration logs.

1. **Find requests over 1 second**:
```logql
{service_name="main-service"}
| json
| duration_ms > 1000
```

2. **Get the trace_id** from the slow request

3. **Analyze the trace** to see which service caused the delay

## Viewing Logs

### Via Docker Compose

```bash
# View logs for specific service
docker-compose logs -f main-service

# View last 100 lines
docker-compose logs --tail=100 main-service

# View with timestamps
docker-compose logs --timestamps payments-service

# Follow multiple services
docker-compose logs -f main-service payments-service
```

### Via Grafana Loki

Benefits of using Loki over Docker logs:
- **Persistent storage**: Logs survive container restarts
- **Powerful queries**: LogQL for filtering and aggregation
- **Trace correlation**: Click trace_id to jump to trace
- **Time-based search**: Query specific time ranges
- **Aggregations**: Count, rate, percentiles

## Related Documentation

For more details on logging standards, see:
- **[LOGGING_STANDARDS.md](LOGGING_STANDARDS.md)**: Detailed logging conventions and alert rules
- **[ARCHITECTURE.md](ARCHITECTURE.md)**: How logs flow through the stack
- **[05_DISTRIBUTED_TRACING.md](05_DISTRIBUTED_TRACING.md)**: Understanding trace context

## Summary

You learned:

- **Structured logging** with JSON format across Python, Go, C#, and Node.js
- **Trace-log correlation** using OpenTelemetry trace_id
- **LogQL queries** for filtering, searching, and aggregating logs
- **Best practices** for log levels and what to log
- **Hands-on skills** for debugging with correlated logs and traces

**Key takeaways**:
1. Always use structured logging with consistent field names
2. Include trace context for correlation
3. Use appropriate log levels
4. Never log sensitive data
5. Combine logs and traces for complete observability

---

**Next**: [Alerting and SLOs](07_ALERTING_AND_SLOS.md) →
