"""Validated monthly e-commerce inputs. Rates use fractions, money one currency."""

from dataclasses import asdict, dataclass, fields
import math


@dataclass(frozen=True)
class Business:
    price: float = 120.0
    unit_cost: float = 42.0
    variable_cost: float = 8.0
    orders: float = 1000.0
    returns: float = 0.06
    discount: float = 0.05
    payment_rate: float = 0.025
    ad_spend: float = 18000.0
    fixed_cost: float = 15000.0
    other_income: float = 0.0
    currency: str = "USD"
    period: str = "month"

    def __post_init__(self):
        for f in fields(self):
            v = getattr(self, f.name)
            if f.name in ("currency", "period"):
                continue
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
                raise ValueError(f"{f.name}: finite nonnegative number required")
        for key in ("returns", "discount", "payment_rate"):
            if getattr(self, key) > 1:
                raise ValueError(f"{key}: rate must be between 0 and 1")
        if self.currency not in ("USD", "EUR", "RUB") or self.period != "month":
            raise ValueError("Supported currencies: USD/EUR/RUB; period: month")

    def dict(self):
        return asdict(self)


@dataclass(frozen=True)
class Marketing:
    impressions: float = 400000
    clicks: float = 12000
    visitors: float = 11000
    leads: float = 1800
    paid_new: float = 450
    organic_new: float = 150
    repeat_customers: float = 200
    orders: float = 1000
    ad_spend: float = 18000
    acquisition_other: float = 2000
    attributed_revenue: float = 55000

    def __post_init__(self):
        for f in fields(self):
            v = getattr(self, f.name)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
                raise ValueError(f"{f.name}: finite nonnegative number required")
        # Simplified lead-based funnel; visitors are unique within each channel-period.
        if not self.impressions >= self.clicks >= self.visitors >= self.leads >= self.paid_new + self.organic_new:
            raise ValueError("Funnel must descend: impressions >= clicks >= visitors >= leads >= new customers")
        if self.orders < self.paid_new + self.organic_new + self.repeat_customers:
            raise ValueError("Orders must cover all purchasing customers")
