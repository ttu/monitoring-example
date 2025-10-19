package config

import "os"

// Config holds application configuration
type Config struct {
	ServiceName         string
	OTELEndpoint        string
	PaymentProviderURL  string
	Port                string
}

// Load loads configuration from environment variables
func Load() *Config {
	return &Config{
		ServiceName:        "payments-service",
		OTELEndpoint:       getEnv("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317"),
		PaymentProviderURL: getEnv("PAYMENT_PROVIDER_URL", "http://localhost:3001"),
		Port:               getEnv("PORT", "8081"),
	}
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
