"""Structured logging configuration."""
import logging
import sys
from pythonjsonlogger import jsonlogger
from opentelemetry import trace

# Note: OpenTelemetry logging SDK is experimental
# Using stable trace context integration for now
try:
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
    from opentelemetry.sdk.resources import Resource
    OTLP_LOGGING_AVAILABLE = True
except ImportError:
    OTLP_LOGGING_AVAILABLE = False


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter that includes trace context."""

    def add_fields(self, log_record, record, message_dict):
        """Add custom fields to log record."""
        super().add_fields(log_record, record, message_dict)

        # Add trace context if available
        span = trace.get_current_span()
        if span and span.get_span_context().is_valid:
            ctx = span.get_span_context()
            log_record['trace_id'] = format(ctx.trace_id, '032x')
            log_record['span_id'] = format(ctx.span_id, '016x')
            log_record['trace_flags'] = ctx.trace_flags

        # Add service name
        log_record['service'] = 'main-service'

        # Rename message field for clarity
        if 'message' in log_record:
            log_record['msg'] = log_record.pop('message')


def setup_logging():
    """Configure structured logging for the application."""

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 1. Add stdout handler with JSON formatting (for local viewing)
    formatter = CustomJsonFormatter(
        '%(levelname)s %(name)s %(message)s',
        rename_fields={
            'levelname': 'level'
        }
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 2. Add OTLP handler to send logs to collector (if available)
    if OTLP_LOGGING_AVAILABLE:
        try:
            # Create resource with service information
            resource = Resource.create({
                "service.name": "main-service",
                "deployment.environment": "demo"
            })

            # Create logger provider
            logger_provider = LoggerProvider(resource=resource)

            # Create OTLP exporter
            otlp_exporter = OTLPLogExporter(
                endpoint="http://otel-collector:4317",
                insecure=True
            )

            # Add batch processor
            logger_provider.add_log_record_processor(
                BatchLogRecordProcessor(otlp_exporter)
            )

            # Note: Using experimental API - there's no stable set_logger_provider yet
            # This will be replaced with opentelemetry.logs.set_logger_provider when stable
            from opentelemetry._logs import set_logger_provider
            set_logger_provider(logger_provider)

            # Create OTLP logging handler
            otlp_handler = LoggingHandler(
                level=logging.INFO,
                logger_provider=logger_provider
            )
            root_logger.addHandler(otlp_handler)

            logging.info("OTLP logging handler configured successfully (using experimental API)")
        except Exception as e:
            logging.warning(f"Failed to configure OTLP logging handler: {e}")
    else:
        logging.warning("OTLP logging SDK not available - logs will only go to stdout")

    # Reduce noise from libraries
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
