"""Monitoring and observability setup.

Exemplar Support:
-----------------
As of OpenTelemetry Python SDK 1.28.0+, exemplars are automatically enabled
for histogram metrics when using the OTLP exporter. Exemplars link metric
data points to the traces that generated them, allowing you to:

1. Click on a metric spike in Grafana
2. See example traces that contributed to that metric
3. Jump directly to Tempo to investigate the root cause

Exemplars are automatically attached to:
- checkout_amount_histogram (links payment amounts to checkout traces)
- payment_duration_histogram (links slow payments to their traces)

No additional configuration required - exemplars are automatically sampled
when metrics are recorded within an active trace context.
"""
import logging
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
import pyroscope

from config import OTEL_EXPORTER_OTLP_ENDPOINT, PYROSCOPE_SERVER, SERVICE_NAME

logger = logging.getLogger(__name__)


def init_tracing() -> trace.Tracer:
    """
    Initialize OpenTelemetry tracing.

    Returns:
        Tracer instance
    """
    resource = Resource.create({"service.name": SERVICE_NAME})

    tracer_provider = TracerProvider(resource=resource)
    otlp_span_exporter = OTLPSpanExporter(
        endpoint=OTEL_EXPORTER_OTLP_ENDPOINT,
        insecure=True
    )
    tracer_provider.add_span_processor(BatchSpanProcessor(otlp_span_exporter))
    trace.set_tracer_provider(tracer_provider)

    logger.info(f"Tracing initialized with endpoint: {OTEL_EXPORTER_OTLP_ENDPOINT}")

    return trace.get_tracer(__name__)


def init_metrics() -> metrics.Meter:
    """
    Initialize OpenTelemetry metrics.

    Returns:
        Meter instance
    """
    resource = Resource.create({"service.name": SERVICE_NAME})

    otlp_metric_exporter = OTLPMetricExporter(
        endpoint=OTEL_EXPORTER_OTLP_ENDPOINT,
        insecure=True
    )
    otlp_metric_reader = PeriodicExportingMetricReader(
        otlp_metric_exporter,
        export_interval_millis=5000
    )

    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[otlp_metric_reader]
    )
    metrics.set_meter_provider(meter_provider)

    logger.info("Metrics initialized with OTLP exporter")

    return metrics.get_meter(__name__)


def init_profiling() -> None:
    """Initialize Pyroscope profiling."""
    try:
        pyroscope.configure(
            application_name=SERVICE_NAME,
            server_address=PYROSCOPE_SERVER,
            tags={"env": "demo"}
        )
        logger.info(f"Profiling initialized with server: {PYROSCOPE_SERVER}")
    except Exception as e:
        logger.warning(f"Failed to initialize profiling: {e}")


# Initialize tracer and meter
tracer = init_tracing()
meter = init_metrics()

# Business metrics using OpenTelemetry

# Product catalog metrics
product_views_counter = meter.create_counter(
    "webstore.products.views",
    description="Total number of product catalog views by country",
    unit="1"
)

product_detail_views_counter = meter.create_counter(
    "webstore.products.detail_views",
    description="Total number of individual product detail views by country",
    unit="1"
)

active_users_counter = meter.create_counter(
    "webstore.users.active",
    description="Total number of active users browsing the store",
    unit="1"
)

cart_additions_counter = meter.create_counter(
    "webstore.cart.additions",
    description="Total number of items added to cart",
    unit="1"
)

# Funnel analysis metrics
# These metrics track user progression through the purchase funnel
# Funnel stages: Browse Catalog → View Product → Add to Cart → Checkout → Complete
funnel_stage_counter = meter.create_counter(
    "webstore.funnel.stage",
    description="User progression through purchase funnel stages",
    unit="1"
)

# Customer segmentation metrics
customer_segment_counter = meter.create_counter(
    "webstore.customer.segment",
    description="Customer actions by segment (new, returning, vip)",
    unit="1"
)

checkout_counter = meter.create_counter(
    "webstore.checkouts",
    description="Total number of checkouts",
    unit="1"
)

checkout_amount_histogram = meter.create_histogram(
    "webstore.checkout.amount",
    description="Checkout amount in USD",
    unit="USD"
)
# Exemplars: Automatically links high/low checkout amounts to their traces

payment_duration_histogram = meter.create_histogram(
    "webstore.payment.duration",
    description="Payment processing duration",
    unit="s"
)
# Exemplars: Automatically links slow payment requests to their traces

# Optimistic inventory monitoring metrics
inventory_reservation_failures_counter = meter.create_counter(
    "webstore.inventory.reservation_failures",
    description="Total number of inventory reservation failures after payment",
    unit="1"
)

orders_delayed_fulfillment_counter = meter.create_counter(
    "webstore.orders.delayed_fulfillment",
    description="Total number of orders with delayed fulfillment due to inventory issues",
    unit="1"
)

orders_cancelled_out_of_stock_counter = meter.create_counter(
    "webstore.orders.cancelled_out_of_stock",
    description="Total number of orders cancelled due to out-of-stock (post-payment)",
    unit="1"
)

# Security monitoring metrics
auth_failures_counter = meter.create_counter(
    "webstore.auth.failures",
    description="Total number of authentication failures",
    unit="1"
)

auth_attempts_counter = meter.create_counter(
    "webstore.auth.attempts",
    description="Total number of authentication attempts",
    unit="1"
)

rate_limit_exceeded_counter = meter.create_counter(
    "webstore.rate_limit.exceeded",
    description="Total number of rate limit violations",
    unit="1"
)

suspicious_activity_counter = meter.create_counter(
    "webstore.security.suspicious_activity",
    description="Total number of suspicious activity detections",
    unit="1"
)

# External service call metrics
external_inventory_duration_histogram = meter.create_histogram(
    "webstore.external.inventory.duration",
    description="Duration of external inventory service calls",
    unit="s"
)

external_crm_duration_histogram = meter.create_histogram(
    "webstore.external.crm.duration",
    description="Duration of external CRM service calls",
    unit="s"
)

# Note: Observable Gauge for active carts (will be implemented with callback)
# This will be set up where cart state is tracked
