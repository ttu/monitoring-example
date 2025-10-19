package models

// PaymentRequest represents a payment request
type PaymentRequest struct {
	UserID        string  `json:"user_id"`
	Amount        float64 `json:"amount"`
	Currency      string  `json:"currency"`
	Country       string  `json:"country"`
	PaymentMethod string  `json:"payment_method"`
}

// PaymentResponse represents a payment response
type PaymentResponse struct {
	TransactionID string  `json:"transaction_id"`
	Status        string  `json:"status"`
	Amount        float64 `json:"amount"`
	ProcessedAt   string  `json:"processed_at"`
}

// ExternalPaymentRequest represents a request to external payment provider
type ExternalPaymentRequest struct {
	Amount        float64 `json:"amount"`
	Currency      string  `json:"currency"`
	Country       string  `json:"country"`
	PaymentMethod string  `json:"payment_method"`
}

// ExternalPaymentResponse represents a response from external payment provider
type ExternalPaymentResponse struct {
	TransactionID string `json:"transaction_id"`
	Status        string `json:"status"`
}
