# WebStore Monitoring Example - Learning Path

**Welcome!** This guide will help you learn modern observability practices through a hands-on e-commerce application.

## Overview

This project demonstrates production-ready observability across a polyglot microservices architecture using:
- **OpenTelemetry** for instrumentation (Python, Go, C#, Node.js, React)
- **OTLP** (OpenTelemetry Protocol) for transmitting telemetry data
- **Grafana Stack** for visualization (Grafana, Tempo, Loki, Prometheus)
- **Real-world patterns** including distributed tracing, metrics, logs, alerts, and SLOs

## Recommended Reading Order

Follow this numbered sequence for the best learning experience:

### 📚 Phase 1: Getting Started (30 minutes)

**1. [Getting Started](01_GETTING_STARTED.md)** ⭐ **START HERE**
- Quick setup in 5 minutes
- Run the application
- Generate traffic
- Explore Grafana dashboards
- **Outcome**: Working observability stack

**2. [Architecture Overview](02_ARCHITECTURE_OVERVIEW.md)**
- Understand service communication
- Learn the observability pipeline
- See how data flows through the system
- **Outcome**: Mental model of the architecture

### 🔧 Phase 2: Core Concepts (1-2 hours)

**3. [OpenTelemetry Instrumentation](03_OPENTELEMETRY_INSTRUMENTATION.md)**
- Learn auto-instrumentation vs manual
- See language-specific implementations
- Understand OTLP push pattern
- **Outcome**: Know how to instrument services

**4. [Metrics and Dashboards](04_METRICS_AND_DASHBOARDS.md)**
- Business vs infrastructure metrics
- Prometheus queries (PromQL)
- Dashboard design patterns
- **Outcome**: Create and query metrics

**5. [Distributed Tracing](05_DISTRIBUTED_TRACING.md)**
- Trace context propagation
- Value-based sampling
- Using Tempo in Grafana
- **Outcome**: Debug with traces

**6. [Exemplars: Linking Metrics to Traces](06_EXEMPLARS.md)** 🆕
- Click metric spikes to jump to example traces
- Automatic metrics ↔ traces correlation
- Investigate root causes instantly
- **Outcome**: Jump from metrics to traces in one click

**7. [Logging and Correlation](07_LOGGING_AND_CORRELATION.md)**
- Structured logging standards
- Trace-log correlation
- LogQL queries in Loki
- **Outcome**: Correlate logs with traces

### 🚨 Phase 3: Production Readiness (1-2 hours)

**8. [Alerting and SLOs](08_ALERTING_AND_SLOS.md)**
- Alert rule design
- SLO/SLI definitions
- Error budget tracking
- Alertmanager routing
- **Outcome**: Set up production alerts

**9. [Docker and Deployment](09_DOCKER_AND_DEPLOYMENT.md)**
- Container architecture
- Multi-stage builds
- Service configuration
- Health checks
- **Outcome**: Deploy observability stack

**10. [Troubleshooting Guide](10_TROUBLESHOOTING.md)**
- Common issues and solutions
- Debugging techniques
- Performance tuning
- **Outcome**: Fix problems independently

### 📖 Phase 4: Deep Dives (Reference)

**Reference Documentation**:
- [ARCHITECTURE.md](ARCHITECTURE.md) - Detailed technical architecture
- [06_EXEMPLARS.md](06_EXEMPLARS.md) - Metrics to traces correlation 🆕
- [ANALYTICS_FEATURES.md](../ANALYTICS_FEATURES.md) - Funnel analysis & customer segmentation 🆕
- [LOGGING_STANDARDS.md](LOGGING_STANDARDS.md) - Logging best practices
- [TRACE_SAMPLING_STRATEGY.md](TRACE_SAMPLING_STRATEGY.md) - Sampling policies
- [HEALTH_CHECK_ARCHITECTURE.md](HEALTH_CHECK_ARCHITECTURE.md) - Dependency tracking
- [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) - Complete feature list
- [REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md) - Evolution history

## Learning Modes

### 🎯 Quick Start (30 minutes)
Focus on essentials to get running:
1. Getting Started
2. Architecture Overview
3. Generate traffic and explore dashboards

### 🔬 Hands-On Developer (3-4 hours)
Complete walkthrough of all concepts:
1-9 in order, experimenting with each topic

### 📚 Deep Study (1-2 days)
Thorough understanding including reference docs:
- All numbered guides (1-9)
- All reference documentation
- Modify code and observe changes
- Create custom dashboards

## Prerequisites by Phase

### Phase 1: Getting Started
- Docker Desktop (8GB+ RAM)
- Python 3.8+
- Basic terminal/command line skills

### Phase 2: Core Concepts
- Understanding of HTTP/REST APIs
- Basic knowledge of metrics (counters, histograms)
- Familiarity with any programming language

### Phase 3: Production Readiness
- Understanding of alerting concepts
- Basic Prometheus/PromQL knowledge
- Docker basics

### Phase 4: Deep Dives
- Advanced programming skills
- Multi-language development experience
- Production operations experience

## Skill Level Paths

### Beginner (New to Observability)
**Goal**: Understand what observability is and see it in action

**Path**:
1. Getting Started - Run the app, see metrics/traces/logs
2. Architecture Overview - Understand what each component does
3. Metrics and Dashboards - Learn to read dashboards
4. Distributed Tracing - Understand how requests flow
5. Troubleshooting Guide - Learn common fixes

**Skip**: Deep technical details, focus on concepts

### Intermediate (Some Observability Experience)
**Goal**: Learn OpenTelemetry and modern observability stack

**Path**:
1-9 in order
- Focus on OpenTelemetry instrumentation
- Study the OTLP push pattern
- Understand trace sampling strategies
- Learn SLO/error budget calculations

**Deep Dive**: Logging Standards, Trace Sampling Strategy

### Advanced (Observability Expert)
**Goal**: Adopt best practices and advanced patterns

**Path**:
1. Quick scan of Getting Started
2. Architecture Overview - Study the OTLP push pattern
3. OpenTelemetry Instrumentation - Multi-language patterns
4. Trace Sampling Strategy - Value-based policies
5. Alerting and SLOs - Advanced alert routing

**Deep Dive**: All reference documentation

## Hands-On Exercises

### Exercise 1: Generate and Observe
1. Start the stack
2. Generate traffic
3. Find a checkout trace in Tempo
4. Identify the slowest span
5. Find related logs in Loki

### Exercise 2: Follow a Failed Payment
1. Generate traffic from Brazil (high failure rate)
2. Find a failed payment in metrics
3. Jump to the trace via exemplar
4. Find the error log via trace_id
5. Identify root cause

### Exercise 3: Analyze Funnel Conversion
1. Open Grafana → WebStore Overview dashboard
2. Find the funnel analysis panel
3. Compare conversion rates by country
4. Query cart abandonment rate: `1 - (sum(rate(webstore_funnel_stage_total{stage="checkout_complete"}[5m])) / sum(rate(webstore_funnel_stage_total{stage="add_to_cart"}[5m])))`
5. Identify which stage has highest drop-off

### Exercise 3b: Customer Segmentation Analysis
1. Query customer distribution: `sum(rate(webstore_customer_segment_total[5m])) by (segment)`
2. Compare VIP vs new customer conversion rates
3. Identify at-risk customers: `sum(rate(webstore_customer_segment_total{segment="at_risk"}[5m])) by (action)`
4. Create alert for declining VIP engagement

### Exercise 4: Trigger an Alert
1. Stop the main-service: `docker-compose stop main-service`
2. Wait 2 minutes
3. Check Prometheus alerts: http://localhost:9090/alerts
4. Verify ServiceDown alert is firing
5. Check Alertmanager: http://localhost:9093

### Exercise 5: Modify Instrumentation
1. Edit `services/main-service/main.py`
2. Add a custom metric for product views
3. Rebuild: `docker-compose up -d --build main-service`
4. View metric in Prometheus
5. Add to Grafana dashboard

## Quick Reference

### Essential URLs
- **Application**: http://localhost:3001
- **Grafana**: http://localhost:3000 (dashboards, explore)
- **Prometheus**: http://localhost:9090 (metrics, alerts)
- **Main API**: http://localhost:8000/docs (Swagger UI)

### Essential Commands
```bash
# Start
docker-compose up -d

# Generate traffic
cd scripts && python3 generate-traffic.py --users 5 --duration 60

# View logs
docker-compose logs -f main-service

# Health check
./health-check-dependencies.sh

# Stop
docker-compose down
```

### Demo Tokens
- `user-token-123`
- `admin-token-456`
- `test-token-789`

## Getting Help

**Stuck? Check these resources**:
1. [Troubleshooting Guide](09_TROUBLESHOOTING.md) - Common issues
2. Service logs: `docker-compose logs <service>`
3. Health check: `./health-check-dependencies.sh`
4. Main README: [../README.md](../README.md)

## What You'll Learn

After completing this learning path, you will:

✅ **Understand** modern observability architecture
✅ **Instrument** applications with OpenTelemetry in multiple languages
✅ **Collect** metrics, traces, and logs using OTLP
✅ **Visualize** data in Grafana dashboards
✅ **Query** Prometheus (PromQL) and Loki (LogQL)
✅ **Trace** requests across distributed systems
✅ **Correlate** metrics, logs, and traces
✅ **Define** SLOs and track error budgets
✅ **Create** meaningful alerts
✅ **Debug** production issues with distributed tracing
✅ **Analyze** funnel conversion and customer behavior
✅ **Deploy** a complete observability stack

---

**Ready to begin?** → Start with [Getting Started](01_GETTING_STARTED.md) ⭐
