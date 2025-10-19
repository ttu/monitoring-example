package handlers

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"go.opentelemetry.io/otel/trace"
	"go.uber.org/zap"

	"payments-service/logging"
	"payments-service/models"
	"payments-service/service"
)

// PaymentHandler handles HTTP requests for payments
type PaymentHandler struct {
	paymentService *service.PaymentService
}

// NewPaymentHandler creates a new payment handler
func NewPaymentHandler(paymentService *service.PaymentService) *PaymentHandler {
	return &PaymentHandler{
		paymentService: paymentService,
	}
}

// ProcessPayment handles payment processing requests
func (h *PaymentHandler) ProcessPayment(c *gin.Context) {
	ctx := c.Request.Context()
	span := trace.SpanFromContext(ctx)

	var req models.PaymentRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	response, err := h.paymentService.ProcessPayment(ctx, &req)
	if err != nil {
		logger := logging.WithTraceContext(span)
		logger.Error("Payment processing failed",
			zap.Error(err),
			zap.String("user_id", req.UserID),
			zap.Float64("amount", req.Amount),
		)
		c.JSON(http.StatusBadRequest, gin.H{"error": "Payment processing failed"})
		return
	}

	span.AddEvent("payment_processed_successfully")
	c.JSON(http.StatusOK, response)
}

// HealthCheck handles health check requests
func (h *PaymentHandler) HealthCheck(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"status": "healthy"})
}
