#!/bin/bash

# Enhanced Health Check with Dependency Tracking
# Checks all services and their dependencies in correct order
# Returns: 0 if all healthy, 1 if any critical component unhealthy

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
TIMEOUT=5
VERBOSE=true
JSON_OUTPUT=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -q|--quiet)
            VERBOSE=false
            shift
            ;;
        -j|--json)
            JSON_OUTPUT=true
            VERBOSE=false
            shift
            ;;
        -t|--timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        *)
            echo "Usage: $0 [-q|--quiet] [-j|--json] [-t|--timeout SECONDS]"
            exit 1
            ;;
    esac
done

# Health check results
declare -A STATUS
declare -A RESPONSE_TIME
declare -A ERROR_MSG
OVERALL_HEALTHY=true
START_TIME=$(date +%s)

# Function to check HTTP endpoint with detailed response
check_http() {
    local name=$1
    local url=$2
    local expected_status=${3:-200}
    local critical=${4:-true}

    if $VERBOSE; then
        echo -n "  Checking $name... "
    fi

    local start=$(date +%s%3N)
    response=$(curl -s -w "\n%{http_code}" --max-time $TIMEOUT "$url" 2>&1)
    local end=$(date +%s%3N)
    local duration=$((end - start))

    if [ $? -ne 0 ]; then
        STATUS[$name]="unhealthy"
        ERROR_MSG[$name]="Connection failed"
        RESPONSE_TIME[$name]=0
        if [ "$critical" = true ]; then
            OVERALL_HEALTHY=false
        fi
        if $VERBOSE; then
            echo -e "${RED}✗ FAILED${NC} (timeout or connection error)"
        fi
        return 1
    fi

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    RESPONSE_TIME[$name]=$duration

    if [ "$http_code" = "$expected_status" ]; then
        STATUS[$name]="healthy"
        if $VERBOSE; then
            echo -e "${GREEN}✓ OK${NC} (${duration}ms)"
        fi
        return 0
    else
        STATUS[$name]="unhealthy"
        ERROR_MSG[$name]="HTTP $http_code"
        if [ "$critical" = true ]; then
            OVERALL_HEALTHY=false
        fi
        if $VERBOSE; then
            echo -e "${RED}✗ FAILED${NC} (HTTP $http_code)"
        fi
        return 1
    fi
}

# Function to check TCP port
check_port() {
    local name=$1
    local host=$2
    local port=$3
    local critical=${4:-true}

    if $VERBOSE; then
        echo -n "  Checking $name ($host:$port)... "
    fi

    local start=$(date +%s%3N)
    if timeout $TIMEOUT bash -c "cat < /dev/null > /dev/tcp/$host/$port" 2>/dev/null; then
        local end=$(date +%s%3N)
        local duration=$((end - start))
        STATUS[$name]="healthy"
        RESPONSE_TIME[$name]=$duration
        if $VERBOSE; then
            echo -e "${GREEN}✓ OK${NC} (${duration}ms)"
        fi
        return 0
    else
        STATUS[$name]="unhealthy"
        ERROR_MSG[$name]="Port not reachable"
        RESPONSE_TIME[$name]=0
        if [ "$critical" = true ]; then
            OVERALL_HEALTHY=false
        fi
        if $VERBOSE; then
            echo -e "${RED}✗ FAILED${NC} (port not reachable)"
        fi
        return 1
    fi
}

# Print header
if $VERBOSE; then
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  WebStore Health Check with Dependencies${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
fi

# Layer 1: Core Infrastructure (Critical)
if $VERBOSE; then
    echo -e "${BLUE}[Layer 1]${NC} Core Infrastructure (Critical):"
fi

check_port "PostgreSQL" "localhost" "5432" true
check_port "Redis" "localhost" "6379" true

if $VERBOSE; then
    echo ""
fi

# Layer 2: Observability Stack (Non-critical for app, critical for monitoring)
if $VERBOSE; then
    echo -e "${BLUE}[Layer 2]${NC} Observability Infrastructure:"
fi

check_http "OTEL-Collector" "http://localhost:13133" 200 false
check_port "Prometheus" "localhost" "9090" false
check_port "Tempo" "localhost" "3200" false
check_port "Loki" "localhost" "3100" false
check_http "Alertmanager" "http://localhost:9093/-/healthy" 200 false
check_port "Grafana" "localhost" "3000" false

if $VERBOSE; then
    echo ""
fi

# Layer 3: Core Application Services (Dependent on Layer 1)
if $VERBOSE; then
    echo -e "${BLUE}[Layer 3]${NC} Core Application Services:"
    if [ "${STATUS[PostgreSQL]}" != "healthy" ] || [ "${STATUS[Redis]}" != "healthy" ]; then
        echo -e "  ${YELLOW}⚠${NC} Warning: Core infrastructure unhealthy, app services may fail"
    fi
fi

check_http "main-service" "http://localhost:8000/health" 200 true
check_http "payments-service" "http://localhost:8081/health" 200 true
check_http "promotions-service" "http://localhost:8082/health" 200 false

if $VERBOSE; then
    echo ""
fi

# Layer 4: External Services (Dependent on Layer 3)
if $VERBOSE; then
    echo -e "${BLUE}[Layer 4]${NC} External Integration Services:"
fi

check_http "payment-provider" "http://localhost:3001/health" 200 false
check_http "crm-system" "http://localhost:3002/health" 200 false
check_http "inventory-system" "http://localhost:3003/health" 200 false

if $VERBOSE; then
    echo ""
fi

# Layer 5: Frontend (Dependent on all above)
if $VERBOSE; then
    echo -e "${BLUE}[Layer 5]${NC} Frontend:"
fi

check_port "frontend" "localhost" "3001" false

# Calculate total time
END_TIME=$(date +%s)
TOTAL_TIME=$((END_TIME - START_TIME))

# Generate output
if $JSON_OUTPUT; then
    echo "{"
    echo "  \"overall_status\": \"$([ "$OVERALL_HEALTHY" = true ] && echo "healthy" || echo "unhealthy")\","
    echo "  \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
    echo "  \"duration_seconds\": $TOTAL_TIME,"
    echo "  \"services\": {"

    first=true
    for service in "${!STATUS[@]}"; do
        if [ "$first" = true ]; then
            first=false
        else
            echo ","
        fi
        error="${ERROR_MSG[$service]:-none}"
        response_time="${RESPONSE_TIME[$service]:-0}"
        echo -n "    \"$service\": {\"status\": \"${STATUS[$service]}\", \"response_time_ms\": $response_time, \"error\": \"$error\"}"
    done

    echo ""
    echo "  },"
    echo "  \"dependency_graph\": {"
    echo "    \"layer1_infrastructure\": [\"PostgreSQL\", \"Redis\"],"
    echo "    \"layer2_observability\": [\"OTEL-Collector\", \"Prometheus\", \"Tempo\", \"Loki\", \"Alertmanager\", \"Grafana\"],"
    echo "    \"layer3_core_services\": {\"services\": [\"main-service\", \"payments-service\", \"promotions-service\"], \"depends_on\": [\"PostgreSQL\", \"Redis\", \"OTEL-Collector\"]},"
    echo "    \"layer4_external\": {\"services\": [\"payment-provider\", \"crm-system\", \"inventory-system\"], \"depends_on\": [\"main-service\", \"payments-service\"]},"
    echo "    \"layer5_frontend\": {\"services\": [\"frontend\"], \"depends_on\": [\"main-service\"]}"
    echo "  }"
    echo "}"
else
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Dependency Summary:${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    # Layer 1
    echo -e "${BLUE}Layer 1: Infrastructure${NC}"
    echo "  PostgreSQL → [main-service]"
    echo "  Redis → [main-service]"
    echo ""

    # Layer 2
    echo -e "${BLUE}Layer 2: Observability${NC}"
    echo "  OTEL-Collector → [Prometheus, Tempo, Loki]"
    echo "  Prometheus → [Grafana, Alertmanager]"
    echo ""

    # Layer 3
    echo -e "${BLUE}Layer 3: Core Services${NC}"
    echo "  main-service → [payments-service, promotions-service, external services]"
    echo "  payments-service → [payment-provider]"
    echo ""

    # Layer 4
    echo -e "${BLUE}Layer 4: External Services${NC}"
    echo "  payment-provider → [payments-service]"
    echo "  crm-system → [main-service]"
    echo "  inventory-system → [main-service]"
    echo ""

    # Layer 5
    echo -e "${BLUE}Layer 5: Frontend${NC}"
    echo "  frontend → [main-service]"
    echo ""

    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Health Summary:${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    healthy_count=0
    unhealthy_count=0
    critical_unhealthy=0

    for service in "${!STATUS[@]}"; do
        if [ "${STATUS[$service]}" = "healthy" ]; then
            ((healthy_count++))
        else
            ((unhealthy_count++))
            # Check if critical service
            if [[ "$service" =~ ^(PostgreSQL|Redis|main-service|payments-service)$ ]]; then
                ((critical_unhealthy++))
            fi
        fi
    done

    echo "Healthy: $healthy_count"
    echo "Unhealthy: $unhealthy_count"
    if [ $critical_unhealthy -gt 0 ]; then
        echo -e "Critical Unhealthy: ${RED}$critical_unhealthy${NC}"
    fi
    echo ""
    echo "Total check time: ${TOTAL_TIME}s"
    echo ""

    if [ "$OVERALL_HEALTHY" = true ]; then
        echo -e "${GREEN}═══════════════════════════════════════${NC}"
        echo -e "${GREEN}Overall Status: ✓ HEALTHY${NC}"
        echo -e "${GREEN}═══════════════════════════════════════${NC}"
    else
        echo -e "${RED}═══════════════════════════════════════${NC}"
        echo -e "${RED}Overall Status: ✗ UNHEALTHY${NC}"
        echo -e "${RED}═══════════════════════════════════════${NC}"
        echo ""
        echo -e "${YELLOW}Unhealthy services:${NC}"
        for service in "${!STATUS[@]}"; do
            if [ "${STATUS[$service]}" != "healthy" ]; then
                echo -e "  ${RED}✗${NC} $service: ${ERROR_MSG[$service]}"
            fi
        done
    fi
fi

echo ""

# Exit with appropriate code
if [ "$OVERALL_HEALTHY" = true ]; then
    exit 0
else
    exit 1
fi
