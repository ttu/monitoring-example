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
    service: 'crm-system',
  },
  timestamp: pino.stdTimeFunctions.isoTime,
});

const app = express();
app.use(express.json());

const PORT = process.env.PORT || 3002;

// Simulate occasional failures
const FAILURE_RATE = 0.08;

const ERROR_TYPES = [
  { status: 400, message: 'Invalid customer data' },
  { status: 404, message: 'Customer not found' },
  { status: 500, message: 'CRM database error' },
  { status: 503, message: 'CRM service temporarily unavailable' },
];

function shouldFail() {
  return Math.random() < FAILURE_RATE;
}

function getRandomError() {
  return ERROR_TYPES[Math.floor(Math.random() * ERROR_TYPES.length)];
}

// Routes
app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.post('/api/customer/order', (req, res) => {
  const { user_id, order_id, amount, country } = req.body;

  logger.info({ user_id, order_id, amount, country }, 'Recording order for customer');

  // Simulate processing time
  const processingTime = Math.random() * 300 + 50; // 50-350ms

  setTimeout(() => {
    // Simulate failures
    if (shouldFail()) {
      const error = getRandomError();
      logger.error({ user_id, order_id, status: error.status, error: error.message }, 'Failed to record order');

      return res.status(error.status).json({
        error: error.message,
        status: 'failed',
      });
    }

    // Success
    logger.info({ user_id, order_id, amount, country }, 'Order recorded successfully');

    res.json({
      status: 'success',
      customer_id: user_id,
      order_id: order_id,
      recorded_at: new Date().toISOString(),
    });
  }, processingTime);
});

app.post('/api/customer/update', (req, res) => {
  const { user_id, data } = req.body;

  logger.info({ user_id }, 'Updating customer');

  // Simulate processing time
  const processingTime = Math.random() * 200 + 50; // 50-250ms

  setTimeout(() => {
    if (shouldFail()) {
      const error = getRandomError();
      logger.error({ user_id, status: error.status, error: error.message }, 'Failed to update customer');

      return res.status(error.status).json({
        error: error.message,
        status: 'failed',
      });
    }

    logger.info({ user_id }, 'Customer updated successfully');

    res.json({
      status: 'success',
      customer_id: user_id,
      updated_at: new Date().toISOString(),
    });
  }, processingTime);
});

app.listen(PORT, () => {
  logger.info({ port: PORT }, 'CRM service listening');
});
