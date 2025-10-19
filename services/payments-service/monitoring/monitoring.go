package monitoring

import (
	"context"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/metric"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.21.0"
	"go.opentelemetry.io/otel/trace"
	"go.uber.org/zap"

	"payments-service/logging"
)

var (
	// OpenTelemetry metrics
	PaymentCounter       metric.Int64Counter
	PaymentAmount        metric.Float64Histogram
	ExternalCallDuration metric.Float64Histogram
	HTTPServerDuration   metric.Float64Histogram
)

// InitTracer initializes OpenTelemetry tracing
func InitTracer(serviceName, endpoint string) (*sdktrace.TracerProvider, trace.Tracer, error) {
	ctx := context.Background()

	exporter, err := otlptracegrpc.New(ctx,
		otlptracegrpc.WithEndpoint(endpoint),
		otlptracegrpc.WithInsecure(),
	)
	if err != nil {
		return nil, nil, err
	}

	res, err := resource.New(ctx,
		resource.WithAttributes(
			semconv.ServiceName(serviceName),
		),
	)
	if err != nil {
		return nil, nil, err
	}

	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(res),
	)

	otel.SetTracerProvider(tp)
	tracer := tp.Tracer(serviceName)

	logging.Info("Tracing initialized", zap.String("service_name", serviceName))

	return tp, tracer, nil
}

// InitMeter initializes OpenTelemetry metrics with OTLP exporter
func InitMeter(serviceName, endpoint string) (*sdkmetric.MeterProvider, metric.Meter, error) {
	ctx := context.Background()

	res, err := resource.New(ctx,
		resource.WithAttributes(
			semconv.ServiceName(serviceName),
		),
	)
	if err != nil {
		return nil, nil, err
	}

	// Create OTLP metric exporter
	metricExporter, err := otlpmetricgrpc.New(ctx,
		otlpmetricgrpc.WithEndpoint(endpoint),
		otlpmetricgrpc.WithInsecure(),
	)
	if err != nil {
		return nil, nil, err
	}

	mp := sdkmetric.NewMeterProvider(
		sdkmetric.WithReader(sdkmetric.NewPeriodicReader(metricExporter)),
		sdkmetric.WithResource(res),
	)

	otel.SetMeterProvider(mp)
	meter := mp.Meter(serviceName)

	// Initialize metric instruments
	PaymentCounter, err = meter.Int64Counter(
		"payments_processed_total",
		metric.WithDescription("Total number of payments processed"),
	)
	if err != nil {
		return nil, nil, err
	}

	PaymentAmount, err = meter.Float64Histogram(
		"payment_amount_usd",
		metric.WithDescription("Payment amounts in USD"),
	)
	if err != nil {
		return nil, nil, err
	}

	ExternalCallDuration, err = meter.Float64Histogram(
		"external_payment_provider_duration_seconds",
		metric.WithDescription("Duration of external payment provider calls"),
	)
	if err != nil {
		return nil, nil, err
	}

	HTTPServerDuration, err = meter.Float64Histogram(
		"http_server_duration_milliseconds",
		metric.WithDescription("HTTP server request duration in milliseconds"),
		metric.WithUnit("ms"),
	)
	if err != nil {
		return nil, nil, err
	}

	logging.Info("Metrics initialized with OTLP exporter", zap.String("endpoint", endpoint))

	return mp, meter, nil
}
