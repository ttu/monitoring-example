package logging

import (
	"context"
	"os"

	"go.opentelemetry.io/otel/exporters/otlp/otlplog/otlploggrpc"
	"go.opentelemetry.io/otel/log/global"
	sdklog "go.opentelemetry.io/otel/sdk/log"
	"go.opentelemetry.io/otel/sdk/resource"
	"go.opentelemetry.io/otel/trace"
	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"
)

var logger *zap.Logger
var loggerProvider *sdklog.LoggerProvider

// InitLogger initializes the structured logger
func InitLogger() error {
	// 1. Setup standard zap logger for stdout
	config := zap.NewProductionConfig()
	config.EncoderConfig.TimeKey = "timestamp"
	config.EncoderConfig.EncodeTime = zapcore.ISO8601TimeEncoder
	config.EncoderConfig.MessageKey = "msg"
	config.EncoderConfig.LevelKey = "level"

	var err error
	logger, err = config.Build(
		zap.AddCallerSkip(1), // Skip wrapper functions in stack trace
	)
	if err != nil {
		return err
	}

	// 2. Setup OTLP log exporter
	ctx := context.Background()

	// Get OTLP endpoint from environment or use default
	otlpEndpoint := os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
	if otlpEndpoint == "" {
		otlpEndpoint = "otel-collector:4317"
	}

	// Create OTLP exporter
	exporter, err := otlploggrpc.New(ctx,
		otlploggrpc.WithEndpoint(otlpEndpoint),
		otlploggrpc.WithInsecure(),
	)
	if err != nil {
		logger.Warn("Failed to create OTLP log exporter, logs will only go to stdout", zap.Error(err))
		return nil // Don't fail if OTLP isn't available
	}

	// Create resource
	res, err := resource.New(ctx,
		resource.WithFromEnv(),
		resource.WithProcess(),
		resource.WithAttributes(),
	)
	if err != nil {
		logger.Warn("Failed to create resource", zap.Error(err))
		return nil
	}

	// Create logger provider
	loggerProvider = sdklog.NewLoggerProvider(
		sdklog.WithProcessor(sdklog.NewBatchProcessor(exporter)),
		sdklog.WithResource(res),
	)

	// Set global logger provider
	global.SetLoggerProvider(loggerProvider)

	logger.Info("OTLP logging configured successfully")

	return nil
}

// GetLogger returns the global logger
func GetLogger() *zap.Logger {
	return logger
}

// WithTraceContext adds trace context to logger
func WithTraceContext(span trace.Span) *zap.Logger {
	if span.SpanContext().IsValid() {
		ctx := span.SpanContext()
		return logger.With(
			zap.String("trace_id", ctx.TraceID().String()),
			zap.String("span_id", ctx.SpanID().String()),
			zap.String("service", "payments-service"),
		)
	}
	return logger.With(zap.String("service", "payments-service"))
}

// Info logs an info message with structured fields
func Info(msg string, fields ...zap.Field) {
	logger.With(zap.String("service", "payments-service")).Info(msg, fields...)
}

// Warn logs a warning message with structured fields
func Warn(msg string, fields ...zap.Field) {
	logger.With(zap.String("service", "payments-service")).Warn(msg, fields...)
}

// Error logs an error message with structured fields
func Error(msg string, fields ...zap.Field) {
	logger.With(zap.String("service", "payments-service")).Error(msg, fields...)
}

// Fatal logs a fatal message with structured fields and exits
func Fatal(msg string, fields ...zap.Field) {
	logger.With(zap.String("service", "payments-service")).Fatal(msg, fields...)
}

// Sync flushes any buffered log entries
func Sync() error {
	if logger != nil {
		return logger.Sync()
	}
	return nil
}

// Shutdown gracefully shuts down the logger provider
func Shutdown(ctx context.Context) error {
	if loggerProvider != nil {
		return loggerProvider.Shutdown(ctx)
	}
	return nil
}
