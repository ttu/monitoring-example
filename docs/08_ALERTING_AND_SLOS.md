# Alerting and SLOs

**Reading time**: 17 minutes

Learn how to configure alerts, define Service Level Objectives (SLOs), track error budgets, and respond to production issues.

## Table of Contents

- [Introduction to Alerting](#introduction-to-alerting)
- [Alert Configuration](#alert-configuration)
- [Alert Categories](#alert-categories)
- [Alertmanager Routing](#alertmanager-routing)
- [Service Level Objectives (SLOs)](#service-level-objectives-slos)
- [Error Budget Tracking](#error-budget-tracking)
- [Hands-On Exercise](#hands-on-exercise)

## Introduction to Alerting

**Alerting** notifies you when something goes wrong in production, allowing you to respond before users are significantly impacted.

### The Alerting Stack

```
┌─────────────────────────────────────────────┐
│ Services emit metrics                       │
│ (http_server_duration, payments_processed)  │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ Prometheus evaluates alert rules            │
│ prometheus-alerts.yml                       │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ Alertmanager routes and groups alerts       │
│ alertmanager.yml                            │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ Receivers send notifications                │
│ (Slack, PagerDuty, Email, Webhooks)        │
└─────────────────────────────────────────────┘
```

### Key Concepts

- **Alert Rule**: Condition that triggers an alert (e.g., error rate > 5%)
- **Firing**: Alert condition is currently true
- **Pending**: Alert condition is true but hasn't reached `for` duration yet
- **Resolved**: Alert condition is no longer true
- **Inhibition**: Suppress alerts when related alerts are firing
- **Routing**: Send alerts to different receivers based on labels

## Alert Configuration

Alerts are defined in **`prometheus-alerts.yml`** and grouped by category.

### Alert Rule Structure

```yaml
groups:
  - name: webstore_alerts
    interval: 30s  # How often to evaluate rules
    rules:
      - alert: HighErrorRate
        expr: |
          (
            sum(rate(http_server_duration_count{http_status_code=~"5.."}[5m]))
            /
            sum(rate(http_server_duration_count[5m]))
          ) > 0.05
        for: 5m  # Condition must be true for 5 minutes
        labels:
          severity: critical
          team: platform
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value | humanizePercentage }} (threshold: 5%)"
```

**Components**:
- **alert**: Name of the alert
- **expr**: PromQL query that defines the condition
- **for**: Duration before alert fires (prevents flapping)
- **labels**: Metadata for routing (severity, team, etc.)
- **annotations**: Human-readable information (summary, description, runbook)

### Alert States

An alert goes through these states:

```
Inactive → Pending (condition true, waiting for 'for' duration)
         ↓
      Firing (condition true for 'for' duration)
         ↓
      Resolved (condition no longer true)
```

## Alert Categories

Our project includes 18+ alerts organized into 4 categories.

### 1. Service Health Alerts

Monitor service availability and error rates.

#### ServiceDown

Triggers when a service stops responding.

```yaml
- alert: ServiceDown
  expr: up{job=~"main-service|payments-service|promotions-service"} == 0
  for: 2m
  labels:
    severity: critical
    team: platform
  annotations:
    summary: "Service {{ $labels.job }} is down"
    description: "{{ $labels.job }} has been down for more than 2 minutes"
```

**What it detects**: Service container crashed or not responding to health checks.

**Response**: Check container logs, restart service if needed.

#### HighErrorRate

Triggers when HTTP 5xx errors exceed 5% of total requests.

```yaml
- alert: HighErrorRate
  expr: |
    (
      sum(rate(http_server_duration_count{http_status_code=~"5.."}[5m]))
      /
      sum(rate(http_server_duration_count[5m]))
    ) > 0.05
  for: 5m
  labels:
    severity: critical
    team: platform
```

**What it detects**: Elevated server errors across all services.

**Response**: Check logs for error patterns, investigate recent deployments.

#### HighExternalServiceFailureRate

Monitors failures when calling external services (CRM, Inventory, Payment Provider).

```yaml
- alert: HighExternalServiceFailureRate
  expr: |
    (
      sum by (service) (rate(external_call_total{status=~"error|timeout"}[5m]))
      /
      sum by (service) (rate(external_call_total[5m]))
    ) > 0.15
  for: 10m
  labels:
    severity: warning
    team: platform
```

**What it detects**: External service integration issues.

**Response**: Check external service status, verify network connectivity.

### 2. Resource Alerts

Monitor resource utilization.

#### HighDatabaseConnectionUsage

Triggers when database connection pool usage exceeds 80%.

```yaml
- alert: HighDatabaseConnectionUsage
  expr: |
    (
      sum(db_pool_connections_in_use)
      /
      sum(db_pool_connections_max)
    ) > 0.80
  for: 5m
  labels:
    severity: warning
    team: platform
  annotations:
    summary: "High database connection pool usage"
    description: "Database connection pool usage is {{ $value | humanizePercentage }}"
```

**What it detects**: Potential connection pool exhaustion.

**Response**: Investigate slow queries, consider increasing pool size.

#### HighRedisMemoryUsage

Monitors Redis memory consumption.

```yaml
- alert: HighRedisMemoryUsage
  expr: |
    (
      redis_memory_used_bytes / redis_memory_max_bytes
    ) > 0.85
  for: 5m
  labels:
    severity: warning
```

**Response**: Review cache eviction policy, clear unnecessary keys.

### 3. Business Metrics Alerts

Track business-critical operations.

#### HighPaymentFailureRate

Monitors payment success rate.

```yaml
- alert: HighPaymentFailureRate
  expr: |
    (
      sum(rate(payments_processed_total{status="failed"}[5m]))
      /
      sum(rate(payments_processed_total[5m]))
    ) > 0.10
  for: 5m
  labels:
    severity: warning
    team: payments
  annotations:
    summary: "High payment failure rate"
    description: "Payment failure rate is {{ $value | humanizePercentage }} (threshold: 10%)"
```

**Impact**: Direct revenue loss.

**Response**: Check payment provider status, investigate country-specific issues.

#### CriticalPaymentFailureRateByCountry

Monitors payment failures per country.

```yaml
- alert: CriticalPaymentFailureRateByCountry
  expr: |
    (
      sum by (country) (rate(payments_processed_total{status="failed"}[5m]))
      /
      sum by (country) (rate(payments_processed_total[5m]))
    ) > 0.20
  for: 10m
  labels:
    severity: critical
    team: payments
  annotations:
    summary: "Critical payment failure rate in {{ $labels.country }}"
```

**Impact**: Regional payment outage.

**Response**: Check country-specific payment provider issues.

#### LowCheckoutConversionRate

Tracks cart-to-checkout conversion.

```yaml
- alert: LowCheckoutConversionRate
  expr: |
    (
      sum(rate(webstore_checkouts_total{status="completed"}[30m]))
      /
      sum(rate(webstore_cart_additions_total[30m]))
    ) < 0.10
  for: 30m
  labels:
    severity: warning
    team: business
```

**What it detects**: Unusual drop in conversion rate.

**Response**: Check for UX issues, payment gateway problems.

### 4. Latency Alerts

Monitor response time degradation.

#### HighLatencyP95

Triggers when P95 latency exceeds 2 seconds.

```yaml
- alert: HighLatencyP95
  expr: |
    histogram_quantile(0.95,
      sum(rate(http_server_duration_bucket[5m])) by (le, service_name)
    ) > 2
  for: 10m
  labels:
    severity: warning
    team: platform
  annotations:
    summary: "High P95 latency on {{ $labels.service_name }}"
    description: "P95 latency is {{ $value | humanizeDuration }} (threshold: 2s)"
```

**Impact**: Degraded user experience.

**Response**: Check for slow database queries, external service issues.

#### SlowPaymentProcessing

Monitors payment processing time.

```yaml
- alert: SlowPaymentProcessing
  expr: |
    histogram_quantile(0.95,
      sum(rate(payment_duration_seconds_bucket[5m])) by (le, country)
    ) > 3
  for: 10m
  labels:
    severity: warning
    team: payments
```

**Response**: Investigate payment provider latency by country.

## Alertmanager Routing

**Alertmanager** groups, routes, and deduplicates alerts before sending notifications.

### Configuration: alertmanager.yml

```yaml
route:
  receiver: 'default'
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 10s       # Wait before sending first notification
  group_interval: 10s   # Wait before sending new alerts in group
  repeat_interval: 12h  # Wait before resending

  routes:
    # Critical alerts
    - match:
        severity: critical
      receiver: 'critical'
      group_wait: 10s
      repeat_interval: 1h

    # Team-specific routing
    - match:
        team: payments
      receiver: 'team-payments'
```

### Grouping

Alerts are grouped by common labels to reduce notification noise:

```
Instead of:
  - ServiceDown: main-service
  - HighErrorRate: main-service
  - HighLatency: main-service
  (3 separate notifications)

You get:
  - Alert Group: main-service
    • ServiceDown
    • HighErrorRate
    • HighLatency
  (1 combined notification)
```

### Inhibition Rules

Suppress alerts when more critical alerts are firing:

```yaml
inhibit_rules:
  # Suppress warning if critical is firing
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'service']

  # Suppress high error rate if service is down
  - source_match:
      alertname: 'ServiceDown'
    target_match_re:
      alertname: 'High.*Rate'
    equal: ['service']
```

**Example**: If `ServiceDown` is firing, don't also alert on `HighErrorRate` for the same service (obviously errors are high if the service is down!).

### Receivers

Define where to send alerts:

```yaml
receivers:
  - name: 'critical'
    # In production: configure PagerDuty, Slack, email
    webhook_configs:
      - url: 'http://localhost:5001/webhook/critical'

    # Uncomment for Slack
    # slack_configs:
    #   - api_url: 'YOUR_SLACK_WEBHOOK_URL'
    #     channel: '#alerts-critical'
    #     title: 'CRITICAL: {{ .GroupLabels.alertname }}'

  - name: 'team-payments'
    # Send payments team alerts to their channel
    webhook_configs:
      - url: 'http://localhost:5001/webhook/team/payments'
```

## Service Level Objectives (SLOs)

**SLOs** define target reliability levels for your service.

### Why SLOs?

- **User-focused**: Based on user experience, not infrastructure
- **Clear targets**: Know what "good" looks like
- **Error budgets**: Balance reliability vs feature velocity
- **Prioritization**: Focus on what matters most

### The Three SLOs

Our webstore defines three critical SLOs:

#### 1. Availability SLO: 99.9%

**Definition**: 99.9% of requests should succeed (non-5xx).

**Alert rule**:
```yaml
- alert: AvailabilitySLOBreach
  expr: |
    (
      sum(rate(http_server_duration_count{http_status_code!~"5.."}[30m]))
      /
      sum(rate(http_server_duration_count[30m]))
    ) < 0.999
  for: 5m
  labels:
    severity: critical
    slo: availability
  annotations:
    summary: "Availability SLO breach"
    description: "Current availability is {{ $value | humanizePercentage }}, SLO is 99.9%"
```

**What it means**:
- 99.9% availability = 43 minutes downtime per month
- 0.1% error budget = ~300 failed requests per 300K total

**Tracking**: View in Grafana → **SLO Tracking** dashboard

#### 2. Latency SLO: P95 < 1s

**Definition**: 95% of requests should complete in under 1 second.

**Alert rule**:
```yaml
- alert: LatencySLOBreach
  expr: |
    histogram_quantile(0.95,
      sum(rate(http_server_duration_bucket[5m])) by (le)
    ) > 1
  for: 10m
  labels:
    severity: warning
    slo: latency
  annotations:
    summary: "Latency SLO breach"
    description: "P95 latency is {{ $value | humanizeDuration }}, SLO is 1s"
```

**What it means**:
- 95% of users experience fast response times
- 5% may experience slower responses (acceptable)

#### 3. Payment Success SLO: 90%

**Definition**: Payment success rate should exceed 90%.

**Alert rule**:
```yaml
- alert: PaymentSLOBreach
  expr: |
    (
      sum(rate(payments_processed_total{status="success"}[1h]))
      /
      sum(rate(payments_processed_total[1h]))
    ) < 0.90
  for: 15m
  labels:
    severity: critical
    slo: payment_success
  annotations:
    summary: "Payment success rate SLO breach"
    description: "Payment success rate is {{ $value | humanizePercentage }}, SLO is 90%"
```

**What it means**:
- 90%+ payments succeed
- 10% failure budget accounts for declined cards, insufficient funds, etc.

## Error Budget Tracking

**Error budget** is the allowed amount of unreliability before violating an SLO.

### Calculating Error Budget

For **99.9% availability SLO** over 30 days:

```
Total time:           30 days = 43,200 minutes
Allowed downtime:     0.1% × 43,200 = 43.2 minutes
Error budget:         43.2 minutes of downtime per month
```

If you have an outage:
- 10-minute outage = 23% of error budget consumed
- 43-minute outage = 100% of error budget consumed (SLO violated)

### Error Budget Policy

**When you have error budget**:
- ✅ Ship new features
- ✅ Do risky deployments
- ✅ Focus on velocity

**When error budget is exhausted**:
- 🛑 Freeze non-critical features
- 🔧 Focus on reliability improvements
- 🐛 Fix bugs and tech debt
- 📊 Improve monitoring

### Viewing Error Budgets

In Grafana, open **SLO Tracking** dashboard to see:

1. **Current SLO compliance**: Are we meeting targets?
2. **Error budget remaining**: How much budget left this month?
3. **Burn rate**: How fast are we consuming budget?
4. **Historical trends**: How has reliability changed?

**Example visualization**:
```
Availability SLO (99.9% target)
┌──────────────────────────────────┐
│ Current: 99.95% ✓                │
│ Error Budget Remaining: 87%      │
│ Burn Rate: Normal                │
│                                  │
│ ████████████████████░░░░ 87%     │
└──────────────────────────────────┘
```

## Hands-On Exercise

### Exercise 1: View Active Alerts

**Goal**: See which alerts are currently firing.

1. **Open Prometheus Alerts**: http://localhost:9090/alerts

2. **Observe alert states**:
   - 🟢 **Inactive**: Condition not met
   - 🟡 **Pending**: Condition met, waiting for `for` duration
   - 🔴 **Firing**: Alert active

3. **Inspect an alert**:
   - Click on alert name
   - View PromQL expression
   - See current value vs threshold

### Exercise 2: Trigger an Alert

**Goal**: Intentionally trigger the `HighPaymentFailureRate` alert.

**Note**: Our payment provider is configured to fail 5-15% of payments by default, so this alert should fire naturally with enough traffic.

1. **Generate traffic with payments**:
```bash
cd scripts
python3 generate-traffic.py --users 10 --duration 300
```

2. **Monitor the alert**:
   - Open Prometheus: http://localhost:9090/alerts
   - Wait 5-10 minutes
   - Watch for `HighPaymentFailureRate` to go **Pending** → **Firing**

3. **Check Alertmanager**: http://localhost:9093
   - View active alerts
   - See grouping in action
   - Check which receiver would be notified

4. **Investigate in Grafana**:
   - Open **WebStore Overview** dashboard
   - View payment failure rate by country
   - Identify which countries have highest failures

5. **Correlate with logs**:
   - Go to Explore → Loki
   - Query:
   ```logql
   {service_name="payments-service"} | json | status="failed"
   ```
   - Find specific error messages

### Exercise 3: Check SLO Compliance

**Goal**: Verify current SLO performance.

1. **Open Grafana**: http://localhost:3000

2. **Navigate to SLO Tracking dashboard**:
   - Dashboards → WebStore → SLO Tracking

3. **Review each SLO**:
   - **Availability**: Are we meeting 99.9%?
   - **Latency**: Is P95 below 1 second?
   - **Payment Success**: Above 90%?

4. **Check error budget**:
   - How much budget remains?
   - What's the burn rate?
   - When will we exhaust budget at current rate?

### Exercise 4: Simulate Service Down

**Goal**: Trigger the `ServiceDown` alert.

1. **Stop the payments service**:
```bash
docker-compose stop payments-service
```

2. **Wait 2 minutes** (alert `for` duration)

3. **Check Prometheus alerts**: http://localhost:9090/alerts
   - `ServiceDown` should be **Firing**
   - `HighErrorRate` might also fire (checkouts will fail)

4. **Observe inhibition**:
   - Go to Alertmanager: http://localhost:9093
   - Notice how related alerts might be suppressed

5. **Check the impact**:
   - Try to checkout in the frontend: http://localhost:3001
   - Should fail with error

6. **Restore the service**:
```bash
docker-compose start payments-service
```

7. **Wait for recovery**:
   - Alert should resolve within 1-2 minutes
   - Checkouts should work again

### Exercise 5: Custom Alert

**Goal**: Create your own alert rule.

1. **Edit prometheus-alerts.yml**:
```yaml
- alert: NoTrafficDetected
  expr: |
    sum(rate(http_server_duration_count[5m])) == 0
  for: 10m
  labels:
    severity: warning
    team: platform
  annotations:
    summary: "No traffic detected"
    description: "No HTTP requests received in the last 10 minutes"
```

2. **Reload Prometheus config**:
```bash
docker-compose restart prometheus
```

3. **Verify the rule loaded**:
   - Open http://localhost:9090/alerts
   - Find your new alert

4. **Trigger it**:
   - Stop traffic generation
   - Wait 10 minutes
   - Alert should fire

## Viewing Alerts

### Prometheus UI

http://localhost:9090/alerts

- View all configured alert rules
- See current state (inactive/pending/firing)
- Inspect PromQL expressions
- Check evaluation time

### Alertmanager UI

http://localhost:9093

- View active alerts
- See grouped alerts
- Check routing decisions
- Silence alerts temporarily
- View inhibition rules in action

### Grafana Dashboards

1. **Service Health Dashboard**: Shows alert status per service
2. **SLO Tracking Dashboard**: Shows SLO compliance and error budgets

## Best Practices

### Alert Design

✅ **DO**:
- Alert on user-facing symptoms (latency, errors), not causes
- Use `for` duration to prevent flapping
- Include runbook links in annotations
- Set appropriate severity levels
- Test alerts by triggering them intentionally

❌ **DON'T**:
- Alert on everything (alert fatigue)
- Use severity "critical" for non-critical issues
- Alert without clear action items
- Forget to document response procedures

### Alert Fatigue Prevention

1. **Review alerts regularly**: Remove noisy alerts
2. **Adjust thresholds**: Based on actual patterns
3. **Use proper grouping**: Reduce notification volume
4. **Implement inhibition**: Suppress redundant alerts
5. **Create runbooks**: Make response clear and quick

## Related Documentation

- **[prometheus-alerts.yml](../prometheus-alerts.yml)**: All alert rules
- **[alertmanager.yml](../alertmanager.yml)**: Routing configuration
- **[04_METRICS_AND_DASHBOARDS.md](04_METRICS_AND_DASHBOARDS.md)**: Understanding metrics used in alerts
- **[06_LOGGING_AND_CORRELATION.md](06_LOGGING_AND_CORRELATION.md)**: Investigating alerts with logs

## Summary

You learned:

- **Alert configuration** with Prometheus and Alertmanager
- **Alert categories**: Service health, resource, business, latency
- **Routing and grouping** to reduce noise
- **SLO definitions** for availability, latency, and payment success
- **Error budget tracking** to balance reliability and velocity
- **Hands-on skills** for monitoring alerts and investigating issues

**Key takeaways**:
1. Alert on symptoms (user impact), not causes
2. Define clear SLOs based on user experience
3. Track error budgets to guide feature vs reliability decisions
4. Use alert grouping and inhibition to reduce noise
5. Always include actionable information in alerts

---

**Next**: [Docker and Deployment](08_DOCKER_AND_DEPLOYMENT.md) →
