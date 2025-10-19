# Distributed Tracing

**Reading time**: 20 minutes

Learn how to use distributed tracing to understand request flows across microservices and debug production issues.

## Table of Contents

- [What is Distributed Tracing?](#what-is-distributed-tracing)
- [Trace Components](#trace-components)
- [Trace Context Propagation](#trace-context-propagation)
- [Using Tempo in Grafana](#using-tempo-in-grafana)
- [Trace Sampling](#trace-sampling)
- [Debugging with Traces](#debugging-with-traces)
- [Best Practices](#best-practices)

## What is Distributed Tracing?

**Distributed tracing** tracks requests as they flow through multiple services in a distributed system.

### The Problem

In a monolithic application, debugging is straightforward - one stack trace shows the entire request flow. In microservices:

```
User Request
    ↓
❓ Which service failed?
❓ Where is the slow operation?
❓ What was the complete path?
❓ Which external API caused the error?
```

### The Solution

Distributed tracing creates a single "trace" that spans all services:

```
Trace ID: 4bf92f3577b34da6a3ce929d0e0e4736

Frontend (50ms)
    ↓
Main Service (350ms)
    ├─→ PostgreSQL query (45ms)
    ├─→ Redis get (2ms)
    ├─→ Inventory Service (80ms) ✓
    ├─→ Payments Service (180ms)
    │   └─→ Payment Provider (150ms) ❌ ERROR
    └─→ CRM System (30ms) ✓
```

**Benefits**:
- See the complete request journey
- Identify bottlenecks instantly
- Understand service dependencies
- Debug errors with full context

## Trace Components

### Trace

A **trace** represents a complete request journey:
- Unique **trace ID**: `4bf92f3577b34da6a3ce929d0e0e4736`
- Collection of **spans**
- Duration: Total time from start to finish

### Span

A **span** represents a single operation:
- Unique **span ID**: `00f067aa0ba902b7`
- **Parent span ID**: Links to calling span
- **Operation name**: "POST /checkout", "db_query", "http_call"
- **Start time** and **duration**
- **Attributes**: Metadata about the operation
- **Status**: OK, ERROR, UNSET

### Example Trace Hierarchy

```
Trace: 4bf92f3577b34da6a3ce929d0e0e4736 (500ms total)
│
├─ Span: "POST /checkout" (500ms)
│  ├─ service: main-service
│  ├─ http.method: POST
│  ├─ http.status_code: 200
│  │
│  ├─ Span: "db_query: get_cart" (45ms)
│  │  ├─ db.system: postgresql
│  │  └─ db.statement: SELECT * FROM cart...
│  │
│  ├─ Span: "redis: get_user_session" (2ms)
│  │
│  ├─ Span: "HTTP POST inventory-system" (80ms)
│  │  └─ http.url: http://inventory-system:3003/check
│  │
│  ├─ Span: "HTTP POST payments-service" (180ms)
│  │  │
│  │  └─ Span: "HTTP POST payment-provider" (150ms)
│  │     ├─ http.status_code: 500
│  │     └─ error: Payment declined
│  │
│  └─ Span: "HTTP POST crm-system" (30ms)
```

## Trace Context Propagation

### W3C Trace Context Standard

All services propagate trace context using the **W3C Trace Context** standard via HTTP headers:

```http
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
             │  └──────────────┬──────────────┘ └──────┬──────┘ └┬┘
             │            trace-id                  span-id    flags
             └─ version
```

**Components**:
- **version**: `00` (current version)
- **trace-id**: 32 hex characters (globally unique)
- **parent-id**: 16 hex characters (current span ID)
- **flags**: Sampling decision

### How It Works

```
1. Frontend makes request
   ├─ Generates: trace_id=abc123
   └─ Sends: traceparent: 00-abc123-span1-01

2. Main Service receives request
   ├─ Reads trace_id from header
   ├─ Creates child span: span_id=span2, parent=span1
   └─ Calls Payments Service
      └─ Sends: traceparent: 00-abc123-span2-01

3. Payments Service receives request
   ├─ Reads trace_id from header
   ├─ Creates child span: span_id=span3, parent=span2
   └─ Calls Payment Provider
      └─ Sends: traceparent: 00-abc123-span3-01

Result: Single trace (abc123) with 3 spans showing full path
```

### Automatic Propagation

OpenTelemetry auto-instrumentation **automatically** propagates context:

```python
# Python (FastAPI) - Automatic
@app.post("/checkout")
async def checkout():
    # Context automatically extracted from request headers
    # Context automatically injected into outgoing HTTP calls
    response = await httpx.post("http://payments-service/process")
```

```go
// Go (Gin) - Automatic
func processPayment(c *gin.Context) {
    // Context automatically extracted
    // Context automatically propagated in HTTP client
    resp, _ := http.Post("http://payment-provider/charge", ...)
}
```

## Using Tempo in Grafana

### Accessing Tempo

1. Open Grafana: http://localhost:3000
2. Click **Explore** (compass icon)
3. Select **Tempo** data source

### Search Options

**Search by Service**:
1. Click **Search**
2. Select **Service Name**: `main-service`
3. Click **Run query**

**Search by Tags**:
```
http.status_code = 500
http.method = POST
status = error
```

**Search by Trace ID**:
```
4bf92f3577b34da6a3ce929d0e0e4736
```

**Search by Duration**:
```
Duration > 1s
```

### Reading a Trace

**Trace View**:
```
┌─────────────────────────────────────────────────────────┐
│ Trace: 4bf92f3577b34da6                                │
│ Duration: 500ms                                         │
│ Services: 4  Spans: 8                                   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ main-service                                            │
│ ▼ POST /checkout ──────────────────────────── 500ms    │
│   │                                                     │
│   ├─ db_query: get_cart ──── 45ms                     │
│   │                                                     │
│   ├─ redis: get_session ─ 2ms                         │
│   │                                                     │
│   ├─ inventory-system                                  │
│   │ ▼ POST /check ────────────── 80ms                 │
│   │                                                     │
│   ├─ payments-service                                  │
│   │ ▼ POST /process ────────────────── 180ms          │
│   │   │                                                │
│   │   └─ payment-provider                              │
│   │     ▼ POST /charge ───────────── 150ms ❌         │
│   │                                                     │
│   └─ crm-system                                        │
│     ▼ POST /update ──────── 30ms                      │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Span Details**:
Click any span to see:
- **Attributes**: HTTP method, URL, status code
- **Events**: Exceptions, custom events
- **Logs**: Related log entries (via trace_id)
- **Duration**: Absolute and relative

### Trace to Metrics

Click **Related Metrics** to see:
- Request rate around this trace
- Error rate at the time
- Latency percentiles

### Trace to Logs

Click **Logs for this span** to jump to related logs in Loki:
```logql
{service_name="main-service"} | json | trace_id="4bf92f3577b34da6"
```

## Trace Sampling

### Why Sample?

**Problem**: Storing 100% of traces is expensive:
- High storage costs
- High network bandwidth
- Most traces are identical

**Solution**: Sample intelligently:
- Keep all important traces (errors, slow requests)
- Sample a percentage of normal traces
- Reduce storage by 70%+ while keeping critical data

### Sampling Strategies

**Head Sampling** (decided when trace starts):
```
✅ Fast - Decision at trace creation
❌ Can't sample based on outcome (error, latency)
❌ May miss important traces
```

**Tail Sampling** (decided after trace completes):
```
✅ Sample based on outcome (errors, latency, business value)
✅ Guaranteed to keep important traces
❌ Requires buffering (more memory)
```

### This Project's Sampling

We use **tail sampling** in the OTLP Collector with 12 policies:

[otel-collector-config.yaml](../otel-collector-config.yaml):
```yaml
tail_sampling:
  policies:
    # Always keep errors
    - name: errors-always
      type: status_code
      status_code: {status_codes: [ERROR]}

    # Always keep slow requests
    - name: slow-requests
      type: latency
      latency: {threshold_ms: 1000}

    # Always keep critical endpoints
    - name: critical-endpoints
      type: string_attribute
      string_attribute:
        key: http.target
        values: [/api/orders, /api/payments/process, /cart/checkout]

    # Keep high-value transactions
    - name: high-value-transactions
      type: numeric_attribute
      numeric_attribute:
        key: transaction.amount
        min_value: 1000

    # Sample 10% of everything else
    - name: probabilistic-baseline
      type: probabilistic
      probabilistic: {sampling_percentage: 10}
```

**Result**: ~30% of traces stored (100% critical + 10% baseline), 70% storage reduction

See [TRACE_SAMPLING_STRATEGY.md](TRACE_SAMPLING_STRATEGY.md) for complete details.

## Debugging with Traces

### Scenario 1: Find Slow Requests

**Problem**: Users report slow checkouts

**Steps**:
1. Grafana → Explore → Tempo
2. Search: Service = `main-service`, Duration > 2s
3. Click slowest trace
4. Identify bottleneck span

**Example Finding**:
```
Trace duration: 3.5s
Slowest span: "payment-provider: POST /charge" (3.2s)
Action: Contact payment provider support
```

### Scenario 2: Debug Failed Payment

**Problem**: Payment failed for order #12345

**Steps**:
1. Find trace_id in application logs:
   ```bash
   docker-compose logs main-service | grep "ORD12345"
   # Output: trace_id=4bf92f3577b34da6
   ```
2. Grafana → Explore → Tempo
3. Search by trace_id: `4bf92f3577b34da6`
4. Examine error span

**Example Finding**:
```
Error in span: "payment-provider"
Status: ERROR
Attributes:
  http.status_code: 500
  error.message: "Insufficient funds"
  country: "BR"
Action: Known issue - BR payment provider has high failure rate
```

### Scenario 3: Understand Service Dependencies

**Problem**: Which services does checkout call?

**Steps**:
1. Find any checkout trace
2. Examine span hierarchy
3. Note all called services

**Finding**:
```
POST /checkout calls:
  ├─ PostgreSQL (get cart)
  ├─ Redis (get session)
  ├─ Inventory Service (check stock)
  ├─ Payments Service
  │  └─ Payment Provider
  └─ CRM System (update customer)
```

### Scenario 4: Compare Fast vs Slow Traces

**Steps**:
1. Find a fast trace (< 500ms)
2. Find a slow trace (> 2s)
3. Compare span durations

**Findings**:
```
Fast trace (450ms):
  payment-provider: 120ms

Slow trace (2.8s):
  payment-provider: 2.5s ← Bottleneck

Action: Payment provider API experiencing latency
```

## Best Practices

### 1. Add Meaningful Span Names

❌ **Bad**:
```python
with tracer.start_as_current_span("function"):  # Too generic
    process_order()
```

✅ **Good**:
```python
with tracer.start_as_current_span("process_order"):  # Descriptive
    validate_order()
    charge_payment()
```

### 2. Enrich Spans with Attributes

❌ **Minimal context**:
```python
span = trace.get_current_span()
# No attributes
```

✅ **Rich context**:
```python
span = trace.get_current_span()
span.set_attribute("user.country", "US")
span.set_attribute("order.amount", 99.99)
span.set_attribute("payment.method", "credit_card")
span.set_attribute("cart.item_count", 3)
```

### 3. Record Errors Properly

❌ **Silent failure**:
```python
try:
    result = call_external_api()
except Exception:
    pass  # Trace shows success!
```

✅ **Proper error recording**:
```python
try:
    result = call_external_api()
except Exception as e:
    span = trace.get_current_span()
    span.set_status(StatusCode.ERROR, str(e))
    span.record_exception(e)
    raise
```

### 4. Don't Over-Instrument

❌ **Too granular**:
```python
with tracer.start_as_current_span("validate_email"):
    if "@" in email: ...
with tracer.start_as_current_span("validate_phone"):
    if len(phone) == 10: ...
```

✅ **Right granularity**:
```python
with tracer.start_as_current_span("validate_user_input"):
    validate_email(email)
    validate_phone(phone)
```

### 5. Link Traces to Logs

Always include trace_id in logs:

```python
import logging
from opentelemetry import trace

span = trace.get_current_span()
ctx = span.get_span_context()

logger.info("Order processed", extra={
    "trace_id": format(ctx.trace_id, '032x'),
    "span_id": format(ctx.span_id, '016x'),
    "order_id": order.id
})
```

See [Logging and Correlation](06_LOGGING_AND_CORRELATION.md) for details.

### 6. Use Service Graphs

Tempo can generate service dependency graphs:

Grafana → Tempo → Service Graph

Shows:
- Which services call which
- Request rates between services
- Error rates between services

### 7. Set Up Alerts on Trace Metrics

Alert on trace-derived metrics:

```promql
# Alert if error traces spike
rate(traces_spanmetrics_calls_total{status_code="STATUS_CODE_ERROR"}[5m]) > 0.1

# Alert if P99 latency high
histogram_quantile(0.99, rate(traces_spanmetrics_latency_bucket[5m])) > 2
```

## Hands-On Exercises

### Exercise 1: Find Your First Trace

1. Generate a checkout:
   ```bash
   curl -X POST http://localhost:8000/checkout \
     -H "Authorization: Bearer user-token-123" \
     -H "Content-Type: application/json" \
     -d '{"payment_method": "credit_card", "country": "US"}'
   ```
2. Grafana → Explore → Tempo → Search
3. Service: `main-service`, last 5 minutes
4. Click the trace to explore

### Exercise 2: Identify a Slow Operation

1. Generate traffic: `make traffic`
2. Find traces with duration > 1s
3. Identify the slowest span
4. Note which service/operation is slow

### Exercise 3: Debug a Failed Payment

1. Generate traffic from Brazil: `country=BR` (15% failure rate)
2. Search for error traces: `status = error`
3. Find the error message in span attributes
4. Trace back to the root cause

### Exercise 4: Trace to Logs

1. Find any trace
2. Note the trace_id
3. Go to Loki explore
4. Query: `{service_name="main-service"} | json | trace_id="<YOUR_TRACE_ID>"`
5. See all logs for that trace

---

**Next**: Learn about logging and correlation → [Logging and Correlation](06_LOGGING_AND_CORRELATION.md)
