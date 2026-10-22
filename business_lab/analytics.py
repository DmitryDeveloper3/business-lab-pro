"""Additional pure decision models; operating profit and cash remain separate."""

from dataclasses import replace
import math
import numpy as np
import pandas as pd
from .engine import economics, ratio, simulate
from .models import Business

SKU_COLUMNS = ["sku", "price", "unit_cost", "variable_cost", "orders", "returns", "discount", "payment_rate"]
ACTUAL_COLUMNS = ["period", "currency", "revenue", "total_costs", "other_income"]


def nonnegative(**values):
    for name, value in values.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"{name}: finite nonnegative value required")


def sku_economics(frame, currency):
    if frame.empty or set(frame.columns) != set(SKU_COLUMNS) or frame.isna().any().any():
        raise ValueError("Expected complete SKU columns: " + ", ".join(SKU_COLUMNS))
    frame = frame.copy()
    frame["sku"] = frame.sku.astype(str).str.strip()
    if frame.sku.eq("").any() or frame.sku.duplicated().any():
        raise ValueError("SKU identifiers must be nonempty and unique")
    rows = []
    for row in frame.to_dict("records"):
        sku = row.pop("sku")
        try:
            model = Business(
                **{k: float(v) for k, v in row.items()}, ad_spend=0, fixed_cost=0, other_income=0, currency=currency
            )
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid SKU {sku}: {exc}") from exc
        rows.append(dict(sku=sku, currency=currency, period="month", orders=model.orders, **economics(model)))
    return pd.DataFrame(rows)


def portfolio(frame, b, allocation="revenue"):
    if allocation not in ("revenue", "orders"):
        raise ValueError("Allocation must be revenue or orders")
    data = sku_economics(frame, b.currency)
    total = float(data[allocation].sum())
    pool = b.ad_spend + b.fixed_cost
    data["allocated_shared_costs"] = data[allocation] / total * pool if total else 0.0
    data["after_allocated_costs"] = data.contribution_profit - data.allocated_shared_costs
    revenue = float(data.revenue.sum())
    contribution = float(data.contribution_profit.sum())
    profit = contribution - pool + b.other_income
    summary = dict(
        revenue=revenue,
        contribution_profit=contribution,
        shared_costs=pool,
        unallocated_costs=pool if not total else 0.0,
        other_income=b.other_income,
        operating_profit=profit,
        profit_margin=ratio(profit, revenue),
    )
    return data, summary


def goal(b, target_profit):
    nonnegative(target_profit=target_profit)
    e = economics(b)
    burden = target_profit + b.ad_spend + b.fixed_cost - b.other_income
    required = (
        max(0.0, burden) / e["unit_contribution"] if e["unit_contribution"] > 0 else (0.0 if burden <= 0 else None)
    )
    denominator = b.orders * (1 - b.returns) * (1 - b.discount) * (1 - b.payment_rate)
    price = (
        max(0.0, (burden + b.orders * b.variable_cost + b.orders * (1 - b.returns) * b.unit_cost) / denominator)
        if denominator
        else None
    )
    budget = e["contribution_profit"] - b.fixed_cost + b.other_income - target_profit
    return dict(
        target_profit=target_profit,
        required_orders=required,
        minimum_orders=math.ceil(required) if required is not None else None,
        required_price=price,
        maximum_ad_spend=budget if budget >= 0 else None,
    )


def acquisition_ceiling(
    b,
    expected_orders=1.0,
    extra_customer_cost=0.0,
    target_customer_profit=0.0,
    paid_new=450.0,
    other_acquisition=2000.0,
    actual_cac=44.44,
):
    nonnegative(
        expected_orders=expected_orders,
        extra_customer_cost=extra_customer_cost,
        target_customer_profit=target_customer_profit,
        paid_new=paid_new,
        other_acquisition=other_acquisition,
        actual_cac=actual_cac,
    )
    unit = economics(b)["unit_contribution"]
    available = unit * expected_orders - extra_customer_cost - target_customer_profit
    allowance = available if available >= 0 else None
    direct = allowance * paid_new - other_acquisition if allowance is not None and paid_new > 0 else None
    return dict(
        maximum_cac=allowance,
        maximum_direct_ad_spend=direct if direct is not None and direct >= 0 else None,
        contribution_in_horizon=unit * expected_orders,
        contribution_payback_orders=(actual_cac + extra_customer_cost) / unit if unit > 0 else None,
        cac_headroom=allowance - actual_cac if allowance is not None else None,
    )


def cash_runway(opening_cash, monthly_receipts, monthly_payments, buffer=0.0, months=12):
    nonnegative(
        opening_cash=opening_cash, monthly_receipts=monthly_receipts, monthly_payments=monthly_payments, buffer=buffer
    )
    if type(months) is not int or not 1 <= months <= 60:
        raise ValueError("Cash horizon must be 1..60 months")
    change = monthly_receipts - monthly_payments
    burn = -change
    rows = []
    for month in range(1, months + 1):
        opening = opening_cash + (month - 1) * change
        closing = opening + change
        rows.append(
            dict(
                month=month,
                opening_cash=opening,
                receipts=monthly_receipts,
                payments=monthly_payments,
                net_cash_flow=change,
                closing_cash=closing,
                below_buffer=closing < buffer,
            )
        )
    first_negative = math.floor(opening_cash / burn) + 1 if burn > 0 else (0 if opening_cash < 0 else None)
    buffer_breach = 0 if opening_cash < buffer else math.floor((opening_cash - buffer) / burn) + 1 if burn > 0 else None
    return pd.DataFrame(rows), dict(
        net_cash_flow=change,
        runway_months=opening_cash / burn if burn > 0 else None,
        first_negative_month=first_negative,
        first_buffer_breach_month=buffer_breach,
    )


def plan_actual(actual, plan, currency):
    if actual.empty or set(actual.columns) != set(ACTUAL_COLUMNS) or actual.isna().any().any():
        raise ValueError("Expected columns: " + ", ".join(ACTUAL_COLUMNS))
    actual = actual.copy()
    if not actual.period.astype(str).str.fullmatch(r"\d{4}-(0[1-9]|1[0-2])").all() or actual.period.duplicated().any():
        raise ValueError("Use unique calendar months YYYY-MM")
    if not actual.currency.eq(currency).all():
        raise ValueError("Actual and plan currencies must match")
    for key in ["revenue", "total_costs", "other_income"]:
        actual[key] = pd.to_numeric(actual[key], errors="raise")
        if not np.isfinite(actual[key]).all() or (actual[key] < 0).any():
            raise ValueError("Actual money values must be finite and nonnegative")
    if set(actual.period) - set(plan.period):
        raise ValueError("Actual months must belong to the selected plan horizon")
    joined = (
        plan[["period", "revenue", "operating_profit"]]
        .rename(columns={"revenue": "planned_revenue", "operating_profit": "planned_profit"})
        .merge(actual, on="period", how="left", validate="one_to_one")
    )
    joined["actual_profit"] = joined.revenue - joined.total_costs + joined.other_income
    joined["revenue_variance"] = joined.revenue - joined.planned_revenue
    joined["profit_variance"] = joined.actual_profit - joined.planned_profit
    joined["revenue_variance_rate"] = joined.revenue_variance / joined.planned_revenue.replace(0, np.nan)
    return joined


def risk_simulation(
    b,
    samples=1000,
    seed=42,
    price_spread=0.1,
    cost_spread=0.15,
    conversion_spread=0.2,
    cac_spread=0.2,
    elasticity=1.0,
    budget_factor=1.0,
    scale_penalty=0.25,
):
    if type(samples) is not int or not 100 <= samples <= 10000 or type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise ValueError("Use 100..10000 samples and an unsigned 32-bit seed")
    for spread in (price_spread, cost_spread, conversion_spread, cac_spread):
        if not math.isfinite(spread) or not 0 <= spread < 1:
            raise ValueError("Risk spreads must be in [0,1)")
    rng = np.random.default_rng(seed)
    draws = [
        rng.triangular(1 - spread, 1, 1 + spread, samples) if spread else np.ones(samples)
        for spread in (price_spread, cost_spread, conversion_spread, cac_spread)
    ]
    rows = []
    for i, values in enumerate(zip(*draws)):
        price, cost, conversion, cac = (float(v) for v in values)
        model = simulate(
            b,
            price_factor=price,
            cost_factor=cost,
            conversion_factor=conversion,
            cac_factor=cac,
            elasticity=elasticity,
            budget_factor=budget_factor,
            scale_penalty=scale_penalty,
            paid_share=0.6 if b.ad_spend else 0.0,
        )
        e = economics(model)
        rows.append(
            dict(
                draw=i + 1,
                price_factor=price,
                cost_factor=cost,
                conversion_factor=conversion,
                cac_factor=cac,
                orders=model.orders,
                revenue=e["revenue"],
                operating_profit=e["operating_profit"],
            )
        )
    frame = pd.DataFrame(rows)
    profit = frame.operating_profit
    return frame, dict(
        loss_frequency=float((profit < 0).mean()),
        profit_p10=float(profit.quantile(0.1)),
        profit_median=float(profit.median()),
        profit_p90=float(profit.quantile(0.9)),
        worst_sample=float(profit.min()),
        best_sample=float(profit.max()),
    )


def default_skus(b):
    rows = []
    for name, share, price, cost in [("Core", 0.6, 1.0, 1.0), ("Premium", 0.25, 1.4, 1.2), ("Entry", 0.15, 0.65, 0.8)]:
        model = replace(b, orders=b.orders * share, price=b.price * price, unit_cost=b.unit_cost * cost)
        rows.append(dict(sku=name, **{k: getattr(model, k) for k in SKU_COLUMNS if k != "sku"}))
    return pd.DataFrame(rows)


def promotion(b, discount=0.1, volume_lift=0.15, campaign_cost=0.0):
    """Compare a discount campaign and solve the volume needed to preserve baseline profit."""
    nonnegative(discount=discount, campaign_cost=campaign_cost)
    if discount > 1 or not math.isfinite(volume_lift) or volume_lift < -1:
        raise ValueError("Discount must be 0..1 and volume lift must be at least -1")
    model = replace(b, discount=discount, orders=b.orders * (1 + volume_lift), fixed_cost=b.fixed_cost + campaign_cost)
    current = economics(b)
    offer = economics(model)
    burden = current["operating_profit"] + model.ad_spend + model.fixed_cost - model.other_income
    unit = offer["unit_contribution"]
    required = max(0.0, burden) / unit if unit > 0 else (0.0 if burden <= 0 else None)
    return dict(
        baseline_profit=current["operating_profit"],
        campaign_profit=offer["operating_profit"],
        incremental_profit=offer["operating_profit"] - current["operating_profit"],
        campaign_revenue=offer["revenue"],
        campaign_orders=model.orders,
        campaign_unit_contribution=unit,
        required_orders_to_preserve_profit=required,
        required_volume_lift=required / b.orders - 1 if required is not None and b.orders > 0 else None,
        discount=discount,
        volume_lift=volume_lift,
        campaign_cost=campaign_cost,
    )
