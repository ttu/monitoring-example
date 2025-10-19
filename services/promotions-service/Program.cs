using System.Diagnostics;
using System.Diagnostics.Metrics;
using OpenTelemetry;
using OpenTelemetry.Exporter;
using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;
using Prometheus;
using Serilog;
using Serilog.Formatting.Compact;

// Configure Serilog for structured logging
var otlpEndpointForLogs = Environment.GetEnvironmentVariable("OTEL_EXPORTER_OTLP_ENDPOINT") ?? "http://otel-collector:4317";

Log.Logger = new LoggerConfiguration()
    .Enrich.FromLogContext()
    .Enrich.WithProperty("service", "promotions-service")
    .WriteTo.Console(new CompactJsonFormatter())
    .WriteTo.OpenTelemetry(options =>
    {
        options.Endpoint = otlpEndpointForLogs;
        options.Protocol = Serilog.Sinks.OpenTelemetry.OtlpProtocol.Grpc;
        options.ResourceAttributes = new Dictionary<string, object>
        {
            ["service.name"] = "promotions-service",
            ["deployment.environment"] = "demo"
        };
    })
    .CreateLogger();

var builder = WebApplication.CreateBuilder(args);

// Use Serilog
builder.Host.UseSerilog();

// OpenTelemetry configuration
var serviceName = Environment.GetEnvironmentVariable("OTEL_SERVICE_NAME") ?? "promotions-service";
var otlpEndpoint = Environment.GetEnvironmentVariable("OTEL_EXPORTER_OTLP_ENDPOINT") ?? "http://localhost:4317";

builder.Services.AddOpenTelemetry()
    .ConfigureResource(resource => resource.AddService(serviceName))
    .WithTracing(tracing => tracing
        .AddAspNetCoreInstrumentation()
        .AddOtlpExporter(options =>
        {
            options.Endpoint = new Uri(otlpEndpoint);
            options.Protocol = OtlpExportProtocol.Grpc;
        }))
    .WithMetrics(metrics => metrics
        .AddAspNetCoreInstrumentation()
        .AddPrometheusExporter()
        .AddOtlpExporter(options =>
        {
            options.Endpoint = new Uri(otlpEndpoint);
            options.Protocol = OtlpExportProtocol.Grpc;
        }));

builder.Services.AddControllers();

var app = builder.Build();

// Prometheus metrics endpoint
app.UseRouting();
app.UseHttpMetrics();
app.MapMetrics();

app.MapControllers();

try
{
    Log.Information("Promotions service starting");
    app.Run();
}
catch (Exception ex)
{
    Log.Fatal(ex, "Application terminated unexpectedly");
}
finally
{
    Log.CloseAndFlush();
}
