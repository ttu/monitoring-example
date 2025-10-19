# Architecture Overview

**Reading time**: 15 minutes

This guide explains the WebStore architecture, service communication patterns, and observability pipeline.

## Table of Contents

- [System Architecture](#system-architecture)
- [Service Communication Flow](#service-communication-flow)
- [Observability Pipeline](#observability-pipeline)
- [Security Architecture](#security-architecture)
- [Analytics Features](#analytics-features)
- [User Journey: E-commerce Flow](#user-journey-e-commerce-flow)
- [Data Flow: Complete Checkout Process](#data-flow-complete-checkout-process)
- [Ports and Endpoints](#ports-and-endpoints)

## System Architecture

WebStore is a polyglot microservices e-commerce application that evolved from a monolith to demonstrate modern observability practices.

### Evolution Journey

**Phase 1: Monolithic Application**
- Single FastAPI service handling all e-commerce functionality
- Direct database and Redis access
- All business logic in one codebase

**Phase 2: Payment Service Extraction** (Go)
- Isolated payment processing for PCI compliance
- Independent scaling for payment workloads
- Separate deployment lifecycle

**Phase 3: Promotions Service Addition** (C#/.NET)
- Greenfield service for promotional features
- Demonstrates polyglot architecture
- A/B testing capabilities

**Current State**: Distributed microservices with full observability

### High-Level Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Users (Global)                          │
│                  🇺🇸 🇬🇧 🇩🇪 🇫🇷 🇯🇵 🇧🇷 🇮🇳                   │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │  React Frontend   │
                    │  (Grafana Faro)   │
                    │   Port: 3001      │
                    └─────────┬─────────┘
                              │
┌──────────────────────────────┼────────────────────────────────┐
│ OUR SERVICES                 │                                │
│                    ┌─────────▼─────────┐                      │
│                    │   Main Service    │                      │
│                    │    (FastAPI)      │                      │
│                    │   Port: 8000      │                      │
│                    └─────────┬─────────┘                      │
│                              │                                │
│            ┌─────────────────┼─────────────────┐              │
│            │                 │                 │              │
│    ┌───────▼────────┐ ┌─────▼──────┐          │              │
│    │   Payments     │ │ Promotions │          │              │
│    │   Service      │ │  Service   │          │              │
│    │    (Go)        │ │   (.NET)   │          │              │
│    │  Port: 8081    │ │ Port: 8082 │          │              │
│    └───────┬────────┘ └────────────┘          │              │
│            │                                   │              │
│            │                    ┌──────────────▼────────┐     │
│            │                    │    PostgreSQL         │     │
│            │                    │      Redis            │     │
│            │                    └───────────────────────┘     │
└────────────┼────────────────────────────────────────────────┘
             │
             │ HTTP Calls to 3rd Party APIs
             │
┌────────────▼─────────────────────────────────────────────────┐
│ EXTERNAL 3RD PARTY SYSTEMS (Mocked in Demo)                 │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │   Payment    │  │     CRM      │  │    Inventory    │   │
│  │   Provider   │  │    System    │  │     System      │   │
│  │  (Stripe-    │  │ (Salesforce- │  │  (SAP-like)     │   │
│  │    like)     │  │    like)     │  │                 │   │
│  │ Port: 3001   │  │ Port: 3002   │  │  Port: 3003     │   │
│  └──────────────┘  └──────────────┘  └─────────────────┘   │
│                                                              │
│  Note: These simulate external third-party systems          │
│        Real third-party services don't expose monitoring    │
└──────────────────────────────────────────────────────────────┘
```

## Service Communication Flow

### Application Services

**Frontend** (React + Grafana Faro)
- Single Page Application for e-commerce UI
- Real User Monitoring (RUM) with Grafana Faro
- Sends user interactions, page loads, errors to Grafana
- Communicates with Main Service via REST API

**Main Service** (Python/FastAPI) - Port 8000
- **Core Functions**: Product catalog, shopping cart, order management
- **Dependencies**: PostgreSQL, Redis, Payments Service, Promotions Service, External Services
- **Database**: PostgreSQL for orders, products
- **Cache**: Redis for cart sessions
- **Instrumentation**: OpenTelemetry auto-instrumentation for FastAPI, SQLAlchemy, Redis, HTTPX

**Payments Service** (Go/Gin) - Port 8081
- **Core Functions**: Payment processing, transaction handling
- **Dependencies**: Payment Provider (external)
- **Instrumentation**: OpenTelemetry for Gin, HTTP client
- **Custom Metrics**: Payment success/failure rates by country

**Promotions Service** (C#/.NET) - Port 8082
- **Core Functions**: Discount calculation, promotional campaigns
- **Dependencies**: None (standalone)
- **Instrumentation**: OpenTelemetry for ASP.NET Core
- **Logging**: Serilog with structured logging

**External Services** (Node.js/Express)
- **Payment Provider** (Port 3001): Simulates Stripe-like payment gateway
- **CRM System** (Port 3002): Simulates Salesforce-like customer management
- **Inventory System** (Port 3003): Simulates SAP-like warehouse management
- **Behavior**: Realistic failure rates, NO monitoring instrumentation (simulates real third-party APIs)

### Infrastructure Services

**PostgreSQL** (Port 5432)
- Main database for products, orders, users
- Connection pooling via SQLAlchemy

**Redis** (Port 6379)
- Session storage for shopping carts
- Cache for frequently accessed data

## Observability Pipeline

The architecture uses a **pure OTLP push pattern** - all telemetry flows through the OpenTelemetry Collector.

**OTLP** (OpenTelemetry Protocol) is the native protocol for transmitting metrics, traces, and logs from instrumented applications to collectors and backends. It supports both gRPC (port 4317) and HTTP (port 4318) transports.

```
┌──────────────────────────────────────────────────────────────┐
│                    Application Services                      │
│         (Instrumented with OpenTelemetry SDKs)              │
│   main-service (Python) | payments-service (Go)             │
│   promotions-service (.NET) | frontend (Faro)               │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       │ Push telemetry via OTLP (OpenTelemetry Protocol)
                       │ • Metrics (OTLP/gRPC port 4317)
                       │ • Traces  (OTLP/gRPC port 4317)
                       │ • Logs    (OTLP/gRPC port 4317)
                       │
           ┌───────────▼────────────┐
           │  OpenTelemetry         │
           │     Collector          │
           │                        │
           │  • Receives OTLP data  │
           │  • Batches & processes │
           │  • Exports to backends │
           │  • Tail sampling       │
           └───────────┬────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        │ Prometheus   │ OTLP Push    │ OTLP Push
        │ PULL (scrape)│ (port 4317)  │ (HTTP)
        │              │              │
  ┌─────▼─────┐  ┌────▼────┐  ┌─────▼─────┐
  │Prometheus │  │  Tempo  │  │   Loki    │
  │ (Metrics) │  │(Traces) │  │  (Logs)   │
  │ Port: 9090│  │Port:3200│  │ Port:3100 │
  │           │  │         │  │           │
  │ Scrapes:  │  │         │  │  Loki     │
  │ :8889     │  │         │  │  Ruler    │
  └─────┬─────┘  └────┬────┘  └─────┬─────┘
        │             │              │
        │      ┌──────▼──────┐       │
        │      │Alertmanager │       │
        │      │   (Alerts)  │       │
        │      │ Port: 9093  │       │
        │      └──────┬──────┘       │
        │             │              │
        └─────────────┼──────────────┘
                      │
              ┌───────▼────────┐
              │    Grafana     │
              │ (Visualization)│
              │   Port: 3000   │
              │                │
              │  • Dashboards  │
              │  • Explore     │
              │  • Alerting    │
              └────────────────┘
```

### Key Architectural Decisions

**1. Pure OTLP Push (No Prometheus Client Libraries)**
- ✅ Services push metrics via OTLP only
- ✅ No `/metrics` endpoints on services
- ✅ OTLP Collector aggregates and exports to Prometheus exporter (:8889)
- ✅ Prometheus scrapes the collector, not individual services
- ✅ Vendor-neutral, pure OpenTelemetry implementation

**2. Centralized Telemetry Processing**
- All telemetry flows through the OTLP Collector
- Consistent labeling and enrichment
- Tail sampling for traces (value-based policies)
- Single point for data routing

**3. External Services Have No Monitoring**
- Payment Provider, CRM, Inventory systems don't expose metrics/traces
- Realistic simulation of third-party SaaS APIs
- You can only monitor your calls TO them, not their internals

## Security Architecture

The Main Service implements comprehensive security measures with full observability to detect and prevent abuse.

### Security Layers

```
┌──────────────────────────────────────────────────────────────┐
│                        Client Request                        │
└─────────────────────────┬────────────────────────────────────┘
                          │
                ┌─────────▼─────────┐
                │ LAYER 1: CORS     │
                │ - Origin validation│
                │ - Headers control │
                └─────────┬─────────┘
                          │
                ┌─────────▼─────────────────┐
                │ LAYER 2: Rate Limiting    │
                │ Redis-Backed Dual-Tier    │
                │ Sliding Window            │
                │                           │
                │ Per IP: 200 req/min       │
                │  └─→ Shared IPs (corporate,│
                │      CGNAT, public WiFi)  │
                │                           │
                │ Per User: 60 req/min      │
                │  └─→ Authenticated users  │
                │      (individual limit)   │
                │                           │
                │ ✓ Survives restarts       │
                │ ✓ Works across instances  │
                │ ✓ Atomic operations       │
                └─────────┬─────────────────┘
                          │
                ┌─────────▼─────────────────┐
                │ LAYER 3: Authentication   │
                │ - Bearer token validation │
                │ - Metrics tracking        │
                └─────────┬─────────────────┘
                          │
                ┌─────────▼───────────────────┐
                │ LAYER 4: Suspicious Activity│
                │         Detection           │
                │                             │
                │ • Credential stuffing       │
                │   (5+ failed auths/5min)    │
                │                             │
                │ • Endpoint scanning         │
                │   (10+ 404s/5min)          │
                │                             │
                │ • Abuse detection           │
                │   (20+ 4xx/5min)           │
                └─────────┬───────────────────┘
                          │
                    ┌─────▼──────┐
                    │  Business  │
                    │   Logic    │
                    └────────────┘
```

### Dual-Tier Rate Limiting

**Why Two Different Limits?**

The Main Service implements **Redis-backed** dual-tier rate limiting with IP-based and user-based limits:

| Limit Type | Requests/Min | Rationale |
|------------|--------------|-----------|
| **IP-based** | 200 | Many legitimate users may share the same IP address |
| **User-based** | 60 | Individual authenticated users get stricter limits |

**Shared IP Scenarios**:
- **Corporate Networks**: 100s of employees behind same NAT gateway
- **ISP CGNAT** (Carrier-Grade NAT): 1000s of residential customers sharing one public IP
- **Public WiFi**: Coffee shops, airports, hotels serve many simultaneous users
- **Educational Institutions**: Universities, schools with centralized network

**Implementation**: Redis-backed sliding window using sorted sets

**Advantages**:
- ✅ **Survives Restarts**: Rate limit state persists across service deployments
- ✅ **Horizontal Scaling**: Shared state across multiple service instances
- ✅ **Atomic Operations**: Redis pipeline ensures race-free counting
- ✅ **Automatic Cleanup**: TTL-based expiration prevents memory bloat
- ✅ **Accurate Windows**: Sorted sets enable true sliding windows

**Algorithm**:
1. Remove timestamps older than window (60 seconds)
2. Count requests in current window
3. Add current request with timestamp
4. Set TTL for automatic cleanup

**Code Reference**: [redis_rate_limiter.py:54-107](services/main-service/redis_rate_limiter.py#L54-L107)

### Authentication

Bearer token validation with comprehensive monitoring:

```python
Authorization: Bearer {token}
```

**Metrics Tracked**:
- Total authentication attempts
- Failed authentications by reason:
  - `missing_header`: No Authorization header
  - `invalid_format`: Malformed header (not "Bearer {token}")
  - `invalid_token`: Token not in valid set

**Code Reference**: [auth.py:34-67](services/main-service/auth.py#L34-L67)

### Suspicious Activity Detection

Real-time pattern detection for security threats:

| Pattern | Threshold | Metric | Action |
|---------|-----------|--------|--------|
| **Credential Stuffing** | 5+ failed auths in 5min | `suspicious_activity{type="credential_stuffing"}` | Alert security team |
| **Endpoint Scanning** | 10+ 404s in 5min | `suspicious_activity{type="endpoint_scanning"}` | Alert + potential IP block |
| **Abuse** | 20+ 4xx errors in 5min | `suspicious_activity{type="abuse"}` | Alert + investigate |

**Code Reference**: [security.py:112-140](services/main-service/security.py#L112-L140)

### Security Metrics

All security events are instrumented with OpenTelemetry metrics:

```python
# Authentication
webstore_auth_attempts_total{type="bearer_token"}
webstore_auth_failures_total{reason="invalid_token"}

# Rate Limiting
webstore_rate_limit_exceeded_total{limit_type="ip", client_ip="..."}
webstore_rate_limit_exceeded_total{limit_type="user", user_id="..."}

# Suspicious Activity
webstore_security_suspicious_activity_total{type="credential_stuffing", client_ip="..."}
webstore_security_suspicious_activity_total{type="endpoint_scanning", client_ip="..."}
webstore_security_suspicious_activity_total{type="abuse", client_ip="..."}
```

**Dashboard**: See [Security Monitoring](http://localhost:3000/d/security-monitoring) in Grafana

### Security Alerts

Prometheus alerts configured for security incidents:

**Critical Alerts**:
- `CredentialStuffingAttack`: Immediate alert on credential stuffing detection
- `HighAuthenticationFailureRate`: >10% auth failure rate for 5 minutes
- `SuspiciousActivitySpike`: >50 suspicious events/min

**Warning Alerts**:
- `HighRateLimitViolations`: >100 rate limit hits/min
- `EndpointScanningDetected`: Active endpoint scanning attempts
- `AbnormalAuthFailures`: >5% auth failure rate sustained

**Code Reference**: [prometheus-alerts.yml:140-229](prometheus-alerts.yml#L140-L229)

### Best Practices

**1. Defense in Depth**
- Multiple security layers (rate limiting → auth → activity detection)
- Each layer is independently monitored
- Failures don't cascade (auth failure doesn't prevent rate limit tracking)

**2. Observable Security**
- Every security event generates metrics
- All events include trace context for investigation
- Security dashboard provides real-time visibility

**3. Gradual Response**
- Rate limiting: 429 response (Retry-After header)
- Auth failure: 401 response (no account details leaked)
- Suspicious activity: Alert (human review)

**4. Production Hardening**
- ✅ **Redis-backed rate limiting** - Persistent across restarts, works across instances
- Implement IP allowlisting/blocklisting
- Add WAF (Web Application Firewall)
- Enable DDoS protection (Cloudflare, AWS Shield)
- Rotate tokens regularly
- Implement token refresh mechanism

## Analytics Features

The Main Service includes comprehensive analytics capabilities for business intelligence and conversion optimization.

### Funnel Analysis

**Purpose**: Track user progression through the purchase journey to identify drop-off points and optimize conversion rates.

**Funnel Stages**:
```
1. Browse Catalog → 2. View Product → 3. Add to Cart → 4. Checkout Complete
```

**Metric**: `webstore.funnel.stage`

**Attributes**:
- `stage`: browse_catalog, view_product, add_to_cart, checkout_complete
- `country`: Country code (US, UK, DE, FR, JP, BR, IN)
- `payment_method`: For checkout_complete stage

**Example Queries**:
```promql
# Overall conversion rate (browse to checkout)
sum(rate(webstore_funnel_stage_total{stage="checkout_complete"}[5m]))
/ sum(rate(webstore_funnel_stage_total{stage="browse_catalog"}[5m]))

# Country-specific drop-off analysis
sum(rate(webstore_funnel_stage_total[5m])) by (stage, country)

# Cart abandonment rate
1 - (
  sum(rate(webstore_funnel_stage_total{stage="checkout_complete"}[5m]))
  / sum(rate(webstore_funnel_stage_total{stage="add_to_cart"}[5m]))
)
```

**Use Cases**:
- Identify which countries have lowest conversion rates
- Measure impact of UX changes on funnel progression
- Calculate cart abandonment and checkout completion rates
- A/B test optimization impact

**Code Reference**: [monitoring.py:94-99](services/main-service/monitoring.py#L94-L99)

### Customer Segmentation

**Purpose**: Automatically classify customers into behavioral segments for targeted analytics and business intelligence.

**Segments**:

| Segment | Definition | Criteria |
|---------|------------|----------|
| **new** | First-time visitor | No previous activity recorded |
| **returning** | Active customer | Activity in last 30 days |
| **vip** | High-value customer | >$500 total spend OR >5 orders |
| **at_risk** | Declining engagement | Last activity 30-90 days ago |
| **churned** | Inactive customer | No activity in 90+ days |

**Metric**: `webstore.customer.segment`

**Attributes**:
- `segment`: new, returning, vip, at_risk, churned
- `action`: browse_catalog, view_product, add_to_cart, checkout
- `country`: Country code

**Data Storage**: Redis (90-day TTL)
- `customer:{user_id}:activity` - Last activity timestamp
- `customer:{user_id}:spend` - Total spend (USD)
- `customer:{user_id}:orders` - Total order count

**Example Queries**:
```promql
# Distribution of customers by segment
sum(rate(webstore_customer_segment_total[5m])) by (segment)

# VIP customer checkout rate
sum(rate(webstore_customer_segment_total{segment="vip", action="checkout"}[5m]))

# At-risk customer re-engagement
sum(rate(webstore_customer_segment_total{segment="at_risk"}[5m])) by (action)

# New vs returning customer conversion
sum(rate(webstore_customer_segment_total{action="checkout"}[5m])) by (segment)
```

**Use Cases**:
- Monitor VIP customer activity and engagement
- Identify at-risk customers for retention campaigns
- Compare conversion rates across segments
- Measure effectiveness of re-engagement strategies
- Calculate customer lifetime value by segment

**Code Reference**: [customer_segmentation.py](services/main-service/customer_segmentation.py)

### Analytics Dashboard Integration

Both funnel analysis and customer segmentation are visualized in the **WebStore Overview** Grafana dashboard:

**Panels**:
- **Funnel Visualization**: Sankey diagram showing progression through stages
- **Conversion Rates**: Time-series by country and segment
- **Customer Segment Distribution**: Pie chart of current segment breakdown
- **Segment Performance**: Table of key metrics per segment
- **Drop-off Analysis**: Heatmap showing where users abandon the journey

**Access**: [http://localhost:3000/d/webstore-overview](http://localhost:3000/d/webstore-overview)

**Related Documentation**: [ANALYTICS_FEATURES.md](../ANALYTICS_FEATURES.md)

## User Journey: E-commerce Flow

This section explains the complete customer journey through the WebStore, including the **optimistic inventory strategy** used to maximize sales conversion.

### Overview

The WebStore implements an **optimistic e-commerce pattern** where customer experience and conversion rate are prioritized over strict inventory validation. This is a realistic approach used by major retailers (Amazon, Best Buy, Zappos) to maximize revenue.

### Complete User Journey

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER JOURNEY                                │
└─────────────────────────────────────────────────────────────────────┘

1. SELECT COUNTRY
   ├─ User visits webstore homepage
   ├─ Frontend: Country selector defaulted to "US"
   │  └─→ Options: US, UK, DE, FR, JP, BR, IN
   └─ Result: ✅ Country context set for session

   Business Decision: Country determines:
   - Product catalog availability
   - Pricing and currency
   - Inventory locations
   - Shipping options


2. BROWSE PRODUCT CATALOG
   ├─ User views product catalog for selected country
   ├─ GET /{country}/products
   │  ├─→ Example: GET /us/products (US catalog)
   │  ├─→ Example: GET /de/products (German catalog)
   │  ├─→ DB: SELECT * FROM products
   │  ├─→ Metric: webstore.products.views{country="US"}
   │  └─→ Returns: All products (no stock filtering)
   └─ Result: ✅ Customer sees full catalog for their country

   Business Decision: Show all products to maximize discovery

   Real-world pattern:
   - Amazon.com vs Amazon.de have different catalogs
   - Products vary by region (electronics, books, regulations)
   - Pricing differs by market

   Code: services/main-service/routers/products.py:14-53


3. VIEW PRODUCT DETAILS
   ├─ User clicks on a product to see details
   ├─ GET /{country}/products/{product_id}
   │  ├─→ Example: GET /us/products/123
   │  ├─→ DB: SELECT * FROM products WHERE id=123
   │  ├─→ Metric: webstore.products.detail_views{country="US", product_id="123", category="Electronics"}
   │  ├─→ Returns: Product details (name, price, description, stock)
   │  └─→ Shows stock level but allows adding even if low/out-of-stock
   └─ Result: ✅ Customer sees product details for their country

   Business Decision: Display stock as informational, not blocking
   - Shows current stock level
   - Allows adding to cart regardless of stock
   - Stock updates frequently (may change during checkout)

   Monitoring:
   - Track which products are viewed most by country
   - Browse-to-detail conversion rate
   - Popular categories by region

   Code: services/main-service/routers/products.py:56-92


4. ADD TO CART
   ├─ User clicks "Add to Cart" from product detail page
   ├─ POST /cart/add {product_id, quantity, country}
   │  ├─→ Validates: Product exists in catalog
   │  ├─→ Does NOT check: Stock availability
   │  ├─→ DB: INSERT INTO cart_items
   │  └─→ Redis: INCR cart:{user_id}
   └─ Result: ✅ Item added (even if out of stock)

   Business Decision: Cart is a "wishlist" - stock changes frequently
   during browsing. Checking stock here creates poor UX (item appears
   available, then suddenly "out of stock", then available again).

   Code: services/main-service/services/cart_service.py:77-88


5. VIEW CART
   ├─ User reviews cart
   ├─ GET /cart
   │  ├─→ DB: SELECT cart_items WHERE user_id=?
   │  ├─→ DB: SELECT products (join for pricing)
   │  └─→ Returns: Cart contents with current prices
   └─ Result: ✅ Cart displayed with subtotal


6. CHECKOUT - STEP 1: VALIDATE CART
   ├─ User clicks "Checkout"
   ├─ POST /orders/checkout {payment_method, country}
   │  ├─→ DB: SELECT cart_items WHERE user_id=?
   │  ├─→ IF cart empty → 400 Bad Request
   │  └─→ DB: SELECT products WHERE id IN (cart_items)
   └─ Result: ✅ Cart validated, proceed to payment


7. CHECKOUT - STEP 2: INVENTORY CHECK (Advisory Only)
   ├─ For each cart item:
   │  └─→ POST inventory-system /api/inventory/check
   │     ├─→ {product_id, quantity, country}
   │     └─→ Returns: {available: true/false, warehouses: [...]}
   │
   ├─ IF not available:
   │  ├─→ Log warning: "Inventory not available in preferred warehouses"
   │  └─→ Continue anyway (do NOT block checkout)
   │
   └─ Result: ⚠️ Warning logged but order continues

   Business Decision: OPTIMISTIC INVENTORY APPROACH
   - Inventory check is advisory, NOT blocking
   - We process payment even if warehouse shows low/no stock
   - Rationale:
     1. Inventory updates frequently (restocks, returns, transfers)
     2. May find product in alternative warehouse
     3. Can fulfill from supplier if needed (dropship)
     4. Better UX: "Order confirmed" vs "Out of stock" rejection

   Tradeoff: Higher conversion vs occasional fulfillment delays

   Code: services/main-service/services/order_service.py:121-142


8. CHECKOUT - STEP 3: APPLY PROMOTIONS
   ├─→ POST promotions-service /api/promotions/check
   │  ├─→ {user_id, country, amount}
   │  ├─→ Checks: Tiered discounts, coupon codes
   │  └─→ Returns: {discount, promo_code}
   │
   ├─→ Calculate final total: subtotal - discount
   └─ Result: ✅ Discount applied (if eligible)


9. CHECKOUT - STEP 4: PROCESS PAYMENT
   ├─→ POST payments-service /api/payments/process
   │  ├─→ {user_id, amount, country, payment_method}
   │  │
   │  ├─→ Go payments-service calls external provider:
   │  │  └─→ POST payment-provider /api/payment/process
   │  │     ├─→ 3% chance: Slow (1-2 seconds)
   │  │     ├─→ Country-specific failure rates:
   │  │     │   - US: 5%, UK: 3%, DE: 2%, JP: 8%, etc.
   │  │     └─→ Returns: {status: "success", transaction_id}
   │  │
   │  └─→ IF payment fails → 500 Error, stop checkout
   │
   └─ Result: ✅ Payment charged, transaction_id received

   CRITICAL: Payment happens BEFORE warehouse inventory confirmation
   This is intentional (see Step 11 for explanation)


10. CHECKOUT - STEP 5: CREATE ORDER
   ├─→ DB Transaction:
   │  ├─→ INSERT INTO orders (status='completed', ...)
   │  ├─→ UPDATE products SET stock = stock - quantity
   │  ├─→ DELETE FROM cart_items WHERE user_id=?
   │  ├─→ Redis: DELETE cart:{user_id}
   │  └─→ COMMIT
   │
   └─ Result: ✅ Order created, customer charged, cart cleared


11. FULFILLMENT - STEP 6: RESERVE WAREHOUSE INVENTORY (Post-Payment)
   ├─ For each order item (async, after payment succeeds):
   │  └─→ POST inventory-system /api/inventory/reserve
   │     ├─→ {product_id, quantity, country, order_id}
   │     └─→ Returns: {reserved: true, reservation_id}
   │
   ├─ IF reservation succeeds (99% case):
   │  └─→ Ships from confirmed warehouse
   │
   └─ IF reservation fails (1% case):
      ├─→ Option A: Find alternative warehouse
      ├─→ Option B: Order from supplier (dropship)
      ├─→ Option C: Notify customer of 1-2 day delay
      └─→ Rarely: Cancel order and refund (monitored metric)

   OPTIMISTIC INVENTORY STRATEGY EXPLAINED:

   Why we process payment BEFORE warehouse confirmation:

   ✅ Pros:
   - Higher conversion rate (customer completes purchase)
   - Inventory often becomes available quickly (restocks)
   - Can fulfill from alternative sources
   - Better customer experience ("order confirmed")

   ⚠️ Cons:
   - Occasional fulfillment delays (1-2 days)
   - Rare out-of-stock cancellations (must be <0.1%)

   Monitoring:
   - Track reservation failure rate
   - Track customer complaints about delays
   - Track cancellation rate due to out-of-stock

   If metrics are acceptable (e.g., <1% delay rate), this approach
   maximizes revenue while maintaining customer satisfaction.

   Real-world examples:
   - Amazon: Allows ordering out-of-stock items, extends delivery
   - Best Buy: Processes payment, may fulfill from different location
   - Zappos: Orders from supplier if needed, upgrades shipping

   Code: services/main-service/services/order_service.py:254-277


12. POST-ORDER OPERATIONS (Background)
    ├─→ POST crm-system /api/customer/order
    │  └─→ Update customer profile (fire-and-forget)
    │
    └─→ (In production: Send confirmation email)


13. ORDER COMPLETE
    └─ Result: ✅ Customer receives order confirmation
              ✅ 99% shipped normally
              ⚠️ 1% slight delay (acceptable for higher conversion)
```

### Journey Summary Table

| Step | Action | Stock Check | Blocking? | Success Rate |
|------|--------|-------------|-----------|--------------|
| 1. Select Country | Choose market | ❌ None | No | 100% |
| 2. Browse Catalog | View products | ❌ None | - | 100% |
| 3. View Product | Product details | ❌ None | - | 100% |
| 4. Add to Cart | Add item | ❌ None | No | 100% |
| 5. View Cart | Review cart | ❌ None | No | 100% |
| 6. Checkout Start | Validate cart exists | ❌ None | Yes (if empty) | ~100% |
| 7. Inventory Check | Advisory check | ⚠️ Advisory only | **No** | N/A (not blocking) |
| 8. Promotions | Apply discounts | ❌ None | No | 100% |
| 9. Payment | Charge customer | ❌ None | Yes (if fails) | ~95% (country-dependent) |
| 10. Create Order | DB transaction | ✅ Stock decremented | Yes (if DB error) | ~100% |
| 11. Reserve Inventory | Warehouse confirmation | ✅ Post-payment | **No** (already paid) | ~99% |
| 12. CRM Update | Background | - | - | ~92% (non-critical) |
| 13. Ship | Fulfillment | - | - | 99% normal, 1% delayed |

### Key Insights

**Why This Flow is Realistic**:

1. **Optimistic Cart**: Allows adding out-of-stock items (matches customer expectations)
2. **Advisory Inventory**: Checks availability but doesn't block (maximizes conversion)
3. **Payment First**: Charges before warehouse confirmation (captures sale)
4. **Graceful Degradation**: Handles inventory issues post-payment (maintains revenue)

**When Optimistic Inventory Works**:
- ✅ High product availability (>95%)
- ✅ Multiple fulfillment centers
- ✅ Alternative sourcing options (dropship)
- ✅ Customer tolerance for 1-3 day delays
- ✅ Low expected cancellation rate (<0.1%)

**When to Use Pessimistic Inventory Instead**:
- ❌ Limited/rare items (concert tickets, limited editions)
- ❌ No alternative sourcing
- ❌ Immediate delivery expectations
- ❌ Regulatory requirements (prescriptions)

**Metrics to Monitor**:
```promql
# Reservation failure rate (should be <1%)
rate(inventory_reservation_failures_total[5m])

# Orders with delayed fulfillment (should be <1%)
rate(orders_delayed_fulfillment_total[5m])

# Out-of-stock cancellations (should be <0.1%)
rate(orders_cancelled_out_of_stock_total[5m])
```

## Data Flow: Complete Checkout Process

Let's trace a complete checkout request through the system:

```
1. User clicks "Checkout" in Frontend
   │
   ├─→ [Frontend] Grafana Faro
   │   └─→ RUM event: checkout_initiated
   │   └─→ Sends to Grafana Cloud/local
   │
2. Frontend calls POST /checkout
   │
   ├─→ [Main Service] FastAPI receives request
   │   │
   │   ├─→ OpenTelemetry creates trace: trace_id=abc123
   │   │   └─→ Root span: "POST /checkout"
   │   │
   │   ├─→ Log: "Checkout started" (with trace_id)
   │   │   └─→ Pushed to OTLP Collector → Loki
   │   │
   │   ├─→ Query cart from PostgreSQL
   │   │   └─→ Span: "db_query cart"
   │   │
   │   ├─→ Check inventory availability
   │   │   │
   │   │   └─→ HTTP call to Inventory Service (propagates trace_id)
   │   │       │
   │   │       ├─→ [Inventory Service] Node.js receives request
   │   │       │   └─→ Span: "check_stock" (child of checkout span)
   │   │       │   └─→ Random 10% failure simulation
   │   │       │   └─→ Returns: {available: true, warehouse: "US-EAST"}
   │   │       │
   │   │       └─→ Main Service receives response
   │   │
   │   ├─→ Process payment
   │   │   │
   │   │   └─→ HTTP call to Payments Service (propagates trace_id)
   │   │       │
   │   │       ├─→ [Payments Service] Go receives request
   │   │       │   │
   │   │       │   ├─→ Span: "process_payment" (child of checkout span)
   │   │       │   │
   │   │       │   ├─→ Call external Payment Provider
   │   │       │   │   │
   │   │       │   │   └─→ [Payment Provider] Node.js
   │   │       │   │       └─→ Span: "payment_provider_api"
   │   │       │   │       └─→ Country-specific failure rate (US: 5%)
   │   │       │   │       └─→ Returns: {status: "success", txn_id: "xyz"}
   │   │       │   │
   │   │       │   ├─→ Metric: payments_processed_total{status="success", country="US"}
   │   │       │   │   └─→ Pushed to OTLP Collector → Prometheus
   │   │       │   │
   │   │       │   ├─→ Metric: payment_amount_usd (histogram)
   │   │       │   │   └─→ Links to trace via exemplar
   │   │       │   │
   │   │       │   └─→ Log: "Payment processed successfully"
   │   │       │       └─→ Pushed to OTLP Collector → Loki
   │   │       │
   │   │       └─→ Main Service receives payment result
   │   │
   │   ├─→ Create order in PostgreSQL
   │   │   └─→ Span: "db_insert order"
   │   │
   │   ├─→ Reserve inventory
   │   │   └─→ HTTP call to Inventory Service
   │   │       └─→ Span: "reserve_stock"
   │   │       └─→ Returns: {reserved: true, reservation_id: "R123"}
   │   │
   │   ├─→ Update CRM
   │   │   └─→ HTTP call to CRM System (propagates trace_id)
   │   │       │
   │   │       └─→ [CRM System] Node.js
   │   │           └─→ Span: "update_customer"
   │   │           └─→ Random 8% failure simulation
   │   │           └─→ Returns: {success: true}
   │   │
   │   ├─→ Clear cart from Redis
   │   │   └─→ Span: "redis_delete cart"
   │   │
   │   ├─→ Metric: webstore_checkouts_total{status="success", country="US"}
   │   │   └─→ Pushed to OTLP Collector → Prometheus
   │   │
   │   ├─→ Log: "Checkout completed" (with trace_id, order_id)
   │   │   └─→ Pushed to OTLP Collector → Loki
   │   │
   │   └─→ Return: {order_id: "ORD123", status: "success"}
   │
3. Frontend receives response
   │
   └─→ [Frontend] Grafana Faro
       └─→ RUM event: checkout_completed
```

### Trace Context Propagation

All services use **W3C Trace Context** standard:

```
traceparent: 00-{trace-id}-{span-id}-{flags}
```

Example:
```
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
                └─────────────┬──────────────┘ └──────┬──────┘ └┬┘
                          trace-id (32 hex)     parent-id (16)  flags
```

This header is automatically propagated by OpenTelemetry instrumentation across:
- HTTP calls between services
- Database queries (as span attributes)
- Log entries (extracted and added to structured logs)

## Ports and Endpoints

### Application Services

| Service | Port | Health Endpoint | Purpose |
|---------|------|----------------|---------|
| Frontend | 3001 | N/A | React SPA (nginx) |
| Main Service | 8000 | `/health` | Core e-commerce API |
| Payments Service | 8081 | `/health` | Payment processing |
| Promotions Service | 8082 | `/health` | Discount management |
| Payment Provider | 3001 | `/health` | External payment gateway |
| CRM System | 3002 | `/health` | Customer management |
| Inventory System | 3003 | `/health` | Warehouse management |

### Infrastructure Services

| Service | Port(s) | Access URL | Purpose |
|---------|---------|-----------|---------|
| PostgreSQL | 5432 | N/A | Database |
| Redis | 6379 | N/A | Cache |
| OTEL Collector | 4317 (gRPC), 4318 (HTTP), 13133 (health) | http://localhost:13133 | Telemetry collection |
| Prometheus | 9090 | http://localhost:9090 | Metrics storage |
| Tempo | 3200 | http://localhost:3200 | Trace storage |
| Loki | 3100 | http://localhost:3100 | Log aggregation |
| Alertmanager | 9093 | http://localhost:9093 | Alert management |
| Grafana | 3000 | http://localhost:3000 | Visualization |

### Main Service API Endpoints

**Public** (no authentication):
- `GET /health` - Health check
- `GET /{country}/products` - List products for country (e.g., `/us/products`, `/de/products`)
- `GET /{country}/products/{id}` - Product details (e.g., `/uk/products/123`)

**Protected** (requires Bearer token):
- `POST /cart/add` - Add item to cart
- `GET /cart` - View cart
- `POST /checkout` - Process checkout
- `GET /orders` - View orders

**Country-Specific URLs**:
Product endpoints use country codes in the URL path (lowercase) following REST best practices:
- `/us/products` - US product catalog
- `/de/products` - German product catalog
- `/jp/products/123` - Product 123 in Japanese market

This pattern matches real e-commerce APIs (Amazon, eBay) where product catalogs, pricing, and availability vary by country.

**Product Monitoring**:
Product endpoints track the following metrics by country:
- `webstore.products.views` - Catalog page views by country
- `webstore.products.detail_views` - Individual product views by country and category
- Browse-to-detail conversion rate (calculated in dashboards)

See the [Product Analytics Dashboard](http://localhost:3000/d/product-analytics) for insights.

## Service Dependencies

### Dependency Graph

```
Main Service depends on:
  ├─→ PostgreSQL (critical)
  ├─→ Redis (critical)
  ├─→ Payments Service
  ├─→ Promotions Service
  ├─→ Inventory System (external)
  ├─→ CRM System (external)
  └─→ OTEL Collector (for telemetry)

Payments Service depends on:
  ├─→ Payment Provider (external)
  └─→ OTEL Collector

Promotions Service depends on:
  └─→ OTEL Collector

External Services depend on:
  └─→ Nothing (simulate third-party SaaS)
```

### Startup Order

For proper initialization, services should start in this order:

1. **Infrastructure** (PostgreSQL, Redis)
2. **Observability** (OTEL Collector, Prometheus, Tempo, Loki)
3. **External Services** (independent, can start anytime)
4. **Core Services** (Payments, Promotions)
5. **Main Service** (depends on all above)
6. **Frontend** (depends on Main Service)

Docker Compose handles this with `depends_on` directives.

## Key Takeaways

1. **Polyglot Architecture**: Python, Go, C#, Node.js all instrumented with OpenTelemetry
2. **Pure OTLP Push**: No Prometheus client libraries, everything via OTLP Collector
3. **Realistic External Services**: Third-party services don't expose monitoring
4. **Full Trace Propagation**: W3C Trace Context across all service boundaries
5. **Structured Logging**: JSON logs with trace correlation
6. **Value-Based Sampling**: Intelligent trace sampling in OTLP Collector
7. **Centralized Observability**: All telemetry flows through OTLP Collector

---

**Next**: Learn how OpenTelemetry instrumentation works → [OpenTelemetry Instrumentation](03_OPENTELEMETRY_INSTRUMENTATION.md)
