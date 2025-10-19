# Trace Sampling Strategy - Technical Reference

> **Note**: For an introduction to distributed tracing and sampling, see [05_DISTRIBUTED_TRACING.md](05_DISTRIBUTED_TRACING.md).
> This document provides **detailed technical specifications** for the tail sampling configuration.

## Overview

The WebStore monitoring example uses **value-based tail sampling** in the OpenTelemetry Collector with 12 policies optimized for e-commerce observability.

**Expected outcomes**:
- ~30% overall sampling rate (100% critical + 10% baseline)
- 70% reduction in storage costs
- Zero loss of critical traces (errors, slow requests, high-value transactions)

## Complete Sampling Configuration

File: [otel-collector-config.yaml](../otel-collector-config.yaml)

### Policy Execution Order

Policies are evaluated sequentially. A trace is sampled if **any** policy matches:

| Priority | Policy Name | Type | Sample Rate | Matches |
|----------|------------|------|-------------|---------|
| 1 | errors-always | status_code | 100% | All ERROR spans |
| 2 | very-slow-always | latency | 100% | >5s requests |
| 3 | slow-requests | latency | 100% | >1s requests |
| 4 | critical-endpoints | string_attribute | 100% | /api/orders, /api/payments/process, /cart/checkout |
| 5 | admin-users | string_attribute | 100% | Admin/test user traces |
| 6 | high-value-transactions | numeric_attribute | 100% | Transactions >$1000 |
| 7 | high-risk-countries | string_attribute | 100% | BR, IN, MX |
| 8 | external-services | string_attribute | 100% | payment-provider, crm-system, inventory-system |
| 9 | medium-latency | latency | 50% | 500ms-1s requests |
| 10 | failed-payments | string_attribute | 100% | payment.status=failed |
| 11 | slow-db-queries | numeric_attribute | 100% | DB queries >500ms |
| 12 | probabilistic-baseline | probabilistic | 10% | Everything else |

## Policy Specifications

### 1. Error Sampling

```yaml
- name: errors-always
  type: status_code
  status_code:
    status_codes: [ERROR]
```

**Matches**: Any trace containing at least one ERROR span
**Business Justification**: All errors need investigation for reliability
**Estimated Volume**: ~2-5% of traces (depending on error rate)

### 2. Latency-Based Sampling

**Critical Latency** (>5s):
```yaml
- name: very-slow-always
  type: latency
  latency:
    threshold_ms: 5000
```
- **Matches**: Traces taking >5 seconds end-to-end
- **Business Justification**: Severe user experience degradation
- **Estimated Volume**: <1% of traces

**High Latency** (>1s):
```yaml
- name: slow-requests
  type: latency
  latency:
    threshold_ms: 1000
```
- **Matches**: Traces >1s (exceeds SLO target)
- **Business Justification**: Performance optimization opportunities
- **Estimated Volume**: ~5-10% of traces

**Medium Latency** (500ms-1s, 50% sampled):
```yaml
- name: medium-latency
  type: latency
  latency:
    threshold_ms: 500
    sampling_percentage: 50
```
- **Matches**: 50% of traces between 500ms-1s
- **Business Justification**: Statistical performance analysis
- **Estimated Volume**: ~5% of traces sampled (10% total × 50%)

### 3. Business Value Sampling

**High-Value Transactions** (>$1000):
```yaml
- name: high-value-transactions
  type: numeric_attribute
  numeric_attribute:
    key: transaction.amount
    min_value: 1000
```
- **Matches**: Checkout/payment transactions >$1000
- **Business Justification**: High-revenue transaction debugging
- **Estimated Volume**: ~2-3% of traces

**Failed Payments**:
```yaml
- name: failed-payments
  type: string_attribute
  string_attribute:
    key: payment.status
    values: [failed, declined, error]
```
- **Matches**: All failed payment attempts
- **Business Justification**: Revenue recovery and fraud detection
- **Estimated Volume**: ~5-15% of payment traces (varies by country)

### 4. Geographic Sampling

**High-Risk Countries**:
```yaml
- name: high-risk-countries
  type: string_attribute
  string_attribute:
    key: user.country
    values: [BR, IN, MX]
```
- **Matches**: Traffic from Brazil, India, Mexico
- **Business Justification**: Higher failure rates, fraud analysis
- **Estimated Volume**: ~20-30% of total traffic

### 5. Critical Endpoints

```yaml
- name: critical-endpoints
  type: string_attribute
  string_attribute:
    key: http.target
    values:
      - /api/orders
      - /api/payments/process
      - /cart/checkout
```
- **Matches**: Revenue-generating endpoints
- **Business Justification**: Mission-critical flows
- **Estimated Volume**: ~15-20% of requests

### 6. Admin and Test Traffic

```yaml
- name: admin-users
  type: string_attribute
  string_attribute:
    key: user.id
    values: [admin, test, user-token-123]
```
- **Matches**: Internal testing and admin operations
- **Business Justification**: Debugging, QA verification
- **Estimated Volume**: ~1-2% of traffic

### 7. External Service Calls

```yaml
- name: external-services
  type: string_attribute
  string_attribute:
    key: peer.service
    values:
      - payment-provider
      - crm-system
      - inventory-system
```
- **Matches**: Calls to third-party integrations
- **Business Justification**: Third-party SLA monitoring, integration debugging
- **Estimated Volume**: ~30% of traces (many requests call multiple external services)

### 8. Slow Database Queries

```yaml
- name: slow-db-queries
  type: numeric_attribute
  numeric_attribute:
    key: db.query.duration_ms
    min_value: 500
```
- **Matches**: Database queries >500ms
- **Business Justification**: Database optimization
- **Estimated Volume**: ~1-3% of traces

### 9. Baseline Probabilistic Sampling

```yaml
- name: probabilistic-baseline
  type: probabilistic
  probabilistic:
    sampling_percentage: 10
```
- **Matches**: 10% of all other traces
- **Business Justification**: Statistical baseline, unexpected patterns
- **Estimated Volume**: ~10% of remaining traces (~5-7% of total)

## Composite Policy Example

To sample based on **multiple conditions** (AND logic), create a composite policy:

```yaml
# Sample: High-value transactions from high-risk countries
- name: high-value-high-risk
  type: and
  and:
    and_sub_policy:
      - name: high-value
        type: numeric_attribute
        numeric_attribute:
          key: transaction.amount
          min_value: 1000
      - name: risk-country
        type: string_attribute
        string_attribute:
          key: user.country
          values: [BR, IN]
```

## Expected Sampling Rates by Scenario

| Scenario | Matching Policies | Sample Rate |
|----------|------------------|-------------|
| Successful fast request (US, $50) | probabilistic-baseline | 10% |
| Error in any request | errors-always | 100% |
| Slow request (2s) | slow-requests | 100% |
| Checkout endpoint | critical-endpoints | 100% |
| Failed payment (any country) | failed-payments | 100% |
| High-value ($1500, any country) | high-value-transactions | 100% |
| Brazil traffic ($50, fast) | high-risk-countries | 100% |
| External API call | external-services | 100% |
| Medium latency (700ms) | medium-latency | 50% |

## Storage Impact Calculation

**Before sampling** (100% retention):
- 1000 requests/min = 1,440,000 traces/day
- Avg trace size: 50 KB
- Daily storage: ~72 GB/day
- Monthly storage: ~2.2 TB/month

**After sampling** (~30% retention):
- Sampled traces: ~430,000 traces/day
- Daily storage: ~21.5 GB/day
- Monthly storage: ~645 GB/month
- **Savings: ~70%**

## Customization Guide

### Adjusting Sampling Rates

**Increase baseline sampling** (more statistical accuracy):
```yaml
probabilistic:
  sampling_percentage: 20  # Was 10%
```

**Sample fewer medium-latency traces**:
```yaml
latency:
  threshold_ms: 500
  sampling_percentage: 25  # Was 50%
```

### Adding Custom Policies

**Sample VIP customers**:
```yaml
- name: vip-customers
  type: string_attribute
  string_attribute:
    key: user.tier
    values: [platinum, gold]
```

**Sample specific product categories**:
```yaml
- name: electronics-category
  type: string_attribute
  string_attribute:
    key: product.category
    values: [electronics, computers]
```

**Sample based on user-agent** (bot detection):
```yaml
- name: bot-traffic
  type: string_attribute
  string_attribute:
    key: http.user_agent
    values: [bot, crawler, spider]
```

### Policy Best Practices

1. **Order matters**: Place most restrictive (100%) policies first
2. **Use AND policies sparingly**: They're harder to debug
3. **Monitor sampling rates**: Track `otelcol_processor_tail_sampling_policy_decision`
4. **Start conservative**: Begin with higher sampling, reduce gradually
5. **Document business justification**: Each policy should have clear value

## Monitoring Sampling Effectiveness

### Collector Metrics

```promql
# Traces sampled per policy
otelcol_processor_tail_sampling_policy_decision{decision="sampled"}

# Traces dropped per policy
otelcol_processor_tail_sampling_policy_decision{decision="dropped"}

# Sampling rate by policy
rate(otelcol_processor_tail_sampling_policy_decision{decision="sampled"}[5m])
/
rate(otelcol_processor_tail_sampling_policy_decision[5m])
```

### Grafana Dashboard Queries

**Overall sampling rate**:
```promql
sum(rate(otelcol_processor_tail_sampling_policy_decision{decision="sampled"}[5m]))
/
sum(rate(otelcol_processor_tail_sampling_policy_decision[5m]))
* 100
```

**Top sampled policies**:
```promql
topk(5,
  sum by (policy) (
    rate(otelcol_processor_tail_sampling_policy_decision{decision="sampled"}[5m])
  )
)
```

## Performance Considerations

**Memory Requirements**:
- Tail sampling buffers complete traces in memory
- Default: 100 traces buffered (`num_traces: 100`)
- Increase for high-traffic: `num_traces: 1000`

**Decision Wait Time**:
- Default: 10 seconds (`decision_wait: 10s`)
- Trade-off: Longer wait = more complete traces, higher memory
- Recommended: 10-30 seconds

**Expected Traces per Second**:
- Configure based on traffic: `expected_new_traces_per_sec: 100`
- Too low: Traces dropped before evaluation
- Too high: Excessive memory usage

## Troubleshooting

### Traces Missing Despite Matching Policy

**Check**: Policy evaluation order
```bash
# View collector logs for sampling decisions
docker-compose logs otel-collector | grep tail_sampling
```

**Solution**: Ensure your policy appears before the probabilistic baseline

### High Memory Usage

**Check**: Buffered trace count
```promql
otelcol_processor_tail_sampling_traces_on_memory
```

**Solution**: Reduce `decision_wait` or `num_traces`

### Sampling Rate Too Low

**Check**: Policy hit rates
```promql
rate(otelcol_processor_tail_sampling_policy_decision{decision="sampled"}[5m])
```

**Solution**: Increase `probabilistic_percentage` or add more specific policies

---

**Related Documentation**:
- [05_DISTRIBUTED_TRACING.md](05_DISTRIBUTED_TRACING.md) - Introduction to tracing
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture
- [otel-collector-config.yaml](../otel-collector-config.yaml) - Full configuration
