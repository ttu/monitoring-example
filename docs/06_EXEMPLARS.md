# Exemplars: Linking Metrics to Traces

**Reading time**: 8 minutes

This guide explains how exemplars link metric data points to the traces that generated them, enabling powerful correlation between metrics and traces.

## Table of Contents

- [What Are Exemplars?](#what-are-exemplars)
- [Why Use Exemplars?](#why-use-exemplars)
- [How Exemplars Work](#how-exemplars-work)
- [Implementation in WebStore](#implementation-in-webstore)
- [Using Exemplars in Grafana](#using-exemplars-in-grafana)
- [Configuration](#configuration)

## What Are Exemplars?

**Exemplars** are example data points attached to aggregated metric data that link back to the original traces that contributed to those metrics.

### Problem Exemplars Solve

When you see a metric spike (e.g., payment latency increased from 100ms to 5s), you need to answer:
- Which specific requests caused this spike?
- What were the trace IDs?
- How can I investigate the root cause?

Without exemplars, you must:
1. Note the time of the spike
2. Manually search traces in that time window
3. Hope to find the relevant traces

With exemplars:
1. Click on the metric spike in Grafana
2. Instantly jump to example traces that contributed to that data point
3. Investigate the root cause immediately

## Why Use Exemplars?

### Traditional Monitoring (Without Exemplars)

```
┌──────────────────────────────────────────┐
│         Metrics Dashboard                │
│                                          │
│  Payment Duration (P95)                  │
│  ┌────────────────────────────────┐     │
│  │         ╱\                      │     │
│  │        ╱  \                     │     │
│  │   ____╱    \____                │     │
│  │                                 │     │
│  └────────────────────────────────┘     │
│                                          │
│  "Hmm, spike at 14:23. Let me search    │
│   traces for that time window..."       │
└──────────────────────────────────────────┘
         │
         │ Manual process
         │ 1. Note time: 14:23
         │ 2. Open Tempo
         │ 3. Search: service.name="main-service" AND timestamp > 14:23
         │ 4. Filter by duration > 5s
         │ 5. Browse results hoping to find the issue
         ▼
┌──────────────────────────────────────────┐
│         Trace Search                     │
│                                          │
│  Found 234 traces between 14:20-14:25   │
│  Showing 50 per page...                  │
│                                          │
│  Which ones caused the spike? 🤷        │
└──────────────────────────────────────────┘
```

### Modern Monitoring (With Exemplars)

```
┌──────────────────────────────────────────┐
│         Metrics Dashboard                │
│                                          │
│  Payment Duration (P95)                  │
│  ┌────────────────────────────────────┐ │
│  │         ╱\ ← Click spike           │ │
│  │        ╱  \                        │ │
│  │   ____╱    \____                   │ │
│  │       ⬤ Exemplar trace IDs        │ │
│  └────────────────────────────────────┘ │
│                                          │
│  "Click the spike to see example traces" │
└──────────────────────────────────────────┘
         │
         │ One click
         │ Exemplar: trace_id=4bf92f35...
         ▼
┌──────────────────────────────────────────┐
│         Tempo Trace View                 │
│                                          │
│  POST /checkout [6.2s]                   │
│    ├─ db.query.get_product [5.8s] ← SLOW│
│    ├─ payment_service [200ms]            │
│    └─ inventory_service [100ms]          │
│                                          │
│  Root cause: Slow database query!        │
└──────────────────────────────────────────┘
```

## How Exemplars Work

### Architecture Flow

```
┌────────────────────────────────────────────────────────────┐
│                      Application Code                      │
└────────────────────────────────────────────────────────────┘
                               │
                               │ Records metric within trace context
                               │
                               ▼
┌────────────────────────────────────────────────────────────┐
│  OpenTelemetry SDK (Python 1.28.0+)                        │
│                                                            │
│  Current Span Context:                                     │
│    trace_id: 4bf92f3577b34da6a3ce929d0e0e4736             │
│    span_id:  00f067aa0ba902b7                              │
│                                                            │
│  Metric Recording:                                         │
│    payment_duration_histogram.record(                      │
│      value=5.8,  # seconds                                 │
│      attributes={"country": "US", "payment_method": "card"}│
│    )                                                       │
│                                                            │
│  SDK automatically attaches:                               │
│    exemplar = {                                            │
│      trace_id: "4bf92f3577b34da6a3ce929d0e0e4736"         │
│      span_id: "00f067aa0ba902b7"                           │
│      timestamp: "2024-10-21T14:23:45Z"                    │
│      value: 5.8                                            │
│      filtered_attributes: {"country": "US"}                │
│    }                                                       │
└────────────────────────────────────────────────────────────┘
                               │
                               │ OTLP/gRPC
                               ▼
┌────────────────────────────────────────────────────────────┐
│            OpenTelemetry Collector                         │
│                                                            │
│  Receives metric with exemplar:                            │
│    - Histogram data point: value=5.8, bucket=[5-10s]       │
│    - Exemplar: trace_id=4bf92f35..., span_id=00f067aa...  │
│                                                            │
│  Forwards to:                                              │
│    - Prometheus (metrics + exemplars)                      │
│    - Tempo (traces)                                        │
└────────────────────────────────────────────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
                    ▼                     ▼
        ┌─────────────────┐   ┌─────────────────┐
        │   Prometheus    │   │      Tempo      │
        │                 │   │                 │
        │  Stores:        │   │  Stores:        │
        │  - Metric value │   │  - Full trace   │
        │  - Exemplar     │   │  - Span details │
        │    trace_id     │   │                 │
        └────────┬────────┘   └────────┬────────┘
                 │                     │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────┐
                 │    Grafana      │
                 │                 │
                 │  1. Show metric │
                 │  2. Click spike │
                 │  3. Query Tempo │
                 │     with trace_id│
                 │  4. Display trace│
                 └─────────────────┘
```

### Exemplar Data Structure

When a histogram records a value, an exemplar looks like:

```json
{
  "exemplar": {
    "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
    "span_id": "00f067aa0ba902b7",
    "timestamp": "2024-10-21T14:23:45.123456Z",
    "value": 5.8,
    "filtered_attributes": {
      "country": "US",
      "payment_method": "card"
    }
  },
  "bucket": {
    "upper_bound": 10.0,
    "count": 1
  }
}
```

## Implementation in WebStore

### Automatic Exemplar Collection

As of OpenTelemetry Python SDK **1.28.0+**, exemplars are **automatically enabled** for histogram metrics when using the OTLP exporter.

**No configuration required!**

### Metrics with Exemplars

The following histogram metrics automatically include exemplars:

#### 1. Checkout Amount Histogram

```python
# File: services/main-service/monitoring.py
checkout_amount_histogram = meter.create_histogram(
    "webstore.checkout.amount",
    description="Checkout amount in USD",
    unit="USD"
)
# Exemplars: Automatically links high/low checkout amounts to their traces
```

**Use Case**: When you see unusually high or low transaction amounts, click the data point to see the exact checkout trace.

**Example Scenario**:
- Metric shows: $15,000 checkout at 14:23
- Click exemplar → Jump to trace
- Trace reveals: Customer purchased 500x of product due to UI bug

#### 2. Payment Duration Histogram

```python
# File: services/main-service/monitoring.py
payment_duration_histogram = meter.create_histogram(
    "webstore.payment.duration",
    description="Payment processing duration",
    unit="s"
)
# Exemplars: Automatically links slow payment requests to their traces
```

**Use Case**: When payment latency spikes, instantly investigate example slow requests.

**Example Scenario**:
- Metric shows: P95 latency jumped to 8s at 14:23
- Click exemplar → Jump to trace
- Trace reveals: Payment provider experiencing timeouts

### Recording Metrics with Trace Context

Exemplars are automatically attached when metrics are recorded within an active span:

```python
# File: services/main-service/services/order_service.py
async def process_checkout(...):
    # This function runs within a FastAPI span automatically created
    # by OpenTelemetry instrumentation

    payment_start = time.time()

    # Process payment
    payment_data = await self.external_service.process_payment(...)

    # Record metric - exemplar automatically attached from current span
    payment_duration_histogram.record(
        time.time() - payment_start,
        {
            "country": country,
            "payment_method": payment_method
        }
    )
    # SDK automatically adds:
    # - trace_id from current span
    # - span_id from current span
    # - timestamp

    # Record checkout amount - exemplar automatically attached
    checkout_amount_histogram.record(
        total_amount,
        {
            "country": country,
            "payment_method": payment_method
        }
    )
```

**Key Point**: Exemplars are only attached when metrics are recorded within an active trace context. If no span is active, the metric is recorded without an exemplar.

## Using Exemplars in Grafana

### Viewing Exemplars in Dashboards

1. **Open any dashboard with histogram metrics**:
   - [HTTP Metrics Dashboard](http://localhost:3000/d/http-metrics)
   - [Service Health Dashboard](http://localhost:3000/d/service-health)

2. **Enable exemplar display**:
   - Edit panel → Query options
   - Enable "Exemplars" toggle
   - Exemplars appear as dots on the graph

3. **Click an exemplar**:
   - Click any dot on the metric graph
   - Grafana queries Tempo with the trace_id
   - Full trace opens in split view

### Example: Investigating Slow Payments

**Scenario**: Payment latency P95 spiked to 8 seconds.

**Steps**:
1. Open Service Health dashboard
2. Locate "Payment Duration P95" panel
3. See spike at 14:23
4. Click exemplar dot on the spike
5. Trace opens showing:
   ```
   POST /checkout [8.2s]
     ├─ validate_cart [50ms]
     ├─ check_inventory [100ms]
     ├─ process_payment [7.8s] ← SLOW!
     │   └─ payment_provider_api [7.6s] ← External service timeout
     └─ create_order [150ms]
   ```
6. Root cause identified: Payment provider experiencing timeouts

### Configuring Exemplar Sampling

By default, OpenTelemetry Python SDK samples exemplars for each histogram bucket using `AlignedHistogramBucketExemplarReservoir`. This means:

- Each histogram bucket stores the **last exemplar** that fell into that bucket
- No configuration needed for basic use case
- For advanced sampling, you can customize the `ExemplarReservoir`

**Custom Exemplar Reservoir** (advanced):

```python
from opentelemetry.sdk.metrics.view import View
from opentelemetry.sdk.metrics._internal.exemplar import (
    AlignedHistogramBucketExemplarReservoir,
    SimpleFixedSizeExemplarReservoir
)

# Custom view with exemplar reservoir
custom_view = View(
    instrument_name="webstore.payment.duration",
    exemplar_reservoir_factory=lambda aggregation, config:
        AlignedHistogramBucketExemplarReservoir(config)
)
```

## Configuration

### Requirements

**Minimum Versions**:
- OpenTelemetry Python SDK: `>= 1.28.0`
- OpenTelemetry API: `>= 1.28.0`
- OpenTelemetry Instrumentation: `>= 0.49b0`

**WebStore Configuration**:
- ✅ SDK version: 1.29.0 (exemplar support enabled)
- ✅ OTLP exporter: Configured
- ✅ Histogram metrics: Defined
- ✅ Trace context: Automatic via FastAPI instrumentation

### Verification

To verify exemplars are being collected:

```bash
# 1. Generate traffic
./scripts/generate-traffic.sh

# 2. Query Prometheus for exemplars
curl -s 'http://localhost:9090/api/v1/query?query=webstore_payment_duration_bucket' \
  | jq '.data.result[0].exemplars'

# Expected output:
[
  {
    "labels": {
      "traceID": "4bf92f3577b34da6a3ce929d0e0e4736"
    },
    "value": "5.8",
    "timestamp": 1634826225.123
  }
]
```

### Troubleshooting

**Exemplars not appearing in Grafana?**

1. **Check SDK version**:
   ```bash
   pip list | grep opentelemetry-sdk
   # Must be >= 1.28.0
   ```

2. **Verify trace context exists**:
   - Exemplars are only added when metrics are recorded within an active span
   - Check that FastAPI instrumentation is working (traces appear in Tempo)

3. **Enable exemplars in Grafana panel**:
   - Edit panel → Query options → Enable "Exemplars"

4. **Check Tempo data source**:
   - Grafana needs a configured Tempo data source to query traces
   - Settings → Data Sources → Tempo

5. **Verify OTLP exporter**:
   - Exemplars require OTLP exporter (not Prometheus direct exporter)
   - Check `monitoring.py` uses `OTLPMetricExporter`

## Best Practices

### 1. Use Exemplars for High-Cardinality Investigation

Exemplars excel when investigating outliers:
- ✅ Why did this specific payment take 10s?
- ✅ Which checkout had a $50,000 amount?
- ✅ What trace caused 100% CPU spike?

### 2. Combine with Alerts

In alert runbooks, include exemplar investigation:

```yaml
# prometheus-alerts.yml
- alert: HighPaymentLatency
  expr: |
    histogram_quantile(0.95,
      rate(webstore_payment_duration_bucket[5m])
    ) > 5
  annotations:
    runbook: |
      1. Open Service Health dashboard
      2. Click exemplar on payment duration spike
      3. Investigate trace in Tempo
      4. Check payment provider status
```

### 3. Limit Exemplar Retention

Prometheus stores exemplars in memory:
- Default: Last exemplar per bucket
- High-volume: Consider reducing retention
- Production: Monitor Prometheus memory usage

### 4. Don't Rely on Exemplars for All Traces

Exemplars are **examples**, not **all traces**:
- ❌ Don't use exemplars to find all slow requests
- ✅ Use exemplars to investigate **why** requests are slow
- ✅ Use Tempo search for comprehensive trace analysis

## Real-World Example

**Alert fired**: Payment latency P95 exceeded 5s

**Traditional approach** (5-10 minutes):
1. Open Grafana, see spike at 14:23
2. Open Tempo, search traces between 14:20-14:25
3. Filter by service.name="payments-service"
4. Sort by duration > 5s
5. Manually review 50+ traces
6. Identify pattern: payment-provider timeouts

**With exemplars** (30 seconds):
1. Open Grafana, see spike at 14:23
2. Click exemplar dot
3. Trace opens: payment-provider timeout
4. Root cause identified immediately

**Time saved**: 90%

## Key Takeaways

1. **Exemplars link metrics to traces** - Click a metric spike, jump to example traces
2. **Automatic in Python SDK 1.28.0+** - No configuration required
3. **Works with histograms** - Checkout amount, payment duration, etc.
4. **Requires trace context** - Only works when metrics recorded within spans
5. **Powerful for investigation** - Instantly identify root causes of metric anomalies

---

**Next**: Learn about distributed tracing patterns → [Distributed Tracing](05_DISTRIBUTED_TRACING.md)
