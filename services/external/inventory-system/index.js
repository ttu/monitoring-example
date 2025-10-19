const express = require('express');
const pino = require('pino');

// Note: External services simulate third-party APIs
// They don't expose monitoring to maintain realistic behavior

// Configure Pino for structured logging
const logger = pino({
  formatters: {
    level: (label) => {
      return { level: label };
    },
  },
  base: {
    service: 'inventory-system',
  },
  timestamp: pino.stdTimeFunctions.isoTime,
});

const app = express();
app.use(express.json());

const PORT = process.env.PORT || 3003;

// Simulate failures (0.1% for realistic demo - with 50 concurrent users, this results in ~0.5-1% overall failure rate)
const FAILURE_RATE = 0.001;

const ERROR_TYPES = [
  { status: 400, message: 'Invalid inventory request' },
  { status: 404, message: 'Product not found in warehouse' },
  { status: 500, message: 'Inventory database error' },
  { status: 503, message: 'Inventory service temporarily unavailable' },
];

// Warehouse locations with stock levels
const WAREHOUSES = {
  'US-EAST': { country: 'US', region: 'East Coast', fulfillmentDays: 2 },
  'US-WEST': { country: 'US', region: 'West Coast', fulfillmentDays: 2 },
  'EU-CENTRAL': { country: 'DE', region: 'Central Europe', fulfillmentDays: 3 },
  'UK-LONDON': { country: 'UK', region: 'London', fulfillmentDays: 2 },
  'ASIA-TOKYO': { country: 'JP', region: 'Tokyo', fulfillmentDays: 3 },
  'SA-BRAZIL': { country: 'BR', region: 'São Paulo', fulfillmentDays: 5 },
  'ASIA-MUMBAI': { country: 'IN', region: 'Mumbai', fulfillmentDays: 4 },
};

// Country to warehouse mapping
const COUNTRY_WAREHOUSE_MAP = {
  US: ['US-EAST', 'US-WEST'],
  UK: ['UK-LONDON', 'EU-CENTRAL'],
  DE: ['EU-CENTRAL', 'UK-LONDON'],
  FR: ['EU-CENTRAL', 'UK-LONDON'],
  JP: ['ASIA-TOKYO'],
  BR: ['SA-BRAZIL', 'US-EAST'],
  IN: ['ASIA-MUMBAI', 'ASIA-TOKYO'],
};

// Simulated inventory levels (product_id -> stock per warehouse)
const inventoryStock = {};

function initializeInventory() {
  // Initialize stock for products 1-8 across all warehouses
  for (let productId = 1; productId <= 8; productId++) {
    inventoryStock[productId] = {};
    for (const warehouse in WAREHOUSES) {
      // Much higher stock to support continuous traffic - Random stock between 5000-10000
      const stock = Math.floor(Math.random() * 5000) + 5000;
      inventoryStock[productId][warehouse] = stock;
    }
  }
  logger.info({ product_count: 8, warehouse_count: Object.keys(WAREHOUSES).length }, 'Initialized stock levels');
}

function shouldFail() {
  return Math.random() < FAILURE_RATE;
}

function getRandomError() {
  return ERROR_TYPES[Math.floor(Math.random() * ERROR_TYPES.length)];
}

function selectWarehouse(country, productId, quantity) {
  const warehouses = COUNTRY_WAREHOUSE_MAP[country] || ['US-EAST'];
  
  // Try to find warehouse with sufficient stock
  for (const warehouse of warehouses) {
    if (inventoryStock[productId] && inventoryStock[productId][warehouse] >= quantity) {
      return {
        warehouse,
        available: true,
        stock: inventoryStock[productId][warehouse],
        fulfillmentDays: WAREHOUSES[warehouse].fulfillmentDays,
      };
    }
  }
  
  // No warehouse has sufficient stock
  return {
    warehouse: warehouses[0],
    available: false,
    stock: inventoryStock[productId]?.[warehouses[0]] || 0,
    fulfillmentDays: WAREHOUSES[warehouses[0]].fulfillmentDays + 7, // Additional wait
  };
}

// Initialize inventory on startup
initializeInventory();

// Routes
app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.post('/api/inventory/check', (req, res) => {
  const { product_id, quantity, country } = req.body;

  logger.info({ product_id, quantity, country }, 'Checking stock');

  // Simulate processing time
  const processingTime = Math.random() * 200 + 50; // 50-250ms

  setTimeout(() => {
    // Simulate failures
    if (shouldFail()) {
      const error = getRandomError();
      logger.error({ product_id, quantity, country, status: error.status, error: error.message }, 'Stock check failed');

      return res.status(error.status).json({
        error: error.message,
        status: 'failed',
      });
    }

    // Check inventory
    const result = selectWarehouse(country, product_id, quantity);

    logger.info({
      product_id,
      quantity,
      country,
      warehouse: result.warehouse,
      available: result.available,
      stock: result.stock
    }, 'Stock check result');

    res.json({
      product_id,
      quantity,
      available: result.available,
      warehouse: result.warehouse,
      stock: result.stock,
      fulfillment_days: result.fulfillmentDays,
      checked_at: new Date().toISOString(),
    });
  }, processingTime);
});

app.post('/api/inventory/reserve', (req, res) => {
  const { product_id, quantity, country, order_id } = req.body;

  logger.info({ order_id, product_id, quantity, country }, 'Reserving stock for order');

  // Simulate processing time
  const processingTime = Math.random() * 300 + 100; // 100-400ms

  setTimeout(() => {
    // Simulate failures
    if (shouldFail()) {
      const error = getRandomError();
      logger.error({
        order_id,
        product_id,
        quantity,
        country,
        status: error.status,
        error: error.message
      }, 'Reservation failed');

      return res.status(error.status).json({
        error: error.message,
        status: 'failed',
      });
    }

    // Check and reserve inventory
    const result = selectWarehouse(country, product_id, quantity);

    if (!result.available) {
      logger.warn({
        order_id,
        product_id,
        quantity,
        country,
        available_stock: result.stock
      }, 'Insufficient stock for reservation');

      return res.status(409).json({
        error: 'Insufficient stock',
        status: 'out_of_stock',
        available_stock: result.stock,
      });
    }

    // Reserve the stock
    inventoryStock[product_id][result.warehouse] -= quantity;
    const reservationId = `RES-${Date.now()}-${Math.random().toString(36).substring(7)}`;

    logger.info({
      reservation_id: reservationId,
      order_id,
      product_id,
      quantity,
      warehouse: result.warehouse
    }, 'Reservation successful');

    res.json({
      reservation_id: reservationId,
      product_id,
      quantity,
      warehouse: result.warehouse,
      fulfillment_days: result.fulfillmentDays,
      reserved_at: new Date().toISOString(),
      status: 'success',
    });
  }, processingTime);
});

app.listen(PORT, () => {
  logger.info({ port: PORT }, 'Inventory service listening');
});
