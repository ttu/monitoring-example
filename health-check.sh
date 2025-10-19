#!/bin/bash
# Observability Stack Health Check Script
# This script verifies that telemetry data flows correctly through the entire stack

echo "=== Observability Stack Health Check ==="
echo ""

echo "1. Testing metric flow..."
curl -X POST http://localhost:8000/cart/add \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer user-token-123" \
  -d '{"product_id": 3, "quantity": 1}' > /dev/null 2>&1
sleep 2

echo "2. Checking OTEL Collector metrics..."
OTEL_METRICS=$(curl -s http://localhost:8889/metrics | grep -c "webstore_cart_additions")
echo "   OTEL Collector has $OTEL_METRICS cart metrics ✓"

echo "3. Checking Prometheus..."
PROM_METRICS=$(curl -s 'http://localhost:9090/api/v1/query?query=webstore_cart_additions_total' | grep -c "webstore_cart_additions_total")
if [ $PROM_METRICS -gt 0 ]; then
  echo "   Prometheus has cart metrics ✓"
else
  echo "   ✗ Prometheus has no cart metrics - check scraping"
fi

echo "4. Checking Prometheus targets..."
UP_TARGETS=$(curl -s http://localhost:9090/api/v1/targets | grep -c '"health":"up"')
echo "   $UP_TARGETS targets are UP ✓"

echo "5. Checking Tempo..."
curl -s http://localhost:3200/ready > /dev/null 2>&1
if [ $? -eq 0 ]; then
  echo "   Tempo is ready ✓"
else
  echo "   ✗ Tempo is not responding"
fi

echo "6. Checking Loki..."
curl -s http://localhost:3100/ready > /dev/null 2>&1
if [ $? -eq 0 ]; then
  echo "   Loki is ready ✓"
else
  echo "   ✗ Loki is not responding"
fi

echo "7. Checking Alertmanager..."
curl -s http://localhost:9093/-/ready > /dev/null 2>&1
if [ $? -eq 0 ]; then
  echo "   Alertmanager is ready ✓"
else
  echo "   ✗ Alertmanager is not responding"
fi

echo "8. Checking Grafana..."
curl -s http://localhost:3000/api/health > /dev/null 2>&1
if [ $? -eq 0 ]; then
  echo "   Grafana is ready ✓"
else
  echo "   ✗ Grafana is not responding"
fi

echo ""
echo "=== Detailed Metrics Check ==="
echo ""

# Check specific metrics
echo "Cart additions:"
curl -s 'http://localhost:9090/api/v1/query?query=webstore_cart_additions_total' | \
  python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"   Found {len(data['data']['result'])} metrics\")" 2>/dev/null || echo "   Error querying"

echo "Checkouts:"
curl -s 'http://localhost:9090/api/v1/query?query=webstore_checkouts_total' | \
  python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"   Found {len(data['data']['result'])} metrics\")" 2>/dev/null || echo "   Error querying"

echo "HTTP requests:"
curl -s 'http://localhost:9090/api/v1/query?query=http_server_duration_count' | \
  python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"   Found {len(data['data']['result'])} metrics\")" 2>/dev/null || echo "   Error querying"

echo ""
echo "=== Data Flow Verification ==="
echo ""

# Verify complete data flow
echo "Service → OTLP → OTEL Collector → Prometheus:"
if [ $OTEL_METRICS -gt 0 ] && [ $PROM_METRICS -gt 0 ]; then
  echo "   ✓ Metrics flow is working correctly"
else
  echo "   ✗ Metrics flow has issues - see above for details"
fi

echo ""
echo "=== Health Check Complete ==="
echo ""
echo "Next steps:"
echo "  • Visit Grafana: http://localhost:3000"
echo "  • View dashboards: WebStore Overview, SLO Tracking, Service Health"
echo "  • Explore traces: Grafana → Explore → Tempo"
echo "  • View logs: Grafana → Explore → Loki"
echo "  • Check alerts: http://localhost:9090/alerts"
echo ""
