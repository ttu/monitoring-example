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
    service: 'payment-provider',
  },
  timestamp: pino.stdTimeFunctions.isoTime,
});

const app = express();
app.use(express.json());

const PORT = process.env.PORT || 3001;

// Simulate failures based on country and random chance
const FAILURE_RATES = {
  US: 0.05,
  UK: 0.07,
  DE: 0.06,
  FR: 0.08,
  JP: 0.10,
  BR: 0.15,
  IN: 0.12,
  default: 0.10,
};

const ERROR_TYPES = [
  { status: 400, message: 'Invalid payment details' },
  { status: 404, message: 'Payment method not found' },
  { status: 500, message: 'Internal payment processing error' },
  { status: 503, message: 'Payment service temporarily unavailable' },
  { status: 429, message: 'Rate limit exceeded' },
];

function shouldFail(country) {
  const failureRate = FAILURE_RATES[country] || FAILURE_RATES.default;
  return Math.random() < failureRate;
}

function getRandomError() {
  return ERROR_TYPES[Math.floor(Math.random() * ERROR_TYPES.length)];
}

function generateTransactionId() {
  return `TXN-${Date.now()}-${Math.random().toString(36).substring(7)}`;
}

// Routes
app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.post('/api/payment/process', (req, res) => {
  const { amount, currency, country, payment_method } = req.body;

  logger.info({ amount, currency, country, payment_method }, 'Processing payment');

  // Simulate processing time
  const processingTime = Math.random() * 500 + 100; // 100-600ms

  setTimeout(() => {
    // Simulate failures
    if (shouldFail(country)) {
      const error = getRandomError();
      logger.error({
        amount,
        currency,
        country,
        payment_method,
        status: error.status,
        error: error.message
      }, 'Payment failed');

      return res.status(error.status).json({
        error: error.message,
        status: 'failed',
      });
    }

    // Success
    const transactionId = generateTransactionId();

    logger.info({
      transaction_id: transactionId,
      amount,
      currency,
      country,
      payment_method
    }, 'Payment successful');

    res.json({
      transaction_id: transactionId,
      status: 'success',
      amount,
      currency,
      processed_at: new Date().toISOString(),
    });
  }, processingTime);
});

app.listen(PORT, () => {
  logger.info({ port: PORT }, 'Payment Provider service listening');
});
