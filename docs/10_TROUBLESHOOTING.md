# Troubleshooting

**Reading time**: 15 minutes

Common issues, debugging techniques, and solutions for the monitoring example project.

## Table of Contents

- [Services Not Starting](#services-not-starting)
- [No Metrics, Traces, or Logs Appearing](#no-metrics-traces-or-logs-appearing)
- [High Memory Usage](#high-memory-usage)
- [Port Conflicts](#port-conflicts)
- [Database Connection Issues](#database-connection-issues)
- [Container ID Issues (macOS)](#container-id-issues-macos)
- [Data Flow Verification](#data-flow-verification)
- [Debug Commands Reference](#debug-commands-reference)

## Services Not Starting

### Symptoms

- Containers keep restarting
- `docker-compose ps` shows "Restarting" or "Exit" status
- Services fail with errors in logs

### Common Causes and Solutions

#### 1. Insufficient Docker Memory

**Symptom**:
```bash
docker-compose ps
# Shows services constantly restarting
```

**Cause**: Docker Desktop doesn't have enough memory allocated. This project requires at least 8GB.

**Solution**:
```bash
# macOS/Windows: Docker Desktop → Settings → Resources → Memory
# Set to at least 8GB (10GB recommended)

# Verify current memory limit
docker info | grep Memory
```

**After increasing memory**:
```bash
docker-compose down
docker-compose up -d
```

#### 2. PostgreSQL Not Ready

**Symptom**:
```
main-service_1    | sqlalchemy.exc.OperationalError: could not connect to server
main-service_1    | Is the server running on host "postgres"
```

**Cause**: Application services start before PostgreSQL is ready.

**Solution**: The project uses health checks, but if still failing:

```bash
# Check PostgreSQL status
docker-compose logs postgres

# Common error: data directory initialization failed
docker-compose down -v  # Removes volumes
docker-compose up -d postgres  # Start fresh

# Wait for healthy status
docker-compose ps postgres
```

#### 3. Port Already in Use

**Symptom**:
```
ERROR: for grafana  Cannot start service grafana:
Ports are not available: listen tcp 0.0.0.0:3000: bind: address already in use
```

**Cause**: Another application is using the required port.

**Solution**:

```bash
# Find what's using the port
lsof -i :3000

# Kill the process
kill -9 <PID>

# Or change the port in docker-compose.yml
services:
  grafana:
    ports:
      - "3001:3000"  # Use 3001 on host instead
```

#### 4. Build Failures

**Symptom**:
```
ERROR: Service 'main-service' failed to build
```

**Cause**: Docker build context issues, missing files, or network problems.

**Solution**:

```bash
# Check the specific error
docker-compose logs main-service

# Try rebuilding with no cache
docker-compose build --no-cache main-service

# Check if Dockerfile exists
ls -la services/main-service/Dockerfile

# Verify build context
docker-compose config | grep build
```

#### 5. Missing Environment Variables

**Symptom**:
```
KeyError: 'OTEL_EXPORTER_OTLP_ENDPOINT'
```

**Cause**: Required environment variables not set.

**Solution**:

```bash
# Check environment variables in container
docker-compose exec main-service env | grep OTEL

# Verify docker-compose.yml has correct environment section
docker-compose config | grep -A 10 main-service

# Restart with updated config
docker-compose up -d main-service
```

## No Metrics, Traces, or Logs Appearing

### Symptoms

- Grafana dashboards show "No data"
- Prometheus has no targets or targets are down
- Loki returns empty results
- Tempo searches find no traces

### Diagnostic Steps

#### Step 1: Verify Services Are Running

```bash
# Check all services
docker-compose ps

# All should show "Up" status
# If not, check logs:
docker-compose logs <service-name>
```

#### Step 2: Check OTEL Collector

The OTEL Collector is the central hub for all telemetry.

```bash
# Check if OTEL Collector is running
docker-compose ps otel-collector

# View OTEL Collector logs
docker-compose logs otel-collector

# Look for errors like:
# - "connection refused" → Backend service (Prometheus/Tempo/Loki) not ready
# - "parse error" → Configuration syntax error

# Check OTEL Collector metrics (should show data received)
curl -s http://localhost:8888/metrics | grep otelcol_receiver_accepted_spans
curl -s http://localhost:8888/metrics | grep otelcol_receiver_accepted_metric_points
```

#### Step 3: Verify Application Services Are Sending Data

```bash
# Generate test traffic
curl -X POST http://localhost:8000/cart/add \
  -H "Authorization: Bearer user-token-123" \
  -H "Content-Type: application/json" \
  -d '{"product_id": 1, "quantity": 1, "country": "US"}'

# Check application logs for OpenTelemetry initialization
docker-compose logs main-service | grep -i otel
docker-compose logs payments-service | grep -i otel

# Should see:
# "OpenTelemetry initialized"
# "TracerProvider configured"
```

#### Step 4: Check Prometheus Targets

```bash
# Open Prometheus UI
open http://localhost:9090/targets

# All targets should show "UP" status
# If DOWN:
# 1. Check service is running
# 2. Verify scrape config in prometheus.yml
# 3. Check network connectivity
```

**Common issues**:

1. **OTEL Collector target DOWN**:
```bash
# Check OTEL Collector is exposing metrics
curl http://localhost:8889/metrics

# If fails, check docker-compose.yml port mapping
```

2. **Service targets DOWN**:
```bash
# Check service health endpoint
curl http://localhost:8000/health
curl http://localhost:8081/health

# Check Prometheus scrape config
grep -A 5 "job_name: 'main-service'" prometheus.yml
```

#### Step 5: Check Tempo

```bash
# Verify Tempo is ready
curl http://localhost:3200/ready

# Check Tempo received traces
curl http://localhost:3200/api/search?tags=

# Generate trace and verify
curl http://localhost:8000/products

# Search in Grafana Explore → Tempo
```

#### Step 6: Check Loki

```bash
# Verify Loki is ready
curl http://localhost:3100/ready

# Query logs directly
curl -G -s "http://localhost:3100/loki/api/v1/query" \
  --data-urlencode 'query={service_name="main-service"}' \
  | jq

# Should return log entries
# If empty, check OTEL Collector logs export config
```

### Data Flow Verification Script

**Use the provided health check script**:

```bash
./health-check.sh
```

This script:
1. Generates test traffic
2. Checks OTEL Collector received data
3. Verifies Prometheus scraped metrics
4. Tests Tempo and Loki connectivity
5. Validates end-to-end data flow

**Expected output**:
```
=== Observability Stack Health Check ===
1. Testing metric flow... ✓
2. Checking OTEL Collector metrics... ✓
3. Checking Prometheus... ✓
4. Checking Tempo... ✓
5. Checking Loki... ✓
```

## High Memory Usage

### Symptoms

- Docker Desktop shows high memory usage
- System becomes slow
- Services are OOMKilled (Out Of Memory)

### Solutions

#### 1. Check Memory Usage

```bash
# View resource usage
docker stats

# Look for containers using excessive memory
# Typically:
# - Prometheus: 200-500MB
# - Tempo: 200-400MB
# - Grafana: 100-200MB
# - Services: 50-150MB each
```

#### 2. Reduce Retention Periods

**Prometheus** (`prometheus.yml`):
```yaml
global:
  # Reduce scrape frequency
  scrape_interval: 30s  # Instead of 15s

# In command args (docker-compose.yml)
command:
  - '--storage.tsdb.retention.time=7d'  # Instead of 15d
  - '--storage.tsdb.retention.size=5GB'  # Add size limit
```

**Tempo** (`tempo.yaml`):
```yaml
storage:
  trace:
    wal:
      # Reduce trace retention
      retention: 168h  # 7 days instead of 15
```

**Loki** (`loki.yaml`):
```yaml
limits_config:
  # Reduce log retention
  retention_period: 168h  # 7 days
```

#### 3. Limit Container Resources

Edit `docker-compose.yml`:

```yaml
services:
  prometheus:
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M
```

#### 4. Stop Unused Services

If you're not using certain features:

```bash
# Stop profiling if not needed
docker-compose stop pyroscope

# Stop cAdvisor if not monitoring containers
docker-compose stop cadvisor

# Restart needed services later
docker-compose start pyroscope
```

#### 5. Clean Up Docker Resources

```bash
# Remove stopped containers
docker container prune -f

# Remove unused images
docker image prune -a -f

# Remove unused volumes
docker volume prune -f

# Remove build cache
docker builder prune -f

# Nuclear option: clean everything (CAUTION)
docker system prune -a --volumes -f
```

## Port Conflicts

### Finding Port Conflicts

```bash
# Check what's using a specific port
lsof -i :3000
lsof -i :8000
lsof -i :9090

# On Linux
netstat -tulpn | grep :3000

# Kill the process
kill -9 <PID>
```

### Changing Ports

Edit `docker-compose.yml`:

```yaml
services:
  grafana:
    ports:
      - "3030:3000"  # Use 3030 instead of 3000

  main-service:
    ports:
      - "8080:8000"  # Use 8080 instead of 8000
```

**Remember to update**:
- Frontend environment variable `REACT_APP_API_URL`
- Any scripts or documentation referencing the ports

## Database Connection Issues

### PostgreSQL Connection Errors

**Symptom**:
```
could not connect to server: Connection refused
Is the server running on host "postgres" (172.18.0.2) and accepting
TCP/IP connections on port 5432?
```

**Solutions**:

1. **Wait for PostgreSQL to be ready**:
```bash
# Check PostgreSQL status
docker-compose logs postgres

# Wait for this message:
# "database system is ready to accept connections"

# Check health
docker-compose ps postgres
# Status should show "healthy"
```

2. **Verify connection string**:
```bash
# Check environment variable
docker-compose exec main-service env | grep DATABASE_URL

# Should be:
# postgresql://webstore:webstore123@postgres:5432/webstore

# Common mistake: using "localhost" instead of "postgres"
```

3. **Test connection manually**:
```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U webstore

# If this fails, PostgreSQL is not healthy
# Try recreating:
docker-compose down -v
docker-compose up -d postgres
```

4. **Check PostgreSQL logs for errors**:
```bash
docker-compose logs postgres | grep -i error
docker-compose logs postgres | grep -i fatal
```

### Redis Connection Errors

**Symptom**:
```
redis.exceptions.ConnectionError: Error connecting to Redis
```

**Solutions**:

```bash
# Check Redis status
docker-compose ps redis

# Test connection
docker-compose exec redis redis-cli ping
# Should return: PONG

# Check Redis logs
docker-compose logs redis

# Restart if needed
docker-compose restart redis
```

## Container ID Issues (macOS)

### Symptom

cAdvisor shows errors related to accessing container IDs or metrics.

**Error**:
```
unable to read directory /sys/fs/cgroup
```

**Cause**: macOS Docker Desktop uses a VM layer that limits cgroups access.

**Solutions**:

1. **Expected behavior**: Some cAdvisor metrics may not work on macOS. This is normal.

2. **Disable cAdvisor on macOS** (if causing issues):
```bash
# Stop cAdvisor
docker-compose stop cadvisor

# Or comment out in docker-compose.yml
```

3. **Use Linux or production environment**: cAdvisor works fully on Linux hosts.

4. **Alternative**: Use Docker Desktop's built-in metrics or Grafana's Docker integration.

## Data Flow Verification

### Complete Telemetry Pipeline Check

#### 1. Application → OTEL Collector

```bash
# Generate request
curl http://localhost:8000/products

# Check application logs (should show trace context)
docker-compose logs --tail=20 main-service

# Check OTEL Collector received data
curl -s http://localhost:8888/metrics | grep otelcol_receiver_accepted_spans
```

#### 2. OTEL Collector → Prometheus

```bash
# Check OTEL Collector is exporting to Prometheus
docker-compose logs otel-collector | grep prometheus

# Check Prometheus scraped OTEL Collector metrics
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job=="otel-collector")'

# Query metrics in Prometheus
curl -G http://localhost:9090/api/v1/query \
  --data-urlencode 'query=http_server_duration_count' | jq
```

#### 3. OTEL Collector → Tempo

```bash
# Check OTEL Collector logs for trace export
docker-compose logs otel-collector | grep -i trace

# Search for traces in Tempo
# Grafana → Explore → Tempo → Search
```

#### 4. OTEL Collector → Loki

```bash
# Check OTEL Collector logs for log export
docker-compose logs otel-collector | grep -i loki

# Query Loki directly
curl -G http://localhost:3100/loki/api/v1/query \
  --data-urlencode 'query={service_name="main-service"}' \
  --data-urlencode 'limit=10' | jq
```

### Traffic Generation for Testing

```bash
# Quick test: single request
curl http://localhost:8000/products

# Generate load
cd scripts
python3 generate-traffic.py --users 5 --duration 60

# Continuous traffic
python3 continuous-traffic.py
```

## Debug Commands Reference

### Service Status

```bash
# View all services
docker-compose ps

# Check specific service
docker-compose ps main-service

# View service details (JSON)
docker inspect monitoring-example-main-service-1 | jq

# Check health status
docker-compose ps --format json | jq '.[] | {name: .Name, health: .Health}'
```

### Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f main-service

# Last 100 lines
docker-compose logs --tail=100 main-service

# Search logs
docker-compose logs main-service | grep -i error
docker-compose logs payments-service | grep -i trace

# Save logs to file
docker-compose logs main-service > main-service.log
```

### Network Debugging

```bash
# List networks
docker network ls

# Inspect network
docker network inspect monitoring-example_default

# Check DNS resolution
docker-compose exec main-service ping postgres
docker-compose exec main-service nslookup payments-service

# Test connectivity
docker-compose exec main-service curl http://payments-service:8081/health

# Check port accessibility
docker-compose exec main-service nc -zv postgres 5432
```

### Container Shell Access

```bash
# Bash shell
docker-compose exec main-service bash

# If bash not available (Alpine)
docker-compose exec payments-service sh

# Run as root
docker-compose exec -u root main-service bash

# Execute single command
docker-compose exec main-service ls -la /app
docker-compose exec postgres psql -U webstore -c "SELECT version();"
```

### Resource Monitoring

```bash
# Real-time stats
docker stats

# Specific container
docker stats monitoring-example-main-service-1

# CPU and memory limits
docker inspect monitoring-example-main-service-1 | jq '.[0].HostConfig.Memory'
docker inspect monitoring-example-main-service-1 | jq '.[0].HostConfig.NanoCpus'
```

### Configuration Validation

```bash
# Validate docker-compose.yml syntax
docker-compose config

# Show resolved configuration
docker-compose config --services
docker-compose config --volumes

# Check environment variables
docker-compose config | grep -A 10 environment

# Validate port mappings
docker-compose config | grep -A 2 ports
```

### Cleanup Commands

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (deletes data!)
docker-compose down -v

# Restart specific service
docker-compose restart main-service

# Force recreate service
docker-compose up -d --force-recreate main-service

# Rebuild and restart
docker-compose up -d --build main-service
```

## Common Error Messages

### 1. "bind: address already in use"

**Solution**: Port conflict, see [Port Conflicts](#port-conflicts)

### 2. "no such file or directory"

**Cause**: Missing configuration file or incorrect volume mount.

**Solution**:
```bash
# Check file exists
ls -la prometheus.yml
ls -la otel-collector-config.yaml

# Verify volume mounts in docker-compose.yml
docker-compose config | grep -A 5 volumes
```

### 3. "connection refused"

**Cause**: Service not running or not ready.

**Solution**:
```bash
# Check service status
docker-compose ps

# Check if service is listening on expected port
docker-compose exec main-service netstat -tlnp | grep 8000

# Wait for health check
docker-compose ps | grep -i health
```

### 4. "context deadline exceeded"

**Cause**: Timeout connecting to service.

**Solution**:
```bash
# Check service logs
docker-compose logs <service>

# Increase timeout in application config
# Check network connectivity
docker-compose exec main-service ping payments-service
```

### 5. "OOMKilled"

**Cause**: Container ran out of memory.

**Solution**: See [High Memory Usage](#high-memory-usage)

### 6. "Permission denied"

**Cause**: Volume mount permission issues.

**Solution**:
```bash
# Check file permissions
ls -la prometheus.yml

# Fix permissions
chmod 644 prometheus.yml

# For volumes, run container as root temporarily
docker-compose exec -u root main-service chown -R appuser:appuser /app
```

## Getting Help

If you're still stuck after trying these solutions:

1. **Check the logs**: Most issues are visible in logs
   ```bash
   docker-compose logs -f
   ```

2. **Verify configuration**:
   ```bash
   docker-compose config
   ```

3. **Run health check script**:
   ```bash
   ./health-check.sh
   ```

4. **Check resource availability**:
   ```bash
   docker stats
   docker info
   ```

5. **Review related documentation**:
   - [Getting Started](01_GETTING_STARTED.md) - Setup guide
   - [Architecture Overview](02_ARCHITECTURE_OVERVIEW.md) - System design
   - [Docker and Deployment](08_DOCKER_AND_DEPLOYMENT.md) - Container details

6. **Start fresh**:
   ```bash
   # Clean slate (WARNING: deletes all data)
   docker-compose down -v
   docker system prune -a -f
   docker-compose up -d
   ```

## Quick Diagnostics Checklist

Run through this checklist when encountering issues:

- [ ] Docker Desktop has at least 8GB RAM allocated
- [ ] All services show "Up" status: `docker-compose ps`
- [ ] No port conflicts: `lsof -i :3000` (check each port)
- [ ] PostgreSQL is healthy: `docker-compose ps postgres`
- [ ] OTEL Collector is running: `curl http://localhost:8888/metrics`
- [ ] Prometheus targets are UP: http://localhost:9090/targets
- [ ] Traffic has been generated: `curl http://localhost:8000/products`
- [ ] Logs show no errors: `docker-compose logs | grep -i error`
- [ ] Configuration is valid: `docker-compose config`
- [ ] Enough disk space: `df -h`

## Summary

You learned:

- **Common startup issues** and how to fix them
- **Data flow verification** from application to observability backend
- **Memory management** and resource optimization
- **Debugging commands** for logs, networking, and configuration
- **Quick diagnostics** to identify problems fast

**Key takeaways**:
1. Always check logs first: `docker-compose logs <service>`
2. Verify data flow: Application → OTEL Collector → Backends
3. Use health checks to ensure services are ready
4. Monitor resource usage to prevent OOM issues
5. Run `./health-check.sh` to verify end-to-end telemetry

**Most issues are resolved by**:
- Increasing Docker memory allocation
- Waiting for services to be healthy
- Checking logs for specific errors
- Verifying configuration files

---

**Congratulations!** You've completed all the documentation guides. Return to [Getting Started](01_GETTING_STARTED.md) or explore specific topics as needed.
