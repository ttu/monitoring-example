# OpenTelemetry Instrumentation

**Reading time**: 25 minutes

Learn how OpenTelemetry instruments services in multiple languages and sends telemetry via OTLP to the collector.

## Table of Contents

- [What is OpenTelemetry?](#what-is-opentelemetry)
- [Instrumentation Approaches](#instrumentation-approaches)
- [Language-Specific Implementation](#language-specific-implementation)
- [OTLP Configuration](#otlp-configuration)
- [Custom Spans](#custom-spans)
- [Custom Metrics](#custom-metrics)
- [Best Practices](#best-practices)

## What is OpenTelemetry?

**OpenTelemetry** (OTel) is an open-source observability framework that provides:
- **Vendor-neutral** APIs and SDKs for instrumentation
- **Automatic instrumentation** for popular frameworks
- **Unified collection** of metrics, traces, and logs
- **OTLP** (OpenTelemetry Protocol) for data transmission

### Three Pillars of Observability

```
┌─────────────────────────────────────────────────────────┐
│                     Application                         │
└──────────┬──────────────┬──────────────┬───────────────┘
           │              │              │
      ┌────▼────┐    ┌────▼────┐   ┌────▼────┐
      │ Metrics │    │ Traces  │   │  Logs   │
      └────┬────┘    └────┬────┘   └────┬────┘
           │              │              │
           └──────────────┼──────────────┘
                          │
                     ┌────▼────┐
                     │  OTLP   │
                     └────┬────┘
                          │
                ┌─────────▼──────────┐
                │  OTEL Collector    │
                └─────────┬──────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
   ┌────▼────┐       ┌────▼────┐      ┌────▼────┐
   │Prometheus│       │  Tempo  │      │  Loki   │
   └─────────┘       └─────────┘      └─────────┘
```

## Instrumentation Approaches

### Auto-Instrumentation

**What it does**: Automatically instruments frameworks, libraries, and network calls without code changes.

**Advantages**:
- ✅ Zero code changes required
- ✅ Captures standard HTTP, database, cache operations
- ✅ Consistent instrumentation across services
- ✅ Easy to update (just update library versions)

**Limitations**:
- ❌ No business-specific metrics
- ❌ Cannot capture custom application logic
- ❌ Generic span names

### Manual Instrumentation

**What it does**: Explicitly add instrumentation code for custom metrics and spans.

**Advantages**:
- ✅ Business-specific metrics (cart additions, checkouts)
- ✅ Custom span names and attributes
- ✅ Fine-grained control over what's captured
- ✅ Domain-specific context

**Limitations**:
- ❌ Requires code changes
- ❌ More maintenance burden
- ❌ Risk of inconsistent instrumentation

### This Project's Approach: Hybrid

We use **auto-instrumentation** for standard operations plus **manual instrumentation** for business metrics:

```python
# Auto-instrumentation: HTTP requests, DB queries, Redis ops (automatic)
# Manual instrumentation: Business metrics (explicit)

from opentelemetry import metrics

meter = metrics.get_meter(__name__)
cart_additions = meter.create_counter("webstore.cart.additions")

@app.post("/cart/add")
async def add_to_cart(item: CartItem):
    # Auto-instrumented: HTTP span created automatically
    # Manual metric: Track business event
    cart_additions.add(1, {"country": item.country, "product_id": str(item.product_id)})
    # Auto-instrumented: DB query span created automatically
    result = await db.execute(...)
    return result
```

## Language-Specific Implementation

### Python (Main Service)

**Framework**: FastAPI
**Instrumentation Library**: `opentelemetry-instrumentation-fastapi`

**Setup** ([services/main-service/main.py](../services/main-service/main.py)):

```python
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Configure tracing
trace.set_tracer_provider(TracerProvider())
otlp_trace_exporter = OTLPSpanExporter(
    endpoint="http://otel-collector:4317",
    insecure=True
)

# Configure metrics
meter_provider = MeterProvider(
    metric_readers=[PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint="http://otel-collector:4317", insecure=True)
    )]
)
metrics.set_meter_provider(meter_provider)

# Auto-instrument FastAPI
FastAPIInstrumentor.instrument_app(app)
```

**Auto-instrumented components**:
- HTTP requests (FastAPI routes)
- Database queries (SQLAlchemy)
- Redis operations
- HTTP client calls (httpx)

**Custom metrics**:
```python
meter = metrics.get_meter(__name__)

# Counters
cart_additions = meter.create_counter(
    "webstore.cart.additions",
    description="Number of items added to cart"
)

checkouts = meter.create_counter(
    "webstore.checkouts",
    description="Number of checkouts completed"
)

# Histograms
checkout_amount = meter.create_histogram(
    "webstore.checkout.amount",
    description="Checkout amount in USD"
)

# Usage
cart_additions.add(1, {"country": "US", "product_id": "123"})
checkout_amount.record(99.99, {"country": "US", "payment_method": "credit_card"})
```

### Go (Payments Service)

**Framework**: Gin
**Instrumentation Library**: `go.opentelemetry.io/contrib/instrumentation/github.com/gin-gonic/gin/otelgin`

**Setup** ([services/payments-service/main.go](../services/payments-service/main.go)):

```go
import (
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
    "go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc"
    "go.opentelemetry.io/contrib/instrumentation/github.com/gin-gonic/gin/otelgin"
)

// Initialize OTLP trace exporter
traceExporter, _ := otlptracegrpc.New(
    context.Background(),
    otlptracegrpc.WithEndpoint("otel-collector:4317"),
    otlptracegrpc.WithInsecure(),
)

// Initialize OTLP metric exporter
metricExporter, _ := otlpmetricgrpc.New(
    context.Background(),
    otlpmetricgrpc.WithEndpoint("otel-collector:4317"),
    otlpmetricgrpc.WithInsecure(),
)

// Auto-instrument Gin
router := gin.Default()
router.Use(otelgin.Middleware("payments-service"))
```

**Custom metrics**:
```go
import "go.opentelemetry.io/otel/metric"

meter := otel.Meter("payments-service")

// Create counter
paymentsProcessed, _ := meter.Int64Counter(
    "payments_processed_total",
    metric.WithDescription("Total payments processed"),
)

// Record metric
paymentsProcessed.Add(ctx, 1,
    metric.WithAttributes(
        attribute.String("country", "US"),
        attribute.String("status", "success"),
        attribute.String("method", "credit_card"),
    ),
)
```

### C# (.NET) (Promotions Service)

**Framework**: ASP.NET Core
**Instrumentation Library**: `OpenTelemetry.Instrumentation.AspNetCore`

**Setup** ([services/promotions-service/Program.cs](../services/promotions-service/Program.cs)):

```csharp
using OpenTelemetry.Trace;
using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddOpenTelemetry()
    .WithTracing(tracing => tracing
        .SetResourceBuilder(ResourceBuilder.CreateDefault()
            .AddService("promotions-service"))
        .AddAspNetCoreInstrumentation()
        .AddHttpClientInstrumentation()
        .AddOtlpExporter(options =>
        {
            options.Endpoint = new Uri("http://otel-collector:4317");
            options.Protocol = OtlpExportProtocol.Grpc;
        }))
    .WithMetrics(metrics => metrics
        .SetResourceBuilder(ResourceBuilder.CreateDefault()
            .AddService("promotions-service"))
        .AddAspNetCoreInstrumentation()
        .AddHttpClientInstrumentation()
        .AddOtlpExporter(options =>
        {
            options.Endpoint = new Uri("http://otel-collector:4317");
            options.Protocol = OtlpExportProtocol.Grpc;
        }));
```

**Auto-instrumented components**:
- HTTP requests (ASP.NET Core controllers)
- HTTP client calls
- Built-in ASP.NET Core metrics

**Logging with Serilog**:
```csharp
using Serilog;

Log.Logger = new LoggerConfiguration()
    .Enrich.WithProperty("service", "promotions-service")
    .WriteTo.Console(new CompactJsonFormatter())
    .CreateLogger();
```

### Node.js (External Services)

**Framework**: Express
**Instrumentation Library**: `@opentelemetry/auto-instrumentations-node`

**Setup** ([services/external/payment-provider/index.js](../services/external/payment-provider/index.js)):

```javascript
const { NodeSDK } = require('@opentelemetry/sdk-node');
const { OTLPTraceExporter } = require('@opentelemetry/exporter-trace-otlp-grpc');
const { OTLPMetricExporter } = require('@opentelemetry/exporter-metrics-otlp-grpc');
const { getNodeAutoInstrumentations } = require('@opentelemetry/auto-instrumentations-node');

const sdk = new NodeSDK({
  serviceName: 'payment-provider',
  traceExporter: new OTLPTraceExporter({
    url: 'http://otel-collector:4317',
  }),
  metricReader: new PeriodicExportingMetricReader({
    exporter: new OTLPMetricExporter({
      url: 'http://otel-collector:4317',
    }),
  }),
  instrumentations: [getNodeAutoInstrumentations()],
});

sdk.start();
```

**Note**: External services (payment-provider, crm-system, inventory-system) in this project **intentionally do NOT** have OpenTelemetry instrumentation. They simulate third-party SaaS APIs that you don't control.

### React (Frontend)

**Framework**: React
**Instrumentation Library**: Grafana Faro

**Setup** ([frontend/src/monitoring.js](../frontend/src/monitoring.js)):

```javascript
import { initializeFaro } from '@grafana/faro-web-sdk';

export const faro = initializeFaro({
  url: 'http://localhost:3000/collect',  // Grafana endpoint
  app: {
    name: 'webstore-frontend',
    version: '1.0.0',
  },
  instrumentations: [
    // Page load instrumentation
    new FaroWebInstrumentationsPageLoad(),
    // Error tracking
    new FaroWebInstrumentationsErrors(),
    // User interactions
    new FaroWebInstrumentationsClick(),
  ],
});

// Custom events
faro.api.pushEvent('checkout_completed', {
  orderId: 'ORD123',
  amount: 99.99,
  country: 'US',
});
```

## OTLP Configuration

All services push telemetry to the **OpenTelemetry Collector** via OTLP.

### OTLP Endpoints

```
OTLP/gRPC:  otel-collector:4317  (preferred, more efficient)
OTLP/HTTP:  otel-collector:4318  (fallback)
```

### Common Configuration Pattern

Every service follows this pattern:

```yaml
Service Configuration:
  ├── Resource attributes (service.name, service.version)
  ├── Trace provider
  │   └── OTLP Exporter (gRPC → otel-collector:4317)
  ├── Metric provider
  │   └── OTLP Exporter (gRPC → otel-collector:4317)
  └── Auto-instrumentation
      └── Framework-specific (FastAPI, Gin, ASP.NET Core, Express)
```

### Environment Variables

Services can be configured via environment variables:

```bash
# OTLP Endpoint
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317

# Service name
OTEL_SERVICE_NAME=main-service

# Trace sampling (always on for demo)
OTEL_TRACES_SAMPLER=always_on

# Resource attributes
OTEL_RESOURCE_ATTRIBUTES=service.name=main-service,service.version=1.0.0
```

## Custom Spans

### Auto-Instrumentation vs Custom Spans

OpenTelemetry provides **automatic instrumentation** for common operations:

**✅ Already Auto-Instrumented in This Project**:

**Python**:
```python
# services/main-service/main.py
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

# Automatic HTTP request tracing
FastAPIInstrumentor.instrument_app(app)

# Automatic SQL query tracing - captures every SQL statement
SQLAlchemyInstrumentor().instrument(engine=engine)

# Automatic Redis command tracing
RedisInstrumentor().instrument()

# Automatic HTTP client tracing
HTTPXClientInstrumentor().instrument()
```

**What auto-instrumentation provides**:
- ✅ Span for every SQL query with `db.statement`, `db.system`, `db.name`
- ✅ Span for every Redis command with `db.redis.command`
- ✅ Span for every HTTP request/response with `http.method`, `http.status_code`
- ✅ Span for every outgoing HTTP call with full propagation

**Go**:
```go
// services/payments-service/main.go
import (
    "go.opentelemetry.io/contrib/instrumentation/github.com/gin-gonic/gin/otelgin"
    "go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
)

// Automatic HTTP request tracing
router.Use(otelgin.Middleware("payments-service"))

// Automatic HTTP client tracing
client := &http.Client{
    Transport: otelhttp.NewTransport(http.DefaultTransport),
}
```

**C#**:
```csharp
// services/promotions-service/Program.cs
builder.Services.AddOpenTelemetry()
    .WithTracing(tracerProviderBuilder =>
        tracerProviderBuilder
            .AddAspNetCoreInstrumentation()  // Auto HTTP tracing
            .AddHttpClientInstrumentation()   // Auto HTTP client tracing
    );
```

### Why Add Custom Spans?

Custom spans **complement** auto-instrumentation by adding **business context**:

| Auto-Instrumented Span | Custom Span |
|------------------------|-------------|
| `SELECT * FROM products WHERE id = ?` | `db.query.get_product` with `product.id=123` |
| `redis.GET` | `cache.get` with `cache.key=session:user123` and `cache.hit=true` |
| Generic operation | Business operation like `process_payment`, `calculate_discount` |

**Custom spans are useful for**:
- 🎯 Adding business-specific attributes (`user.id`, `order.id`, `product.id`)
- 🎯 Grouping related operations (`db.transaction.create_order`)
- 🎯 Performance tracking of specific business logic
- 🎯 Making traces easier to understand in Grafana Tempo

### Database Query Spans

**Note**: SQLAlchemy auto-instrumentation already traces all SQL queries. Custom spans add business context on top.

**Python (Manual Span Creation)**:
```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

async def get_user_cart(user_id: str, db: Session):
    # Create custom span for database query
    with tracer.start_as_current_span("db.query.get_cart") as span:
        # Add attributes for debugging
        span.set_attribute("db.operation", "SELECT")
        span.set_attribute("db.table", "cart")
        span.set_attribute("user.id", user_id)

        # Execute query
        result = db.query(Cart).filter(Cart.user_id == user_id).first()

        # Add result metadata
        if result:
            span.set_attribute("cart.item_count", len(result.items))
            span.set_attribute("db.rows_returned", 1)
        else:
            span.set_attribute("db.rows_returned", 0)

        return result
```

**Go (Manual Span Creation)**:
```go
import (
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/attribute"
)

func getPaymentRecord(ctx context.Context, paymentID string) (*Payment, error) {
    tracer := otel.Tracer("payments-service")

    // Create custom span
    ctx, span := tracer.Start(ctx, "db.query.get_payment")
    defer span.End()

    // Add attributes
    span.SetAttributes(
        attribute.String("db.operation", "SELECT"),
        attribute.String("db.table", "payments"),
        attribute.String("payment.id", paymentID),
    )

    // Execute query
    var payment Payment
    err := db.QueryRowContext(ctx,
        "SELECT * FROM payments WHERE id = $1",
        paymentID,
    ).Scan(&payment)

    if err != nil {
        span.RecordError(err)
        span.SetStatus(codes.Error, "Payment not found")
        return nil, err
    }

    span.SetAttributes(attribute.Int("db.rows_returned", 1))
    return &payment, nil
}
```

**C# (Manual Span Creation)**:
```csharp
using OpenTelemetry.Trace;

public async Task<Promotion> GetPromotionAsync(string promotionId)
{
    var tracer = TracerProvider.Default.GetTracer("promotions-service");

    using var span = tracer.StartActiveSpan("db.query.get_promotion");
    span.SetAttribute("db.operation", "SELECT");
    span.SetAttribute("db.table", "promotions");
    span.SetAttribute("promotion.id", promotionId);

    try
    {
        var promotion = await _dbContext.Promotions
            .Where(p => p.Id == promotionId)
            .FirstOrDefaultAsync();

        if (promotion != null)
        {
            span.SetAttribute("db.rows_returned", 1);
            span.SetAttribute("promotion.discount_percent", promotion.DiscountPercent);
        }
        else
        {
            span.SetAttribute("db.rows_returned", 0);
        }

        return promotion;
    }
    catch (Exception ex)
    {
        span.RecordException(ex);
        span.SetStatus(Status.Error);
        throw;
    }
}
```

### Cache Operation Spans

**Python (Redis)**:
```python
async def get_cached_user_session(user_id: str, redis: Redis):
    with tracer.start_as_current_span("cache.get") as span:
        # Add cache attributes
        span.set_attribute("cache.system", "redis")
        span.set_attribute("cache.operation", "GET")
        span.set_attribute("cache.key", f"session:{user_id}")

        # Execute Redis operation
        cached_data = await redis.get(f"session:{user_id}")

        # Record cache hit/miss
        if cached_data:
            span.set_attribute("cache.hit", True)
        else:
            span.set_attribute("cache.hit", False)

        return cached_data

async def set_cached_cart(user_id: str, cart_data: dict, redis: Redis):
    with tracer.start_as_current_span("cache.set") as span:
        span.set_attribute("cache.system", "redis")
        span.set_attribute("cache.operation", "SET")
        span.set_attribute("cache.key", f"cart:{user_id}")
        span.set_attribute("cache.ttl_seconds", 3600)

        # Set with expiration
        await redis.setex(
            f"cart:{user_id}",
            3600,  # 1 hour TTL
            json.dumps(cart_data)
        )

        span.set_attribute("cache.item_count", len(cart_data.get("items", [])))
```

**Go (Redis)**:
```go
func getCachedProduct(ctx context.Context, productID string) (*Product, error) {
    tracer := otel.Tracer("main-service")

    ctx, span := tracer.Start(ctx, "cache.get")
    defer span.End()

    span.SetAttributes(
        attribute.String("cache.system", "redis"),
        attribute.String("cache.operation", "GET"),
        attribute.String("cache.key", fmt.Sprintf("product:%s", productID)),
    )

    // Get from Redis
    val, err := redisClient.Get(ctx, fmt.Sprintf("product:%s", productID)).Result()

    if err == redis.Nil {
        // Cache miss
        span.SetAttribute("cache.hit", false)
        return nil, nil
    } else if err != nil {
        // Error
        span.RecordError(err)
        return nil, err
    }

    // Cache hit
    span.SetAttribute("cache.hit", true)

    var product Product
    json.Unmarshal([]byte(val), &product)
    return &product, nil
}
```

### Business Logic Spans

**Payment Processing**:
```python
async def process_checkout(order: Order, payment_method: str):
    with tracer.start_as_current_span("business.checkout") as span:
        span.set_attribute("order.id", order.id)
        span.set_attribute("order.amount", order.total_amount)
        span.set_attribute("order.country", order.country)
        span.set_attribute("payment.method", payment_method)

        # Validate inventory
        with tracer.start_as_current_span("business.validate_inventory"):
            inventory_available = await check_inventory(order.items)
            if not inventory_available:
                span.set_status(StatusCode.ERROR, "Insufficient inventory")
                raise InsufficientInventoryError()

        # Process payment
        with tracer.start_as_current_span("business.process_payment"):
            payment_result = await charge_payment(order, payment_method)
            span.set_attribute("payment.transaction_id", payment_result.transaction_id)

        # Update CRM
        with tracer.start_as_current_span("business.update_crm"):
            await update_customer_record(order.user_id, order)

        span.set_attribute("checkout.status", "success")
        return payment_result
```

### External API Call Spans

**Go (HTTP Client with Context)**:
```go
func callPaymentProvider(ctx context.Context, payment *Payment) (*PaymentResponse, error) {
    tracer := otel.Tracer("payments-service")

    // Create span for external call
    ctx, span := tracer.Start(ctx, "http.client.payment_provider")
    defer span.End()

    span.SetAttributes(
        attribute.String("http.method", "POST"),
        attribute.String("http.url", "http://payment-provider:3001/charge"),
        attribute.String("peer.service", "payment-provider"),
        attribute.String("payment.country", payment.Country),
        attribute.Float64("payment.amount", payment.Amount),
    )

    // Create HTTP request with context (propagates trace)
    req, _ := http.NewRequestWithContext(ctx, "POST",
        "http://payment-provider:3001/charge",
        bytes.NewBuffer(paymentJSON))

    // Execute request
    start := time.Now()
    resp, err := httpClient.Do(req)
    duration := time.Since(start)

    span.SetAttributes(
        attribute.Int("http.status_code", resp.StatusCode),
        attribute.Int64("http.response_time_ms", duration.Milliseconds()),
    )

    if err != nil || resp.StatusCode >= 500 {
        span.RecordError(err)
        span.SetStatus(codes.Error, "Payment provider error")
        return nil, err
    }

    return parsePaymentResponse(resp.Body), nil
}
```

### Span Naming Conventions

Follow **semantic conventions** for span names:

**Database Operations**:
```
✅ db.query.get_cart
✅ db.query.insert_order
✅ db.query.update_user
✅ db.transaction.checkout

❌ get_cart (too vague)
❌ database_operation (not specific)
```

**Cache Operations**:
```
✅ cache.get
✅ cache.set
✅ cache.delete
✅ cache.flush

❌ redis_get (implementation detail)
❌ get_from_cache (verbose)
```

**Business Logic**:
```
✅ business.checkout
✅ business.validate_inventory
✅ business.calculate_discount
✅ business.process_refund

❌ checkout (ambiguous - HTTP or business logic?)
❌ do_checkout (not descriptive)
```

**External Services**:
```
✅ http.client.payment_provider
✅ http.client.crm_system
✅ grpc.client.inventory_service

❌ call_api (too generic)
❌ external_call (not specific)
```

### Span Attributes Reference

**Standard Attributes** (Semantic Conventions):

**Database**:
- `db.system`: "postgresql", "redis", "mongodb"
- `db.operation`: "SELECT", "INSERT", "UPDATE", "DELETE"
- `db.table`: Table/collection name
- `db.statement`: SQL query (sanitized, no sensitive data)
- `db.rows_returned`: Number of rows
- `db.rows_affected`: Rows inserted/updated/deleted

**Cache**:
- `cache.system`: "redis", "memcached"
- `cache.operation`: "GET", "SET", "DELETE"
- `cache.key`: Cache key (without sensitive data)
- `cache.hit`: true/false
- `cache.ttl_seconds`: TTL value

**HTTP Client**:
- `http.method`: "GET", "POST", "PUT", "DELETE"
- `http.url`: Full URL
- `http.status_code`: Response status
- `http.request_content_length`: Request size in bytes
- `http.response_content_length`: Response size
- `peer.service`: Target service name

**Business Logic**:
- `order.id`: Order identifier
- `order.amount`: Order amount
- `payment.method`: Payment method
- `user.id`: User identifier
- `product.id`: Product identifier
- `checkout.status`: "success", "failed"

### Error Recording

**Proper Exception Handling**:
```python
try:
    result = await process_payment(payment_data)
except PaymentDeclinedError as e:
    span = trace.get_current_span()

    # Record exception with full context
    span.record_exception(e)

    # Set error status
    span.set_status(StatusCode.ERROR, "Payment declined")

    # Add error attributes
    span.set_attribute("error.type", "PaymentDeclinedError")
    span.set_attribute("error.message", str(e))
    span.set_attribute("payment.decline_reason", e.decline_reason)

    # Re-raise
    raise
```

**Go Error Recording**:
```go
if err != nil {
    span.RecordError(err)
    span.SetStatus(codes.Error, err.Error())
    span.SetAttributes(
        attribute.String("error.type", "DatabaseError"),
        attribute.String("error.message", err.Error()),
    )
    return nil, err
}
```

### Performance Considerations

**Avoid Over-Instrumentation**:
```python
# ❌ Too granular - creates noise
with tracer.start_as_current_span("validate_email"):
    if "@" not in email:
        raise ValidationError()

with tracer.start_as_current_span("validate_phone"):
    if len(phone) != 10:
        raise ValidationError()

# ✅ Right level of granularity
with tracer.start_as_current_span("business.validate_user_input") as span:
    span.set_attribute("validation.fields", ["email", "phone"])
    validate_email(email)
    validate_phone(phone)
```

**Use Span Events for Fine-Grained Details**:
```python
with tracer.start_as_current_span("business.checkout") as span:
    # Add events instead of child spans for quick operations
    span.add_event("Inventory validated", {
        "items_count": len(order.items),
        "validation_time_ms": 5
    })

    result = await charge_payment(order)

    span.add_event("Payment charged", {
        "transaction_id": result.txn_id,
        "amount": result.amount
    })
```

## Custom Metrics

### Metric Types

**Counter** (monotonically increasing):
```python
# Use for: Total requests, total errors, total sales
cart_additions = meter.create_counter("webstore.cart.additions")
cart_additions.add(1, {"country": "US"})
```

**Histogram** (distribution of values):
```python
# Use for: Request duration, payment amounts, response sizes
checkout_amount = meter.create_histogram("webstore.checkout.amount")
checkout_amount.record(99.99, {"country": "US"})
```

**UpDownCounter** (can increase or decrease):
```python
# Use for: Active connections, queue size, inventory
active_carts = meter.create_up_down_counter("webstore.active.carts")
active_carts.add(1, {"country": "US"})   # Cart created
active_carts.add(-1, {"country": "US"})  # Cart checked out
```

**Gauge** (current value):
```python
# Use for: CPU usage, memory, temperature
# Note: Use UpDownCounter instead in most cases
```

### Metric Naming Conventions

Follow OpenTelemetry semantic conventions:

```
✅ Good:
  - webstore.cart.additions        (namespace.object.action)
  - http.server.duration           (semantic convention)
  - db.query.duration              (semantic convention)

❌ Bad:
  - cart_adds                      (too vague)
  - CartAdditions                  (wrong casing)
  - webstore-cart-additions        (wrong separator)
```

### Labels/Attributes

**High-cardinality** (many unique values) - ❌ Avoid:
- user_id
- order_id
- timestamp

**Low-cardinality** (few unique values) - ✅ Use:
- country
- payment_method
- status (success/failure)
- product_category

**Example**:
```python
# Good: Low cardinality labels
cart_additions.add(1, {
    "country": "US",           # ~7 values
    "product_category": "electronics"  # ~10 values
})

# Bad: High cardinality labels
cart_additions.add(1, {
    "user_id": "user-12345",   # Thousands of values!
    "order_id": "ORD-98765"    # Thousands of values!
})
```

## Best Practices

### 1. Use Auto-Instrumentation First

Start with auto-instrumentation, add manual instrumentation only for business-specific needs:

```python
# ✅ Let auto-instrumentation handle HTTP/DB/Cache
FastAPIInstrumentor.instrument_app(app)
SQLAlchemyInstrumentor().instrument(engine)

# ✅ Add manual metrics for business logic
cart_additions.add(1, {"country": country})
```

### 2. Add Meaningful Span Attributes

Enrich spans with business context:

```python
from opentelemetry import trace

span = trace.get_current_span()
span.set_attribute("user.country", "US")
span.set_attribute("cart.item_count", 3)
span.set_attribute("order.total_amount", 99.99)
```

### 3. Sample Intelligently

Use **tail sampling** in the OTLP Collector (not in services):

```yaml
# otel-collector-config.yaml
processors:
  tail_sampling:
    policies:
      - name: errors-always
        type: status_code
        status_code:
          status_codes: [ERROR]
      - name: slow-requests
        type: latency
        latency:
          threshold_ms: 1000
```

See [TRACE_SAMPLING_STRATEGY.md](TRACE_SAMPLING_STRATEGY.md) for details.

### 4. Correlate Logs with Traces

Extract trace context in logs:

```python
import logging
from opentelemetry import trace

# Get current trace context
span = trace.get_current_span()
trace_id = span.get_span_context().trace_id
span_id = span.get_span_context().span_id

# Add to logs
logger.info("Processing checkout", extra={
    "trace_id": format(trace_id, '032x'),
    "span_id": format(span_id, '016x'),
    "order_id": order_id
})
```

See [LOGGING_STANDARDS.md](LOGGING_STANDARDS.md) for complete standards.

### 5. Avoid Over-Instrumentation

Don't create spans for every function:

```python
# ❌ Too much
@tracer.start_as_current_span("validate_email")
def validate_email(email):
    return "@" in email

# ✅ Right level of granularity
@tracer.start_as_current_span("process_order")
def process_order(order):
    # Meaningful business operation
    validate_email(order.email)
    charge_payment(order)
    send_confirmation(order)
```

### 6. Use Exemplars

Link metrics to traces for debugging:

```python
# Histogram automatically creates exemplars linking to traces
payment_duration.record(
    duration_ms,
    {"country": country, "status": "success"}
)
# In Prometheus/Grafana: Click exemplar → Jump to trace
```

## Inspecting Spans in Grafana Tempo

### Accessing Tempo in Grafana

1. **Open Grafana**: http://localhost:3000
2. **Navigate to Explore** (compass icon in left sidebar)
3. **Select Tempo** from the data source dropdown
4. **Choose a query method**:
   - **Search** - Find traces by service, duration, tags
   - **TraceQL** - Advanced query language
   - **Trace ID** - Look up specific trace

### Finding Traces with Custom Spans

**Search by Service**:
```
Service: main-service
Operation: POST /api/cart/add
Min Duration: 100ms
```

**Search by Span Name** (TraceQL):
```
{ name="db.query.get_product" }
{ name="cache.get" && resource.service.name="promotions-service" }
{ name="db.transaction.create_order" && span.order.total_amount > 100 }
```

### Understanding the Trace View

When you click on a trace, you'll see a **waterfall visualization**:

```
POST /api/cart/add                           [━━━━━━━━━━━━━━━━━━━━] 245ms
├─ db.query.get_product                      [━━━━━] 52ms
│  ├─ Attributes:
│  │  - db.operation: SELECT
│  │  - db.table: products
│  │  - product.id: 123
│  │  - db.rows_returned: 1
│  └─ Auto-instrumented:
│     └─ SELECT * FROM products WHERE id=?   [━━━━] 50ms
│        - db.statement: SELECT * FROM products WHERE id = ?
│        - db.system: postgresql
│
├─ db.query.insert_cart_item                 [━━] 18ms
│  ├─ Attributes:
│  │  - db.operation: INSERT
│  │  - db.table: cart_items
│  │  - user.id: user-123
│  │  - cart_item.id: 456
│  └─ Auto-instrumented:
│     └─ INSERT INTO cart_items...           [━] 16ms
│
└─ cache.incr                                [━] 8ms
   ├─ Attributes:
   │  - cache.system: redis
   │  - cache.operation: INCR
   │  - cache.key: cart:user-123
   │  - cache.ttl: 3600
   └─ Auto-instrumented:
      └─ INCR cart:user-123                  [━] 7ms
         - db.redis.command: INCR
```

**Notice**:
- ✅ **Custom span** (`db.query.get_product`) provides business context
- ✅ **Auto-instrumented span** (SQL query) nested inside shows technical details
- ✅ Both complement each other for full visibility

### Analyzing Database Performance

**Find Slow Queries**:
```
{ name="db.query.get_product" && duration > 500ms }
```

**View in Trace**:
- Click on the slow `db.query.get_product` span
- Expand to see the nested auto-instrumented SQL span
- Check attributes:
  - `db.statement` - See the actual SQL query
  - `product.id` - Identify which product caused slowness
  - `db.rows_returned` - Check if query returned unexpected data

**Example**: Finding a slow query in checkout:
```
Trace: Checkout request taking 2.5 seconds

POST /api/orders/checkout                    [━━━━━━━━━━━━━━━━━━━━━━━━━] 2543ms
├─ db.query.get_product                      [━━━━━━━━━━━━━] 1428ms  ⚠️ SLOW!
│  └─ SELECT * FROM products WHERE id=?      [━━━━━━━━━━━━] 1425ms
│     Attributes:
│     - product.id: 7
│     - db.query.slow: true
│     - db.query.duration_ms: 1425
```

**Action**: Check if product ID 7 has missing indexes or corrupted data.

### Analyzing Cache Performance

**Find Cache Misses**:
```
{ name="cache.get" && span.cache.hit=false }
```

**View in Trace**:
```
cache.get                                    [━━] 125ms
Attributes:
- cache.system: redis
- cache.operation: GET
- cache.key: session:user-456
- cache.hit: false  ⚠️ Cache miss caused slow path
```

**Compare with Cache Hit**:
```
cache.get                                    [━] 3ms
Attributes:
- cache.hit: true  ✅ Fast response
```

### Analyzing Business Transactions

**Find Failed Checkouts**:
```
{ name="db.transaction.create_order" && status=error }
```

**View Complete Transaction**:
```
POST /api/orders/checkout                    [━━━━━━━━━━━━━━] 850ms (ERROR)
├─ db.query.get_cart_items                   [━] 15ms
├─ db.query.get_product (x3)                 [━━] 45ms
├─ http.client.payment_provider              [━━━] 200ms (SUCCESS)
└─ db.transaction.create_order               [━] 12ms (ERROR)
   ├─ Attributes:
   │  - user.id: user-789
   │  - order.total_amount: 299.99
   │  - error.type: IntegrityError
   │  - error.message: duplicate key value violates unique constraint
   └─ db.query.update_product_stock          [━] 8ms
      Attributes:
      - product.id: 5
      - product.stock.before: 0  ⚠️ Out of stock!
      - product.stock.after: -2  ⚠️ Negative stock!
```

**Insight**: Payment succeeded but order creation failed due to race condition in stock check.

### Cross-Service Trace Analysis

**Find Distributed Traces**:
```
{ resource.service.name="main-service" && name="POST /api/orders/checkout" }
```

**View Full Request Path**:
```
main-service: POST /api/orders/checkout                [━━━━━━━━━━━━━━━━━━━━━] 1250ms
├─ db.query.get_cart_items                             [━] 12ms
├─ db.query.get_product                                [━] 15ms
├─ http.client → inventory-system                      [━━━] 180ms
│  └─ inventory-system: POST /api/inventory/check      [━━] 165ms
│     └─ (external service - not instrumented)
├─ http.client → promotions-service                    [━━] 95ms
│  └─ promotions-service: POST /api/promotions/check   [━━] 88ms
│     └─ cache.get (coupon lookup)                     [━] 3ms
│        Attributes:
│        - cache.hit: true
│        - coupon.code: WELCOME10
├─ http.client → payments-service                      [━━━━] 320ms
│  └─ payments-service: POST /api/payments/process     [━━━] 305ms
│     └─ http.client → payment-provider                [━━] 280ms
│        └─ (external service - not instrumented)
└─ db.transaction.create_order                         [━] 18ms
   └─ cache.delete (clear cart)                        [━] 4ms
```

**Insights from this trace**:
- ✅ Total latency: 1.25s
- ⚠️ Payment provider is slowest (280ms)
- ✅ Database operations are fast (<20ms each)
- ✅ Cache hit on promotions check (3ms)
- ✅ Trace context propagated across all 3 services

### Using Span Attributes for Debugging

**Filter by Business Attributes**:
```
# Find all checkouts for a specific country
{ name="db.transaction.create_order" && span.country="US" }

# Find high-value orders
{ name="db.transaction.create_order" && span.order.total_amount > 500 }

# Find specific user's requests
{ span.user.id="user-123" }

# Find product-specific operations
{ name="db.query.get_product" && span.product.id=7 }
```

### Comparing Auto vs Custom Spans

**Example: View Both Layers**

Auto-instrumented span (technical):
```
SELECT * FROM cart_items WHERE user_id = ?
- db.statement: SELECT * FROM cart_items WHERE user_id = ?
- db.system: postgresql
- db.name: webstore
```

Custom span (business):
```
db.query.get_cart_items
- db.operation: SELECT
- db.table: cart_items
- user.id: user-123
- db.rows_returned: 5
```

**When to use which**:
- **View custom span** - Understand business flow (what operation)
- **Expand to auto span** - Debug technical issues (actual SQL, connection pool)

### Grafana Tempo Tips

**Keyboard Shortcuts**:
- `Ctrl+F` - Search within trace
- `+`/`-` - Zoom in/out timeline
- Click span - View attributes and events
- Click "Logs for this span" - Jump to correlated logs in Loki

**Useful Views**:
- **Service Graph** - Visualize service dependencies
- **Node Graph** - See request flow between services
- **Trace to Logs** - Jump from span to related log lines (requires trace_id in logs)

### Linking Dashboards to Traces

You can add **Data Links** in Grafana dashboards to jump from metrics to traces:

**In a dashboard panel** (e.g., HTTP Metrics dashboard):
1. Edit panel → Data links → Add link
2. Title: "View Traces"
3. URL: `${__url.path}/explore?left={"datasource":"tempo","queries":[{"query":"{resource.service.name=\"main-service\"}"}]}`

**Using Exemplars** (automatic metric-to-trace links):
- Histogram metrics automatically create exemplars linking to traces
- In Prometheus/Grafana charts, click the diamond icon (◆) next to a data point
- Jumps directly to the trace that contributed to that metric

**Recommended Dashboards to Add Trace Links**:
- **HTTP Metrics Dashboard**: Link from request duration panels
- **Service Health Dashboard**: Link from error rate panels
- **SLO Tracking Dashboard**: Link from latency SLO panels

**Example**: In the HTTP Metrics dashboard, clicking on a slow request spike will show you the actual traces that were slow during that time period.

## Verification

### 1. Check OTLP Export

```bash
# View service logs for OTLP export
docker-compose logs main-service | grep -i "otlp\|exporter"

# Expected output:
# "OTLP exporter initialized"
# "Exporting traces to otel-collector:4317"
```

### 2. Check OTLP Collector Reception

```bash
# View collector logs
docker-compose logs otel-collector | grep -i "receiver"

# Expected output:
# "OTLP receiver started on :4317"
# "Traces received: 10"
```

### 3. Verify Metrics in Prometheus

```bash
# Check if metrics are flowing
curl -s http://localhost:8889/metrics | grep webstore_cart_additions

# Query Prometheus
curl -s 'http://localhost:9090/api/v1/query?query=webstore_cart_additions_total' | jq
```

### 4. Verify Traces in Tempo

Open Grafana → Explore → Tempo → Search → Run query

You should see traces from all instrumented services.

## Troubleshooting

### No Metrics Appearing

**Check**:
1. OTLP Collector is running: `docker-compose ps otel-collector`
2. Service can reach collector: `docker-compose exec main-service ping otel-collector`
3. Metrics are being exported: Check service logs
4. Prometheus is scraping: http://localhost:9090/targets

### No Traces Appearing

**Check**:
1. Trace exporter configured: Check service logs for "trace exporter"
2. OTLP Collector receiving: `docker-compose logs otel-collector | grep -i trace`
3. Tempo is running: `curl http://localhost:3200/ready`

### High Memory Usage

**Cause**: Too many unique label combinations (high cardinality)

**Solution**: Review metrics and remove high-cardinality labels (user_id, order_id, timestamps)

---

**Next**: Learn about metrics collection and dashboards → [Metrics and Dashboards](04_METRICS_AND_DASHBOARDS.md)
