import { trace } from '@opentelemetry/api';

let tracer;

export function initializeOpenTelemetry() {
  try {
    console.log('Initializing OpenTelemetry for browser...');

    // Get a tracer instance - using the global tracer provider
    // The auto-instrumentation from packages will handle trace export
    tracer = trace.getTracer('webstore-frontend', '1.0.0');

    console.log('OpenTelemetry tracer initialized');
  } catch (error) {
    console.error('Failed to initialize OpenTelemetry:', error);
    // Set a fallback tracer to prevent errors
    tracer = trace.getTracer('webstore-frontend-fallback', '1.0.0');
  }
}

// Export a function to get the tracer for custom instrumentation
export function getTracer() {
  if (!tracer) {
    console.warn('OpenTelemetry not initialized, returning noop tracer');
    return trace.getTracer('webstore-frontend-noop', '1.0.0');
  }
  return tracer;
}
