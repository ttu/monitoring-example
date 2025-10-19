# WebStore Monitoring Example

A comprehensive demonstration of modern observability practices using OpenTelemetry, Prometheus, Grafana, and the complete Grafana Stack (Tempo, Loki, Pyroscope).

## What Is This?

A **realistic e-commerce demo application** demonstrating distributed observability across a polyglot microservices architecture:

- **4 languages**: Python (FastAPI), Go, C# (.NET), Node.js, React
- **Full observability stack**: Metrics, traces, logs, alerts, profiling
- **Real-world patterns**: Distributed tracing, SLOs, error budgets, rate limiting
- **Business analytics**: Funnel analysis, customer segmentation

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  React Frontend (Grafana Faro - RUM)                    │
└────────────────────┬────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │   Main Service        │  FastAPI (Python)
         │   + PostgreSQL/Redis  │
         └───────┬───────────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
┌───▼────┐  ┌───▼────┐  ┌───▼────┐
│Payments│  │Promotio│  │External│  Go / .NET / Node.js
│Service │  │ns Svc  │  │Services│
└────────┘  └────────┘  └────────┘
                 │
         ┌───────▼────────┐
         │ OTLP Collector │
         └───┬────┬───┬───┘
             │    │   │
       ┌─────┘    │   └─────┐
       │          │         │
   ┌───▼──┐  ┌───▼───┐  ┌──▼──┐
   │Prom  │  │Tempo  │  │Loki │
   │etheus│  │(traces│  │(logs│
   └───┬──┘  └───────┘  └─────┘
       │
   ┌───▼────────┐
   │  Grafana   │  Dashboards + Explore
   └────────────┘
```

**Services**: 7 application services + 8 infrastructure services
**Observability**: OTLP push pattern (no Prometheus scraping of apps)
**Documentation**: Comprehensive guides in [docs/](docs/)

## 🚀 Quick Start (5 minutes)

### Prerequisites
- Docker Desktop (8GB+ RAM)
- Python 3.8+

### Start Everything

```bash
# 1. Start all services
docker-compose up -d

# 2. Wait 2-3 minutes for initialization
docker-compose ps

# 3. Generate traffic
cd scripts
python3 generate-traffic.py --users 5 --duration 60
```

### Access Points

| Service | URL | Purpose |
|---------|-----|---------|
| 🛒 **WebStore** | http://localhost:3001 | Try the application |
| 📊 **Grafana** | http://localhost:3000 | Dashboards & Explore |
| 📈 **Prometheus** | http://localhost:9090 | Metrics & Alerts |
| 🔍 **API Docs** | http://localhost:8000/docs | Swagger UI |

**Demo Tokens**: `user-token-123`, `admin-token-456`, `test-token-789`

## 🎯 Key Features

### Observability Capabilities

✅ **Distributed Tracing**: Full trace propagation across all services (Tempo)
✅ **Metrics**: Business + infrastructure metrics (Prometheus)
✅ **Logs**: Structured logging with trace correlation (Loki)
✅ **Exemplars**: Click metric spikes → jump to example traces
✅ **Profiling**: Continuous CPU/memory profiling (Pyroscope)
✅ **Alerting**: SLO-based alerts with error budgets (Alertmanager)
✅ **RUM**: Real User Monitoring for frontend (Grafana Faro)

### Business Analytics

✅ **Funnel Analysis**: Track Browse → View → Cart → Checkout conversion
✅ **Customer Segmentation**: Behavioral tracking (new, returning, vip, at_risk, churned)
✅ **Geographic Monitoring**: Country-specific metrics for 7 countries
✅ **Security Monitoring**: Redis-backed rate limiting, suspicious activity detection

### Technology Demonstration

✅ **Auto-instrumentation**: OpenTelemetry for Python, Go, C#, Node.js
✅ **OTLP Push Pattern**: All telemetry via OpenTelemetry Protocol
✅ **Multi-language**: 4 backend languages + React frontend
✅ **Realistic Failures**: External services simulate 5-15% failure rates
✅ **Production Patterns**: Health checks, graceful degradation, circuit breakers

## 📚 Documentation

**Start here**: [Learning Path](docs/00_LEARNING_PATH.md) - Recommended reading order

### Core Guides (Read in order)
1. [Getting Started](docs/01_GETTING_STARTED.md) - Setup & first steps
2. [Architecture Overview](docs/02_ARCHITECTURE_OVERVIEW.md) - System design & data flow
3. [OpenTelemetry Instrumentation](docs/03_OPENTELEMETRY_INSTRUMENTATION.md) - How instrumentation works
4. [Metrics and Dashboards](docs/04_METRICS_AND_DASHBOARDS.md) - Prometheus & Grafana
5. [Distributed Tracing](docs/05_DISTRIBUTED_TRACING.md) - Using Tempo
6. [Exemplars](docs/06_EXEMPLARS.md) - Metrics ↔ traces correlation
7. [Logging and Correlation](docs/07_LOGGING_AND_CORRELATION.md) - Structured logs
8. [Alerting and SLOs](docs/08_ALERTING_AND_SLOS.md) - Production alerts
9. [Docker and Deployment](docs/09_DOCKER_AND_DEPLOYMENT.md) - Container architecture
10. [Troubleshooting](docs/10_TROUBLESHOOTING.md) - Common issues

### Reference Documentation
- [ANALYTICS_FEATURES.md](ANALYTICS_FEATURES.md) - Funnel analysis & customer segmentation
- [HEALTH_CHECK_ARCHITECTURE.md](docs/HEALTH_CHECK_ARCHITECTURE.md) - Dependency tracking
- [LOGGING_STANDARDS.md](docs/LOGGING_STANDARDS.md) - Logging best practices
- [TRACE_SAMPLING_STRATEGY.md](docs/TRACE_SAMPLING_STRATEGY.md) - Sampling policies

## 🔧 Common Commands

```bash
# Health check
./health-check.sh

# View logs
docker-compose logs -f main-service

# Rebuild service
docker-compose up -d --build main-service

# Stop everything
docker-compose down

# Clean restart (removes data)
docker-compose down -v && docker-compose up -d
```

## 🌍 Supported Countries

The application simulates users from 7 countries with different behavior patterns:
- 🇺🇸 US (low payment failure rate)
- 🇬🇧 UK, 🇩🇪 DE, 🇫🇷 FR (medium)
- 🇯🇵 JP, 🇧🇷 BR, 🇮🇳 IN (higher payment failure rates)

## 📊 Grafana Dashboards

Open Grafana at http://localhost:3000 → **Dashboards** → **WebStore** folder:

1. **WebStore Overview**: Business metrics, conversion rates, funnel analysis
2. **SLO Tracking**: Availability, latency, payment success with error budgets
3. **Service Health**: Request rates, latencies, error rates, dependencies
4. **System Metrics**: CPU, memory, network per container (macOS: requires container ID updates)
5. **Logs Explorer**: Structured log analysis with trace correlation
6. **HTTP Metrics**: Detailed HTTP endpoint performance

## 🎓 What You'll Learn

After completing this project, you will understand:

- **OpenTelemetry**: Auto-instrumentation in multiple languages
- **OTLP**: Push-based telemetry collection vs pull-based scraping
- **Distributed Tracing**: Context propagation across microservices
- **Metrics**: Business vs infrastructure metrics, PromQL queries
- **Logs**: Structured logging with trace correlation, LogQL
- **Exemplars**: Linking metric spikes to example traces
- **SLOs**: Service Level Objectives and error budget tracking
- **Alerts**: Multi-level alerting strategies
- **Grafana**: Building dashboards and using Explore
- **Production Patterns**: Rate limiting, health checks, graceful degradation

## 🛠️ Development

### VS Code Workspace

```bash
# Open multi-language workspace
code monitoring-example.code-workspace
```

Includes configurations for Python, Go, C#, TypeScript with language servers and debug configurations.

### Traffic Generation

```bash
# Python script (recommended)
cd scripts
python3 generate-traffic.py --users 10 --duration 120

# Shell script
./scripts/generate-traffic.sh 10 120

# Continuous traffic
python3 scripts/continuous-traffic.py
```

## 🐛 Troubleshooting

### Quick Diagnostics

```bash
# Check service health
./health-check.sh

# Verify metrics flow
curl -s http://localhost:8889/metrics | grep webstore

# Check Prometheus targets
curl -s http://localhost:9090/api/v1/targets | grep -A 5 "otel-collector"

# Query for traces
# Grafana → Explore → Tempo → Search
```

### Common Issues

**No metrics in Grafana**: Generate traffic, wait 60 seconds for scraping
**Traces missing**: Check OTEL Collector logs: `docker-compose logs otel-collector`
**Services not starting**: Check logs: `docker-compose logs <service-name>`
**Port conflicts**: Change ports in `docker-compose.yml`

See [Troubleshooting Guide](docs/10_TROUBLESHOOTING.md) for detailed solutions.

## 📈 Monitoring Best Practices

This project demonstrates:

1. ✅ **Auto-instrumentation** - Minimal code changes
2. ✅ **OTLP Push Pattern** - Vendor-neutral telemetry
3. ✅ **Trace Context Propagation** - W3C standard
4. ✅ **Structured Logging** - JSON with trace correlation
5. ✅ **Exemplars** - Metrics-to-traces linking
6. ✅ **Service Graphs** - Automatic dependency mapping
7. ✅ **SLO-based Alerting** - Error budgets prevent alert fatigue
8. ✅ **Multi-level Monitoring** - Business + service + infrastructure
9. ✅ **Realistic External Services** - Third parties don't expose monitoring
10. ✅ **Production Patterns** - Rate limiting, health checks, profiling

## 📝 License

MIT License - Educational demonstration project

## 🤝 Contributing

This is an example project for learning. Feel free to fork and modify!

---

**Tech Stack**: OpenTelemetry • Prometheus • Grafana • Tempo • Loki • Pyroscope • FastAPI • Go • .NET • Node.js • React

**Need help?** Start with the [Learning Path](docs/00_LEARNING_PATH.md) or check [Troubleshooting](docs/10_TROUBLESHOOTING.md)
