# Inventory Service

External inventory and fulfillment service for managing warehouse stock levels and order fulfillment.

## Overview

This service simulates a third-party inventory management system that:
- Manages stock across multiple global warehouses
- Checks product availability by location
- Reserves inventory for orders
- Estimates fulfillment times based on warehouse location
- Tracks stock levels in real-time

## Warehouses

The service manages 7 warehouses globally:

| Code | Country | Region | Fulfillment Days |
|------|---------|--------|------------------|
| US-EAST | US | East Coast | 2 |
| US-WEST | US | West Coast | 2 |
| EU-CENTRAL | DE | Central Europe | 3 |
| UK-LONDON | UK | London | 2 |
| ASIA-TOKYO | JP | Tokyo | 3 |
| SA-BRAZIL | BR | São Paulo | 5 |
| ASIA-MUMBAI | IN | Mumbai | 4 |

## API Endpoints

### Check Stock Availability

```bash
POST /api/inventory/check
```

**Request:**
```json
{
  "product_id": 1,
  "quantity": 2,
  "country": "US"
}
```

**Response:**
```json
{
  "available": true,
  "warehouse": "US-EAST",
  "stock": 245,
  "estimated_fulfillment_days": 2,
  "checked_at": "2024-01-15T10:30:00Z"
}
```

### Reserve Inventory

```bash
POST /api/inventory/reserve
```

**Request:**
```json
{
  "product_id": 1,
  "quantity": 2,
  "country": "US",
  "order_id": "ORD-12345"
}
```

**Response:**
```json
{
  "status": "success",
  "reservation_id": "RES-1234567890-abc123",
  "warehouse": "US-EAST",
  "quantity": 2,
  "estimated_fulfillment_days": 2,
  "reserved_at": "2024-01-15T10:30:00Z"
}
```

### List Warehouses

```bash
GET /api/inventory/warehouses
```

**Response:**
```json
{
  "warehouses": [
    {
      "code": "US-EAST",
      "country": "US",
      "region": "East Coast",
      "fulfillmentDays": 2
    }
  ]
}
```

## Features

### Intelligent Warehouse Selection

The service automatically selects the best warehouse based on:
1. **Preferred warehouses** for the customer's country
2. **Stock availability** at preferred locations
3. **Fallback to any warehouse** if preferred ones are out of stock
4. **Additional fulfillment days** for non-preferred warehouses (+3 days)

### Country-to-Warehouse Mapping

- **US**: US-EAST, US-WEST
- **UK**: UK-LONDON, EU-CENTRAL
- **DE/FR**: EU-CENTRAL, UK-LONDON
- **JP**: ASIA-TOKYO
- **BR**: SA-BRAZIL, US-EAST
- **IN**: ASIA-MUMBAI, ASIA-TOKYO

### Failure Simulation

- **10% failure rate** to simulate real-world issues
- Random HTTP errors: 400, 404, 500, 503
- Helps test error handling and retry logic

### Real-time Stock Updates

- Stock levels decrease when reservations are made
- Each reservation updates the stock gauge metric
- Initial stock: 50-500 units per product per warehouse

## Metrics

The service exposes Prometheus metrics at `/metrics`:

### Counters
- `inventory_stock_checks_total` - Total stock availability checks
- `inventory_reservations_total` - Total inventory reservations

### Histograms
- `inventory_fulfillment_time_days` - Estimated fulfillment time distribution

### Gauges
- `inventory_stock_level` - Current stock level by warehouse and product

## Observability

### OpenTelemetry

Fully instrumented with OpenTelemetry:
- **Traces**: All requests traced with warehouse selection details
- **Metrics**: Custom metrics for inventory operations
- **Logs**: Structured logging with trace correlation

### Example Trace Attributes

```
span.warehouse = "US-EAST"
span.product_id = "1"
span.quantity = "2"
span.country = "US"
span.fulfillment_days = "2"
```

## Running Locally

```bash
# Install dependencies
npm install

# Set environment variables
export PORT=3003
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Start service
node index.js
```

## Docker

```bash
# Build
docker build -t inventory-system .

# Run
docker run -p 3003:3003 \
  -e OTEL_EXPORTER_OTLP_ENDPOINT=http://host.docker.internal:4317 \
  inventory-system
```

## Use Cases

1. **Pre-checkout Stock Validation**
   - Verify items are available before processing payment
   - Show estimated delivery dates to customers

2. **Order Fulfillment**
   - Reserve inventory when order is placed
   - Prevent overselling
   - Optimize shipping from nearest warehouse

3. **Inventory Management**
   - Monitor stock levels across warehouses
   - Track fulfillment performance by location
   - Identify stock availability issues

## Integration Example

```javascript
// Check stock availability
const checkStock = async (productId, quantity, country) => {
  const response = await fetch('http://inventory-system:3003/api/inventory/check', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ product_id: productId, quantity, country })
  });

  const data = await response.json();

  if (data.available) {
    console.log(`In stock at ${data.warehouse}, ships in ${data.estimated_fulfillment_days} days`);
  }
};

// Reserve inventory
const reserveStock = async (productId, quantity, country, orderId) => {
  const response = await fetch('http://inventory-system:3003/api/inventory/reserve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ product_id: productId, quantity, country, order_id: orderId })
  });

  const data = await response.json();
  console.log(`Reserved: ${data.reservation_id}`);
};
```

## Why This Replaces External Promotions

An **Inventory Service** is more relevant for a webstore than a third-party promotions service because:

1. **Core E-commerce Functionality**: Stock management is essential for any online store
2. **Real Business Logic**: Warehouse selection, stock reservations, and fulfillment are real-world operations
3. **Better Observability Demo**: Shows how to monitor supply chain operations
4. **Geographic Distribution**: Demonstrates multi-region infrastructure monitoring
5. **State Management**: Tracks changing inventory levels (more complex than static promotions)

This service provides a more realistic external dependency that every webstore would actually use.
