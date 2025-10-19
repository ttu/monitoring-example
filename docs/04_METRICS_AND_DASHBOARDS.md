# Metrics and Dashboards

**Reading time**: 20 minutes

Learn how to collect, query, and visualize metrics using Prometheus and Grafana.

## Table of Contents

- [Understanding Metrics](#understanding-metrics)
- [Business vs Infrastructure Metrics](#business-vs-infrastructure-metrics)
- [Prometheus Basics](#prometheus-basics)
- [PromQL Queries](#promql-queries)
- [Grafana Dashboards](#grafana-dashboards)
- [Creating Custom Dashboards](#creating-custom-dashboards)
- [Best Practices](#best-practices)

## Understanding Metrics

**Metrics** are numerical measurements taken over time that help you understand system behavior and performance.

### Metric Types

**Counter** - Monotonically increasing value:
```
Total HTTP requests:     1000 → 1005 → 1010
Total cart additions:    500 → 502 → 505
Total errors:           10 → 12 → 15
```

**Gauge** - Value that can go up or down:
```
Active connections:     50 → 48 → 52
Memory usage (MB):      2048 → 2100 → 2050
Queue length:          10 → 15 → 8
```

**Histogram** - Distribution of values:
```
Request duration buckets:
  ≤100ms: 850 requests
  ≤500ms: 950 requests
  ≤1s:    980 requests
  ≤5s:    1000 requests
```

**Summary** - Similar to histogram, with percentiles calculated client-side:
```
Request duration:
  P50: 120ms
  P90: 450ms
  P99: 980ms
```

## Business vs Infrastructure Metrics

### Business Metrics (Domain-Specific)

These track business outcomes and user behavior:

**WebStore Business Metrics**:
```promql
# Cart additions by country
webstore_cart_additions_total{country="US", product_id="1"}

# Checkout success/failure
webstore_checkouts_total{country="US", status="success"}

# Checkout amounts (histogram)
webstore_checkout_amount_bucket{country="US", payment_method="credit_card"}

# Active shopping carts
webstore_active_carts{country="US"}

# Payment processing
payments_processed_total{country="US", status="success", method="credit_card"}

# Payment amounts
payment_amount_usd_bucket{country="BR", le="100"}

# Funnel analysis (user journey tracking)
webstore_funnel_stage_total{stage="browse_catalog", country="US"}
webstore_funnel_stage_total{stage="view_product", country="US"}
webstore_funnel_stage_total{stage="add_to_cart", country="US"}
webstore_funnel_stage_total{stage="checkout_complete", country="US"}

# Customer segmentation (behavioral tracking)
webstore_customer_segment_total{segment="vip", action="checkout", country="US"}
webstore_customer_segment_total{segment="new", action="browse_catalog", country="US"}
webstore_customer_segment_total{segment="at_risk", action="view_product", country="US"}
```

**Why they matter**:
- Track conversion rates and funnel drop-offs
- Identify geographic trends
- Monitor payment success rates
- Measure revenue
- Analyze customer behavior by segment
- Optimize user journey for maximum conversion

### Infrastructure Metrics (Technical)

These track system health and performance:

**HTTP Metrics** (auto-instrumented):
```promql
# Request rate
http_server_requests_seconds_count{service="main-service"}

# Request duration
http_server_requests_seconds_sum / http_server_requests_seconds_count

# Error rate
rate(http_server_requests_seconds_count{status=~"5.."}[5m])
```

**Database Metrics**:
```promql
# Connection pool usage
db_pool_connections_active / db_pool_connections_max

# Query duration
rate(db_query_duration_seconds_sum[5m]) / rate(db_query_duration_seconds_count[5m])
```

**Container Metrics** (from cAdvisor):
```promql
# CPU usage
rate(container_cpu_usage_seconds_total[5m])

# Memory usage
container_memory_usage_bytes
```

## Prometheus Basics

### Architecture

```
┌─────────────────┐
│   Services      │
│  (OTLP push)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ OTLP Collector  │
│  (Prometheus    │
│   exporter)     │
│   Port: 8889    │
└────────┬────────┘
         │
         │ HTTP scrape
         │ every 15s
         ▼
┌─────────────────┐
│   Prometheus    │
│  Time Series DB │
│   Port: 9090    │
└─────────────────┘
```

### Scrape Configuration

[prometheus.yml](../prometheus.yml):
```yaml
scrape_configs:
  - job_name: 'otel-collector'
    scrape_interval: 15s
    static_configs:
      - targets: ['otel-collector:8889']
```

**Key points**:
- Prometheus scrapes the OTLP Collector, NOT individual services
- 15-second scrape interval
- All metrics flow through the collector first

### Data Model

Prometheus stores time series data:

```
metric_name{label1="value1", label2="value2"} value timestamp

Example:
webstore_cart_additions_total{country="US", product_id="1"} 150 1634567890
```

**Components**:
- **Metric name**: `webstore_cart_additions_total`
- **Labels**: `country="US"`, `product_id="1"`
- **Value**: `150`
- **Timestamp**: `1634567890` (Unix timestamp)

## PromQL Queries

PromQL (Prometheus Query Language) is used to query and aggregate metrics.

### Basic Queries

**Instant vector** (current value):
```promql
# Current cart additions
webstore_cart_additions_total

# Filter by label
webstore_cart_additions_total{country="US"}

# Multiple filters
webstore_cart_additions_total{country="US", product_id="1"}
```

**Range vector** (values over time):
```promql
# Last 5 minutes of data
webstore_cart_additions_total[5m]
```

### Rate Calculations

**rate()** - Per-second rate over time range:
```promql
# Cart additions per second (5-minute average)
rate(webstore_cart_additions_total[5m])

# Requests per second
rate(http_server_requests_seconds_count[5m])

# Error rate
rate(http_server_requests_seconds_count{status=~"5.."}[5m])
```

**irate()** - Instant rate (last 2 data points):
```promql
# More sensitive to spikes
irate(webstore_cart_additions_total[5m])
```

### Aggregation

**sum()** - Add values together:
```promql
# Total cart additions across all countries
sum(rate(webstore_cart_additions_total[5m]))

# Per country
sum by (country) (rate(webstore_cart_additions_total[5m]))
```

**avg()** - Average:
```promql
# Average request duration
avg(rate(http_server_requests_seconds_sum[5m]) / rate(http_server_requests_seconds_count[5m]))
```

**max()** / **min()**:
```promql
# Maximum memory usage across all containers
max(container_memory_usage_bytes)
```

**count()**:
```promql
# Number of services reporting metrics
count(up{job="otel-collector"})
```

### Percentiles (Histograms)

**histogram_quantile()** - Calculate percentiles:
```promql
# P95 checkout amount
histogram_quantile(0.95, rate(webstore_checkout_amount_bucket[5m]))

# P99 request duration
histogram_quantile(0.99, rate(http_server_requests_seconds_bucket[5m]))
```

### Ratio Calculations

**Success rate**:
```promql
# Payment success rate
sum(rate(payments_processed_total{status="success"}[5m]))
/
sum(rate(payments_processed_total[5m]))
```

**Error rate**:
```promql
# HTTP error percentage
sum(rate(http_server_requests_seconds_count{status=~"5.."}[5m]))
/
sum(rate(http_server_requests_seconds_count[5m]))
* 100
```

### Useful Functions

**increase()** - Total increase over time:
```promql
# Total new carts in last hour
increase(webstore_cart_additions_total[1h])
```

**delta()** - Difference between first and last:
```promql
# Change in active carts
delta(webstore_active_carts[1h])
```

**predict_linear()** - Linear prediction:
```promql
# Predict disk usage in 4 hours
predict_linear(disk_usage_bytes[1h], 4*3600)
```

### Analytics Queries

**Funnel conversion rates**:
```promql
# Overall conversion rate (browse to checkout)
sum(rate(webstore_funnel_stage_total{stage="checkout_complete"}[5m]))
/ sum(rate(webstore_funnel_stage_total{stage="browse_catalog"}[5m]))

# Cart abandonment rate
1 - (
  sum(rate(webstore_funnel_stage_total{stage="checkout_complete"}[5m]))
  / sum(rate(webstore_funnel_stage_total{stage="add_to_cart"}[5m]))
)

# Country-specific funnel drop-off
sum(rate(webstore_funnel_stage_total[5m])) by (stage, country)
```

**Customer segmentation analysis**:
```promql
# Distribution of customers by segment
sum(rate(webstore_customer_segment_total[5m])) by (segment)

# VIP customer conversion rate
sum(rate(webstore_customer_segment_total{segment="vip", action="checkout"}[5m]))
/ sum(rate(webstore_customer_segment_total{segment="vip", action="browse_catalog"}[5m]))

# New vs returning customer checkout rate comparison
sum(rate(webstore_customer_segment_total{segment="new", action="checkout"}[5m]))
/
sum(rate(webstore_customer_segment_total{segment="returning", action="checkout"}[5m]))

# At-risk customer re-engagement tracking
sum(rate(webstore_customer_segment_total{segment="at_risk"}[5m])) by (action)
```

**Combined funnel + segmentation**:
```promql
# Segment-specific cart abandonment
1 - (
  sum(rate(webstore_customer_segment_total{action="checkout"}[5m])) by (segment)
  / sum(rate(webstore_customer_segment_total{action="add_to_cart"}[5m])) by (segment)
)

# VIP customers in browse stage (re-engagement opportunity)
sum(rate(webstore_customer_segment_total{segment="vip", action="browse_catalog"}[5m]))
```

## Grafana Dashboards

### Pre-built Dashboards

This project includes 4 dashboards in [grafana/dashboards/](../grafana/dashboards/):

**1. WebStore Overview** ([webstore-overview.json](../grafana/dashboards/webstore-overview.json)):
- Cart additions by country (time series)
- Checkout rates and conversion
- Payment failure rates by country
- Active carts gauge
- Country-specific metrics table

**2. Service Health** ([service-health.json](../grafana/dashboards/service-health.json)):
- Request rate (RPS) per service
- Error rates with thresholds
- Latency percentiles (P50, P95, P99)
- Service status table
- External dependency health
- Database and Redis metrics

**3. SLO Tracking** ([slo-tracking.json](../grafana/dashboards/slo-tracking.json)):
- Availability SLI (99.9% target)
- Latency SLI (P95 < 1s)
- Payment success SLI (>90%)
- Error budget tracking
- Burn rate monitoring

**4. System Metrics** ([system-metrics.json](../grafana/dashboards/system-metrics.json)):
- Container CPU usage
- Container memory usage
- Network I/O
- Disk I/O
- Note: Requires container ID updates on macOS

### Dashboard Components

**Panels**:
- **Time series** - Line graphs over time
- **Stat** - Single number (current value)
- **Gauge** - Visual indicator with thresholds
- **Table** - Tabular data
- **Heatmap** - Distribution visualization
- **Bar chart** - Categorical comparison

**Variables**:
```
$country    - Filter by country
$service    - Filter by service
$interval   - Time range for rate calculations
```

## Creating Custom Dashboards

### Step 1: Create Dashboard

1. Open Grafana: http://localhost:3000
2. Click **+** → **Dashboard**
3. Click **Add new panel**

### Step 2: Write Query

Click **Metrics browser** or enter query directly:

```promql
# Example: Cart additions per second by country
sum by (country) (rate(webstore_cart_additions_total[5m]))
```

### Step 3: Configure Visualization

**Panel options**:
- **Title**: "Cart Additions by Country"
- **Description**: "Rate of items added to cart per second"

**Legend**:
- **Mode**: Table
- **Values**: Last, Max, Min

**Graph styles**:
- **Style**: Lines
- **Line width**: 2
- **Fill opacity**: 10

**Thresholds**:
- Red: < 0.5
- Yellow: 0.5 - 1
- Green: > 1

### Step 4: Add Transform (Optional)

**Rename fields**:
```
{country="US"} → United States
{country="UK"} → United Kingdom
```

**Calculate field**:
```
Conversion Rate = checkouts / cart_additions * 100
```

### Example: Checkout Conversion Dashboard

**Panel 1: Conversion Rate**
```promql
sum(rate(webstore_checkouts_total[5m]))
/
sum(rate(webstore_cart_additions_total[5m]))
* 100
```

**Panel 2: Cart Additions (Time Series)**
```promql
sum by (country) (rate(webstore_cart_additions_total[5m]))
```

**Panel 3: Failed Checkouts**
```promql
sum by (country) (rate(webstore_checkouts_total{status="failed"}[5m]))
```

**Panel 4: Top Products**
```promql
topk(5, sum by (product_id) (rate(webstore_cart_additions_total[5m])))
```

## Best Practices

### 1. Use Rate for Counters

❌ **Don't** query counters directly:
```promql
webstore_cart_additions_total
```

✅ **Do** use rate():
```promql
rate(webstore_cart_additions_total[5m])
```

### 2. Choose Appropriate Time Ranges

**5m** - Most queries (good balance)
```promql
rate(webstore_cart_additions_total[5m])
```

**1m** - Sensitive to spikes (alerts)
```promql
rate(http_requests_total{status="500"}[1m]) > 0.1
```

**1h** - Smoothing long-term trends
```promql
rate(webstore_cart_additions_total[1h])
```

### 3. Use Meaningful Labels

✅ **Good**:
```promql
sum by (country, payment_method) (rate(payments_processed_total[5m]))
```

❌ **Bad** (too many labels, hard to read):
```promql
sum by (country, payment_method, status, user_tier, product_category) (...)
```

### 4. Add Descriptions to Panels

Every panel should have:
- **Title**: What is being measured
- **Description**: Why it matters, how to interpret
- **Unit**: Requests/sec, %, ms, bytes

### 5. Set Meaningful Thresholds

**Error rate**:
- Green: < 1%
- Yellow: 1-5%
- Red: > 5%

**Latency (P95)**:
- Green: < 500ms
- Yellow: 500ms-1s
- Red: > 1s

### 6. Group Related Metrics

Create rows for logical grouping:
- **Row 1**: Business Metrics
- **Row 2**: Service Health
- **Row 3**: Infrastructure

### 7. Use Variables for Flexibility

```
$service   - Allow filtering by service
$country   - Allow filtering by country
$interval  - Allow changing time range
```

Query with variable:
```promql
rate(webstore_cart_additions_total{country="$country"}[$interval])
```

## Common Queries

### Business Metrics

**Conversion rate**:
```promql
sum(rate(webstore_checkouts_total{status="success"}[5m]))
/
sum(rate(webstore_cart_additions_total[5m]))
* 100
```

**Revenue (approximate)**:
```promql
sum(rate(webstore_checkout_amount_sum[5m]))
```

**Top countries by activity**:
```promql
topk(5, sum by (country) (rate(webstore_cart_additions_total[5m])))
```

### Service Health

**Request rate**:
```promql
sum by (service) (rate(http_server_requests_seconds_count[5m]))
```

**Error rate**:
```promql
sum by (service) (rate(http_server_requests_seconds_count{status=~"5.."}[5m]))
/
sum by (service) (rate(http_server_requests_seconds_count[5m]))
* 100
```

**P95 latency**:
```promql
histogram_quantile(0.95,
  sum by (service, le) (rate(http_server_requests_seconds_bucket[5m]))
)
```

**Service availability (SLI)**:
```promql
1 - (
  sum(rate(http_server_requests_seconds_count{status=~"5.."}[5m]))
  /
  sum(rate(http_server_requests_seconds_count[5m]))
)
```

### Infrastructure

**CPU usage**:
```promql
rate(container_cpu_usage_seconds_total{name=~".*main-service.*"}[5m]) * 100
```

**Memory usage**:
```promql
container_memory_usage_bytes{name=~".*main-service.*"} / 1024 / 1024
```

**Database connections**:
```promql
db_pool_connections_active / db_pool_connections_max * 100
```

## Hands-On Exercise

### Exercise 1: Create a Payment Success Dashboard

1. Open Grafana → Create new dashboard
2. Add panel with query:
   ```promql
   sum by (country) (rate(payments_processed_total{status="success"}[5m]))
   ```
3. Add second panel:
   ```promql
   sum by (country) (rate(payments_processed_total{status="failed"}[5m]))
   ```
4. Add stat panel with total success rate:
   ```promql
   sum(rate(payments_processed_total{status="success"}[5m]))
   /
   sum(rate(payments_processed_total[5m]))
   * 100
   ```
5. Save dashboard as "Payment Analytics"

### Exercise 2: Find Slow Requests

1. Open Prometheus: http://localhost:9090
2. Query P99 latency:
   ```promql
   histogram_quantile(0.99, rate(http_server_requests_seconds_bucket[5m]))
   ```
3. Find services with P99 > 1s:
   ```promql
   histogram_quantile(0.99,
     sum by (service, le) (rate(http_server_requests_seconds_bucket[5m]))
   ) > 1
   ```

---

**Next**: Learn about distributed tracing → [Distributed Tracing](05_DISTRIBUTED_TRACING.md)
