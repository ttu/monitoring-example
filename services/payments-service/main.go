package main

import (
	"context"
	"math/rand"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"go.opentelemetry.io/contrib/instrumentation/github.com/gin-gonic/gin/otelgin"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/metric"
	"go.uber.org/zap"

	"payments-service/config"
	"payments-service/handlers"
	"payments-service/logging"
	"payments-service/monitoring"
	"payments-service/service"
)

func main() {
	// Initialize structured logging
	if err := logging.InitLogger(); err != nil {
		panic("Failed to initialize logger: " + err.Error())
	}
	defer logging.Sync()
	defer func() {
		if err := logging.Shutdown(context.Background()); err != nil {
			logging.Error("Error shutting down logger provider", zap.Error(err))
		}
	}()

	// Load configuration
	cfg := config.Load()

	// Initialize OpenTelemetry
	tp, tracer, err := monitoring.InitTracer(cfg.ServiceName, cfg.OTELEndpoint)
	if err != nil {
		logging.Fatal("Failed to initialize tracer", zap.Error(err))
	}
	defer func() {
		if err := tp.Shutdown(context.Background()); err != nil {
			logging.Error("Error shutting down tracer provider", zap.Error(err))
		}
	}()

	mp, _, err := monitoring.InitMeter(cfg.ServiceName, cfg.OTELEndpoint)
	if err != nil {
		logging.Fatal("Failed to initialize meter", zap.Error(err))
	}
	defer func() {
		if err := mp.Shutdown(context.Background()); err != nil {
			logging.Error("Error shutting down meter provider", zap.Error(err))
		}
	}()

	// Seed random
	rand.Seed(time.Now().UnixNano())

	// Initialize service layer
	paymentService := service.NewPaymentService(tracer, cfg.PaymentProviderURL)

	// Initialize handlers
	paymentHandler := handlers.NewPaymentHandler(paymentService)

	// Setup Gin router
	r := gin.Default()

	// OpenTelemetry middleware
	r.Use(otelgin.Middleware(cfg.ServiceName))
	r.Use(httpMetricsMiddleware())

	// Routes
	r.GET("/health", paymentHandler.HealthCheck)
	r.POST("/api/payments/process", paymentHandler.ProcessPayment)

	// Start server
	logging.Info("Payments service starting", zap.String("port", cfg.Port))
	if err := r.Run(":" + cfg.Port); err != nil {
		logging.Fatal("Failed to start server", zap.Error(err))
	}
}

// httpMetricsMiddleware records HTTP request metrics
func httpMetricsMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()

		// Process request
		c.Next()

		// Record duration
		duration := float64(time.Since(start).Milliseconds())

		monitoring.HTTPServerDuration.Record(c.Request.Context(), duration,
			metric.WithAttributes(
				attribute.String("http_method", c.Request.Method),
				attribute.String("http_route", c.FullPath()),
				attribute.String("http_status_code", strconv.Itoa(c.Writer.Status())),
			),
		)
	}
}
