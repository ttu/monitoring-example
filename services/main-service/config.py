"""Configuration settings for the main service."""
import os
from typing import Set

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://webstore:webstore123@localhost:5432/webstore")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Service URLs
OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
PAYMENTS_SERVICE_URL = os.getenv("PAYMENTS_SERVICE_URL", "http://localhost:8081")
PROMOTIONS_SERVICE_URL = os.getenv("PROMOTIONS_SERVICE_URL", "http://localhost:8082")

# External System URLs (3rd party integrations)
PAYMENT_PROVIDER_URL = os.getenv("PAYMENT_PROVIDER_URL", "http://localhost:3001")
CRM_SYSTEM_URL = os.getenv("CRM_SYSTEM_URL", "http://localhost:3002")
INVENTORY_SYSTEM_URL = os.getenv("INVENTORY_SYSTEM_URL", "http://localhost:3003")

# Pyroscope Configuration
PYROSCOPE_SERVER = os.getenv("PYROSCOPE_SERVER_ADDRESS", "http://localhost:4040")

# Authentication
VALID_TOKENS: Set[str] = {"user-token-123", "admin-token-456", "test-token-789"}

# Application Settings
SERVICE_NAME = "main-service"
API_VERSION = "1.0.0"
