using Microsoft.AspNetCore.Mvc;
using System.Diagnostics;
using System.Diagnostics.Metrics;
using Prometheus;

namespace PromotionsService.Controllers;

public class CheckPromotionsRequest
{
    public string UserId { get; set; } = "";
    public string Country { get; set; } = "";
    public double Amount { get; set; }
}

public class CheckPromotionsResponse
{
    public double Discount { get; set; }
    public string PromotionCode { get; set; } = "";
    public string Description { get; set; } = "";
}

public class ValidateCouponRequest
{
    public string CouponCode { get; set; } = "";
    public string UserId { get; set; } = "";
    public double Amount { get; set; }
}

public class ValidateCouponResponse
{
    public bool Valid { get; set; }
    public double Discount { get; set; }
    public string DiscountType { get; set; } = ""; // "percentage" or "fixed"
    public string Message { get; set; } = "";
}

[ApiController]
[Route("api/[controller]")]
public class PromotionsController : ControllerBase
{
    private readonly ILogger<PromotionsController> _logger;
    private readonly ActivitySource _activitySource;

    // Prometheus metrics
    private static readonly Counter PromotionsCheckedCounter = Metrics.CreateCounter(
        "promotions_checked_total",
        "Total number of promotion checks",
        new CounterConfiguration { LabelNames = new[] { "country", "has_discount" } });

    private static readonly Counter CouponsValidatedCounter = Metrics.CreateCounter(
        "coupons_validated_total",
        "Total number of coupon validations",
        new CounterConfiguration { LabelNames = new[] { "coupon_type", "valid" } });

    private static readonly Histogram DiscountAmountHistogram = Metrics.CreateHistogram(
        "promotion_discount_amount_usd",
        "Discount amounts in USD",
        new HistogramConfiguration { Buckets = Histogram.LinearBuckets(0, 10, 20) });

    // In-memory coupon database (in production, this would be a real database)
    private static readonly Dictionary<string, CouponData> Coupons = new()
    {
        { "WELCOME10", new CouponData { DiscountType = "percentage", DiscountValue = 10, MinAmount = 50, MaxUses = 1000, UsedCount = 0 } },
        { "SAVE20", new CouponData { DiscountType = "percentage", DiscountValue = 20, MinAmount = 100, MaxUses = 500, UsedCount = 0 } },
        { "FLAT50", new CouponData { DiscountType = "fixed", DiscountValue = 50, MinAmount = 200, MaxUses = 300, UsedCount = 0 } },
        { "BIGORDER", new CouponData { DiscountType = "percentage", DiscountValue = 15, MinAmount = 500, MaxUses = 100, UsedCount = 0 } },
        { "NEWUSER", new CouponData { DiscountType = "fixed", DiscountValue = 25, MinAmount = 75, MaxUses = 2000, UsedCount = 0 } },
    };

    private class CouponData
    {
        public string DiscountType { get; set; } = "";
        public double DiscountValue { get; set; }
        public double MinAmount { get; set; }
        public int MaxUses { get; set; }
        public int UsedCount { get; set; }
    }

    public PromotionsController(ILogger<PromotionsController> logger)
    {
        _logger = logger;
        _activitySource = new ActivitySource("promotions-service");
    }

    [HttpGet("health")]
    public IActionResult Health()
    {
        return Ok(new { status = "healthy" });
    }

    [HttpPost("check")]
    public async Task<IActionResult> CheckPromotions([FromBody] CheckPromotionsRequest request)
    {
        // ASP.NET Core already creates activities for HTTP requests
        var activity = Activity.Current;
        activity?.SetTag("user.id", request.UserId);
        activity?.SetTag("country", request.Country);
        activity?.SetTag("amount", request.Amount);

        _logger.LogInformation(
            "Checking promotions for user {UserId} from {Country}, amount {Amount}",
            request.UserId, request.Country, request.Amount);

        // Simulate processing delay (50-250ms)
        var delay = Random.Shared.Next(50, 250);
        await Task.Delay(delay);

        // Occasionally simulate slow processing (5% chance, 800-1500ms)
        if (Random.Shared.NextDouble() < 0.05)
        {
            var slowDelay = Random.Shared.Next(800, 1500);
            _logger.LogWarning("Slow promotion check: {Delay}ms", slowDelay);
            await Task.Delay(slowDelay);
        }

        double discount = 0.0;
        string promotionCode = "";
        string description = "";

        // Automatic tiered discounts based on amount
        if (request.Amount > 500)
        {
            discount = request.Amount * 0.1; // 10% discount
            promotionCode = "BIG_ORDER_10";
            description = "10% discount for orders over $500";
        }
        else if (request.Amount > 200)
        {
            discount = request.Amount * 0.05; // 5% discount
            promotionCode = "MEDIUM_ORDER_5";
            description = "5% discount for orders over $200";
        }
        else if (request.Amount > 100)
        {
            discount = request.Amount * 0.03; // 3% discount
            promotionCode = "SMALL_ORDER_3";
            description = "3% discount for orders over $100";
        }

        // Record metrics
        PromotionsCheckedCounter.WithLabels(request.Country, discount > 0 ? "yes" : "no").Inc();
        if (discount > 0)
        {
            DiscountAmountHistogram.Observe(discount);
        }

        activity?.SetTag("discount", discount);
        activity?.SetTag("promotion.code", promotionCode);

        _logger.LogInformation(
            "Promotion check complete: discount ${Discount}, code {PromotionCode}",
            discount, promotionCode);

        var response = new CheckPromotionsResponse
        {
            Discount = discount,
            PromotionCode = promotionCode,
            Description = description
        };

        return Ok(response);
    }

    [HttpPost("validate-coupon")]
    public IActionResult ValidateCoupon([FromBody] ValidateCouponRequest request)
    {
        // ASP.NET Core already creates activities for HTTP requests
        var activity = Activity.Current;
        activity?.SetTag("coupon.code", request.CouponCode);
        activity?.SetTag("user.id", request.UserId);
        activity?.SetTag("amount", request.Amount);

        _logger.LogInformation(
            "Validating coupon {CouponCode} for user {UserId}, amount ${Amount}",
            request.CouponCode, request.UserId, request.Amount);

        var couponCode = request.CouponCode.ToUpper();

        // Check if coupon exists with custom span
        CouponData? coupon;
        using (var lookupActivity = _activitySource.StartActivity("cache.get"))
        {
            lookupActivity?.SetTag("cache.system", "memory");
            lookupActivity?.SetTag("cache.operation", "GET");
            lookupActivity?.SetTag("cache.key", $"coupon:{couponCode}");

            var exists = Coupons.ContainsKey(couponCode);
            lookupActivity?.SetTag("cache.hit", exists);

            if (!exists)
            {
                CouponsValidatedCounter.WithLabels("unknown", "false").Inc();
                _logger.LogWarning("Coupon {CouponCode} not found", request.CouponCode);

                return Ok(new ValidateCouponResponse
                {
                    Valid = false,
                    Discount = 0,
                    Message = "Invalid coupon code"
                });
            }

            coupon = Coupons[couponCode];
        }

        // Check if coupon has reached max uses
        if (coupon.UsedCount >= coupon.MaxUses)
        {
            CouponsValidatedCounter.WithLabels(coupon.DiscountType, "false").Inc();
            _logger.LogWarning("Coupon {CouponCode} has reached maximum uses", couponCode);

            return Ok(new ValidateCouponResponse
            {
                Valid = false,
                Discount = 0,
                Message = "Coupon has expired or reached maximum uses"
            });
        }

        // Check minimum amount requirement
        if (request.Amount < coupon.MinAmount)
        {
            CouponsValidatedCounter.WithLabels(coupon.DiscountType, "false").Inc();
            _logger.LogWarning(
                "Coupon {CouponCode} minimum amount not met: ${Amount} < ${MinAmount}",
                couponCode, request.Amount, coupon.MinAmount);

            return Ok(new ValidateCouponResponse
            {
                Valid = false,
                Discount = 0,
                Message = $"Minimum order amount of ${coupon.MinAmount} required"
            });
        }

        // Calculate discount
        double discount = coupon.DiscountType == "percentage"
            ? request.Amount * (coupon.DiscountValue / 100)
            : coupon.DiscountValue;

        // Ensure discount doesn't exceed order amount
        discount = Math.Min(discount, request.Amount);

        // Increment usage count (in production, this would be atomic in database)
        using (var updateActivity = _activitySource.StartActivity("cache.update"))
        {
            updateActivity?.SetTag("cache.system", "memory");
            updateActivity?.SetTag("cache.operation", "UPDATE");
            updateActivity?.SetTag("cache.key", $"coupon:{couponCode}");
            updateActivity?.SetTag("coupon.used_count.before", coupon.UsedCount);

            coupon.UsedCount++;

            updateActivity?.SetTag("coupon.used_count.after", coupon.UsedCount);
        }

        // Record metrics
        CouponsValidatedCounter.WithLabels(coupon.DiscountType, "true").Inc();
        DiscountAmountHistogram.Observe(discount);

        activity?.SetTag("coupon.valid", true);
        activity?.SetTag("coupon.discount", discount);
        activity?.SetTag("coupon.type", coupon.DiscountType);

        _logger.LogInformation(
            "Coupon {CouponCode} validated successfully: ${Discount} discount",
            couponCode, discount);

        return Ok(new ValidateCouponResponse
        {
            Valid = true,
            Discount = discount,
            DiscountType = coupon.DiscountType,
            Message = $"Coupon applied: {coupon.DiscountValue}{(coupon.DiscountType == "percentage" ? "%" : " USD")} off"
        });
    }

    [HttpGet("coupons")]
    public IActionResult GetAvailableCoupons()
    {
        // ASP.NET Core already creates activities for HTTP requests
        var activity = Activity.Current;

        List<object> availableCoupons;
        using (var scanActivity = _activitySource.StartActivity("cache.scan"))
        {
            scanActivity?.SetTag("cache.system", "memory");
            scanActivity?.SetTag("cache.operation", "SCAN");
            scanActivity?.SetTag("cache.key_pattern", "coupon:*");

            availableCoupons = Coupons
                .Where(c => c.Value.UsedCount < c.Value.MaxUses)
                .Select(c => new
                {
                    code = c.Key,
                    discountType = c.Value.DiscountType,
                    discountValue = c.Value.DiscountValue,
                    minAmount = c.Value.MinAmount,
                    remainingUses = c.Value.MaxUses - c.Value.UsedCount
                })
                .Cast<object>()
                .ToList();

            scanActivity?.SetTag("cache.results_count", availableCoupons.Count);
        }

        return Ok(new { coupons = availableCoupons });
    }
}
