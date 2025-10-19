# Analytics & Security Features Implementation Summary

This document summarizes three major features added to the Main Service for enhanced analytics and production-ready security.

## 1. Funnel Analysis 📊

### Overview
Tracks user progression through the complete purchase funnel to identify drop-off points and optimize conversion.

### Funnel Stages
```
Browse Catalog → View Product → Add to Cart → Checkout Complete
```

### Implementation

**Metric**: `webstore.funnel.stage`

**Attributes**:
- `stage`: browse_catalog, view_product, add_to_cart, checkout_complete
- `country`: Country code (US, UK, DE, FR, JP, BR, IN)
- `payment_method`: For checkout_complete stage

**Code Locations**:
- [monitoring.py:94-99](services/main-service/monitoring.py#L94-L99) - Metric definition
- [routers/products.py:74-77](services/main-service/routers/products.py#L74-L77) - Browse tracking
- [routers/products.py:120-123](services/main-service/routers/products.py#L120-L123) - View product tracking
- [routers/cart.py:52-55](services/main-service/routers/cart.py#L52-L55) - Add to cart tracking
- [routers/orders.py:39-43](services/main-service/routers/orders.py#L39-L43) - Checkout tracking

### Usage in Grafana

**Example Queries**:
```promql
# Funnel conversion rates by country
sum(rate(webstore_funnel_stage_total{stage="checkout_complete"}[5m])) by (country)
/ sum(rate(webstore_funnel_stage_total{stage="browse_catalog"}[5m])) by (country)

# Drop-off at each stage
sum(rate(webstore_funnel_stage_total[5m])) by (stage, country)
```

**Dashboard Visualization**:
- Funnel chart showing progression: Browse → View → Cart → Checkout
- Country-specific conversion rates
- Time-series of each funnel stage

---

## 2. Customer Segmentation 👥

### Overview
Automatically classifies customers into behavioral segments based on activity patterns, enabling targeted analytics and business intelligence.

### Customer Segments

| Segment | Definition | Criteria |
|---------|------------|----------|
| **new** | First-time visitor | No previous activity recorded |
| **returning** | Active customer | Activity in last 30 days |
| **vip** | High-value customer | >$500 total spend OR >5 orders |
| **at_risk** | Declining engagement | Last activity 30-90 days ago |
| **churned** | Inactive customer | No activity in 90+ days |

### Implementation

**Service**: `CustomerSegmentationService` (Redis-backed)

**Metric**: `webstore.customer.segment`

**Attributes**:
- `segment`: new, returning, vip, at_risk, churned
- `action`: browse_catalog, view_product, add_to_cart, checkout
- `country`: Country code

**Code Locations**:
- [customer_segmentation.py](services/main-service/customer_segmentation.py) - Full service implementation
- [dependencies.py:23-26](services/main-service/dependencies.py#L23-L26) - Dependency injection
- [routers/products.py:67-71](services/main-service/routers/products.py#L67-L71) - Browse tracking
- [routers/cart.py:48-50](services/main-service/routers/cart.py#L48-L50) - Cart tracking
- [routers/orders.py:35-36](services/main-service/routers/orders.py#L35-L36) - Checkout tracking

### Data Storage (Redis)

**Keys**:
- `customer:{user_id}:activity` - Last activity timestamp
- `customer:{user_id}:spend` - Total spend (USD)
- `customer:{user_id}:orders` - Total order count

**TTL**: 90 days (automatic cleanup of churned customers)

### Usage in Grafana

**Example Queries**:
```promql
# Actions by customer segment
sum(rate(webstore_customer_segment_total[5m])) by (segment, action)

# VIP customer checkout rate
sum(rate(webstore_customer_segment_total{segment="vip", action="checkout"}[5m]))

# At-risk customer engagement
sum(rate(webstore_customer_segment_total{segment="at_risk"}[5m])) by (action)
```

**Dashboard Visualization**:
- Pie chart: Customer distribution by segment
- Time-series: Segment-specific conversion rates
- Table: Top actions per segment

---

## 3. Redis-Backed Rate Limiting 🔒

### Overview
Production-ready distributed rate limiting using Redis for state persistence across service restarts and horizontal scaling.

### Advantages Over In-Memory Rate Limiting

| Feature | In-Memory | Redis-Backed |
|---------|-----------|--------------|
| **Survives Restarts** | ❌ Lost on restart | ✅ Persists in Redis |
| **Horizontal Scaling** | ❌ Per-instance state | ✅ Shared across instances |
| **Race Conditions** | ⚠️ Requires locks | ✅ Atomic pipeline ops |
| **Memory Management** | ⚠️ Manual cleanup | ✅ Automatic TTL expiration |
| **Window Accuracy** | ⚠️ Fixed buckets | ✅ True sliding window |

### Dual-Tier Rate Limiting

**Why Two Limits?**

Many legitimate users share the same IP address (corporate networks, ISP CGNAT, public WiFi, schools).

| Limit Type | Requests/Min | Rationale |
|------------|--------------|-----------|
| **IP-based** | 200 | Accommodate shared IPs |
| **User-based** | 60 | Stricter individual limits |

### Algorithm (Sliding Window)

1. **Remove old entries**: `ZREMRANGEBYSCORE key 0 {window_start}`
2. **Count requests**: `ZCARD key`
3. **Add current request**: `ZADD key {timestamp} {timestamp}`
4. **Set TTL**: `EXPIRE key {window + 1}`

All operations run in a Redis pipeline for atomicity.

### Implementation

**Class**: `RedisRateLimiter` (FastAPI middleware)

**Redis Keys**:
- `rate:ip:{ip_address}` - IP-based rate limit tracking
- `rate:user:{user_id}` - User-based rate limit tracking
- `suspicious:401:{ip}` - Failed auth tracking (credential stuffing)
- `suspicious:404:{ip}` - 404 tracking (endpoint scanning)
- `suspicious:4xx:{ip}` - General 4xx tracking (abuse)

**Code Locations**:
- [redis_rate_limiter.py](services/main-service/redis_rate_limiter.py) - Full implementation
- [main.py:33](services/main-service/main.py#L33) - Redis client initialization
- [main.py:81-86](services/main-service/main.py#L81-L86) - Middleware registration

### Suspicious Activity Detection

**Patterns Detected**:

| Pattern | Threshold | Detection Window | Metric |
|---------|-----------|-----------------|--------|
| **Credential Stuffing** | 5+ failed auths | 5 minutes | `suspicious_activity_total{type="credential_stuffing"}` |
| **Endpoint Scanning** | 10+ 404s | 5 minutes | `suspicious_activity_total{type="endpoint_scanning"}` |
| **General Abuse** | 20+ 4xx errors | 5 minutes | `suspicious_activity_total{type="abuse"}` |

### Error Handling

**Fail Open Strategy**: If Redis is unavailable, allow requests to proceed (logged as error).

```python
except redis.RedisError as e:
    logger.error(f"Redis rate limit error: {e}")
    return True, 0  # Allow request
```

### HTTP Response (Rate Limited)

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 60

{
  "detail": "Rate limit exceeded for IP. Maximum 200 requests per minute."
}
```

### Metrics

```promql
# Rate limit violations by type
webstore_rate_limit_exceeded_total{limit_type="ip", client_ip="..."}
webstore_rate_limit_exceeded_total{limit_type="user", user_id="..."}

# Suspicious activity
webstore_security_suspicious_activity_total{type="credential_stuffing"}
webstore_security_suspicious_activity_total{type="endpoint_scanning"}
webstore_security_suspicious_activity_total{type="abuse"}
```

---

## Testing the Features

### 1. Test Funnel Analysis

```bash
# Generate traffic through the funnel
./scripts/generate-traffic.sh

# View funnel metrics in Grafana
# Dashboard → WebStore Overview → Funnel Analysis panel
```

### 2. Test Customer Segmentation

```bash
# Simulate different customer behaviors
curl -H "Authorization: Bearer user-token-123" \
  http://localhost:8000/us/products

# Check customer segment in Redis
docker exec -it monitoring-example-redis-1 redis-cli
> HGETALL customer:user_user-token:activity
> HGETALL customer:user_user-token:spend
```

### 3. Test Rate Limiting

```bash
# Test IP-based rate limiting (201st request will be rate limited)
for i in {1..201}; do
  curl http://localhost:8000/us/products
done

# Test user-based rate limiting (61st request will be rate limited)
for i in {1..61}; do
  curl -H "Authorization: Bearer user-token-123" \
    http://localhost:8000/us/products
done

# View rate limit metrics
curl http://localhost:9090/api/v1/query?query=webstore_rate_limit_exceeded_total
```

---

## Grafana Dashboard Integration

All three features integrate seamlessly with the existing Grafana dashboards:

1. **WebStore Overview Dashboard**
   - Funnel analysis panel
   - Customer segment distribution
   - Conversion rates by segment

2. **Service Health Dashboard**
   - Rate limiting violations
   - Suspicious activity alerts

3. **Logs Explorer**
   - Filter by customer segment: `{segment="vip"}`
   - Filter by rate limit events: `"Rate limit exceeded"`
   - Filter by suspicious activity: `"Suspicious activity"`

---

## Production Considerations

### Funnel Analysis
- ✅ Low overhead: Simple counter increments
- ✅ No PII stored: Only aggregated metrics
- ⚠️ Consider sampling for extremely high traffic

### Customer Segmentation
- ✅ Redis TTL prevents unbounded growth
- ✅ Segment calculation is lightweight (Redis hash lookups)
- ⚠️ Monitor Redis memory usage (90-day retention per customer)

### Rate Limiting
- ✅ Redis clustering for high availability
- ✅ Fail-open prevents service disruption
- ⚠️ Tune limits based on load testing
- ⚠️ Consider Redis persistence (RDB/AOF) for rate limit state

---

## Related Documentation

- [Architecture Overview](docs/02_ARCHITECTURE_OVERVIEW.md) - Security architecture
- [OpenTelemetry Instrumentation](docs/03_OPENTELEMETRY_INSTRUMENTATION.md) - Metrics setup
- [Metrics and Dashboards](docs/04_METRICS_AND_DASHBOARDS.md) - Grafana dashboards
- [Alerting and SLOs](docs/08_ALERTING_AND_SLOS.md) - Security alerts

---

**Implementation Date**: October 21, 2025
**Services Modified**: Main Service
**Dependencies**: Redis, OpenTelemetry, Prometheus, Grafana
