package service

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"math/rand"
	"net/http"
	"time"

	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/metric"
	"go.opentelemetry.io/otel/trace"
	"go.uber.org/zap"

	"payments-service/logging"
	"payments-service/models"
	"payments-service/monitoring"
)

// PaymentService handles payment processing logic
type PaymentService struct {
	tracer             trace.Tracer
	paymentProviderURL string
}

// NewPaymentService creates a new payment service
func NewPaymentService(tracer trace.Tracer, paymentProviderURL string) *PaymentService {
	return &PaymentService{
		tracer:             tracer,
		paymentProviderURL: paymentProviderURL,
	}
}

// ProcessPayment processes a payment request
func (s *PaymentService) ProcessPayment(ctx context.Context, req *models.PaymentRequest) (*models.PaymentResponse, error) {
	_, span := s.tracer.Start(ctx, "process_payment")
	defer span.End()

	span.SetAttributes(
		attribute.String("payment.user_id", req.UserID),
		attribute.Float64("payment.amount", req.Amount),
		attribute.String("payment.country", req.Country),
		attribute.String("payment.method", req.PaymentMethod),
	)

	logger := logging.WithTraceContext(span)
	logger.Info("Processing payment",
		zap.String("user_id", req.UserID),
		zap.Float64("amount", req.Amount),
		zap.String("country", req.Country),
		zap.String("payment_method", req.PaymentMethod),
	)

	// Simulate processing delay (100-400ms)
	delay := time.Duration(100+rand.Intn(300)) * time.Millisecond
	time.Sleep(delay)

	// Occasionally simulate slow processing (3% chance, 1-2 seconds)
	if rand.Float32() < 0.03 {
		slowDelay := time.Duration(1000+rand.Intn(1000)) * time.Millisecond
		logger.Warn("Slow payment processing",
			zap.Duration("delay_ms", slowDelay),
			zap.String("user_id", req.UserID),
		)
		time.Sleep(slowDelay)
	}

	// Call external payment provider
	transactionID, err := s.callExternalPaymentProvider(ctx, req)
	if err != nil {
		logger.Error("Payment failed",
			zap.Error(err),
			zap.String("user_id", req.UserID),
			zap.Float64("amount", req.Amount),
			zap.String("country", req.Country),
		)
		// Record failed payment
		monitoring.PaymentCounter.Add(ctx, 1,
			metric.WithAttributes(
				attribute.String("country", req.Country),
				attribute.String("payment_method", req.PaymentMethod),
				attribute.String("status", "failed"),
			),
		)
		span.SetAttributes(attribute.String("payment.status", "failed"))
		return nil, err
	}

	// Record successful payment metrics
	monitoring.PaymentCounter.Add(ctx, 1,
		metric.WithAttributes(
			attribute.String("country", req.Country),
			attribute.String("payment_method", req.PaymentMethod),
			attribute.String("status", "success"),
		),
	)
	monitoring.PaymentAmount.Record(ctx, req.Amount,
		metric.WithAttributes(
			attribute.String("country", req.Country),
			attribute.String("payment_method", req.PaymentMethod),
		),
	)

	span.SetAttributes(
		attribute.String("payment.transaction_id", transactionID),
		attribute.String("payment.status", "success"),
	)

	response := &models.PaymentResponse{
		TransactionID: transactionID,
		Status:        "success",
		Amount:        req.Amount,
		ProcessedAt:   time.Now().UTC().Format(time.RFC3339),
	}

	return response, nil
}

func (s *PaymentService) callExternalPaymentProvider(ctx context.Context, req *models.PaymentRequest) (string, error) {
	// otelhttp.NewTransport already instruments HTTP calls - just add custom attributes
	span := trace.SpanFromContext(ctx)
	span.SetAttributes(
		attribute.String("external.service", "payment-provider"),
		attribute.String("payment.country", req.Country),
	)

	extReq := &models.ExternalPaymentRequest{
		Amount:        req.Amount,
		Currency:      req.Currency,
		Country:       req.Country,
		PaymentMethod: req.PaymentMethod,
	}

	jsonData, err := json.Marshal(extReq)
	if err != nil {
		return "", err
	}

	// Create HTTP client with instrumentation
	client := &http.Client{
		Transport: otelhttp.NewTransport(http.DefaultTransport),
		Timeout:   10 * time.Second,
	}

	start := time.Now()
	resp, err := client.Post(
		fmt.Sprintf("%s/api/payment/process", s.paymentProviderURL),
		"application/json",
		io.NopCloser(bytes.NewReader(jsonData)),
	)
	duration := time.Since(start).Seconds()

	if err != nil {
		monitoring.ExternalCallDuration.Record(ctx, duration,
			metric.WithAttributes(
				attribute.String("country", req.Country),
				attribute.String("status", "error"),
			),
		)
		span.SetAttributes(attribute.String("external.status", "error"))
		return "", fmt.Errorf("failed to call payment provider: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		monitoring.ExternalCallDuration.Record(ctx, duration,
			metric.WithAttributes(
				attribute.String("country", req.Country),
				attribute.String("status", "failed"),
			),
		)
		span.SetAttributes(
			attribute.Int("external.status_code", resp.StatusCode),
			attribute.String("external.status", "failed"),
		)
		return "", fmt.Errorf("payment provider returned status %d", resp.StatusCode)
	}

	var extResp models.ExternalPaymentResponse
	if err := json.NewDecoder(resp.Body).Decode(&extResp); err != nil {
		return "", err
	}

	monitoring.ExternalCallDuration.Record(ctx, duration,
		metric.WithAttributes(
			attribute.String("country", req.Country),
			attribute.String("status", "success"),
		),
	)
	span.SetAttributes(
		attribute.String("external.transaction_id", extResp.TransactionID),
		attribute.String("external.status", "success"),
	)

	return extResp.TransactionID, nil
}
