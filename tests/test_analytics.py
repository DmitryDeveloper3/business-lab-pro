from dataclasses import replace
import pandas as pd
import pytest
from business_lab.models import Business
from business_lab.engine import economics, forecast
from business_lab.analytics import (
    default_skus,
    sku_economics,
    portfolio,
    goal,
    acquisition_ceiling,
    cash_runway,
    plan_actual,
    risk_simulation,
)


def test_single_sku_reconciles_to_company_contribution():
    b = Business()
    source = default_skus(b).iloc[:1].copy()
    source.loc[0, "orders"] = b.orders
    result = sku_economics(source, b.currency).iloc[0]
    assert result.contribution_profit == economics(b)["contribution_profit"]
    assert result.operating_profit == result.contribution_profit


@pytest.mark.parametrize("allocation", ["revenue", "orders"])
def test_portfolio_no_double_deduction(allocation):
    b = Business(other_income=100)
    rows, summary = portfolio(default_skus(b), b, allocation)
    assert rows.allocated_shared_costs.sum() == pytest.approx(b.ad_spend + b.fixed_cost)
    assert summary["operating_profit"] == pytest.approx(
        rows.contribution_profit.sum() - b.ad_spend - b.fixed_cost + b.other_income
    )


def test_empty_allocation_base_preserves_shared_costs():
    b = Business()
    data = default_skus(b)
    data["orders"] = 0
    rows, summary = portfolio(data, b)
    assert rows.allocated_shared_costs.sum() == 0
    assert summary["unallocated_costs"] == 33000
    assert summary["operating_profit"] == -33000


@pytest.mark.parametrize("bad", ["duplicate", "negative", "missing", "infinite", "rate"])
def test_invalid_skus(bad):
    data = default_skus(Business())
    if bad == "duplicate":
        data.loc[1, "sku"] = data.loc[0, "sku"]
    elif bad == "negative":
        data.loc[0, "price"] = -1
    elif bad == "missing":
        data = data.drop(columns="orders")
    elif bad == "rate":
        data.loc[0, "returns"] = 2
    else:
        data.loc[0, "orders"] = float("inf")
    with pytest.raises(ValueError):
        sku_economics(data, "USD")


def test_target_inverse_equations():
    b = Business()
    result = goal(b, 50000)
    assert economics(replace(b, orders=result["required_orders"]))["operating_profit"] == pytest.approx(50000)
    assert economics(replace(b, price=result["required_price"]))["operating_profit"] == pytest.approx(50000)
    assert economics(replace(b, orders=result["minimum_orders"]))["operating_profit"] >= 50000
    assert result["maximum_ad_spend"] is None


def test_target_infeasible_and_zero_demand():
    assert goal(Business(price=1), 1000)["required_orders"] is None
    assert goal(Business(orders=0), 1000)["required_price"] is None
    b = Business(other_income=100000)
    assert goal(b, 0)["minimum_orders"] == 0


def test_cac_ceiling_and_payback():
    b = Business()
    unit = economics(b)["unit_contribution"]
    result = acquisition_ceiling(
        b,
        expected_orders=2,
        extra_customer_cost=5,
        target_customer_profit=10,
        paid_new=100,
        other_acquisition=1000,
        actual_cac=30,
    )
    assert result["maximum_cac"] == pytest.approx(unit * 2 - 15)
    assert result["maximum_direct_ad_spend"] == pytest.approx((unit * 2 - 15) * 100 - 1000)
    assert result["contribution_payback_orders"] == pytest.approx(35 / unit)
    assert acquisition_ceiling(Business(price=1))["maximum_cac"] is None
    assert acquisition_ceiling(b, paid_new=0)["maximum_direct_ad_spend"] is None


def test_cash_independent_from_profit():
    rows, summary = cash_runway(100, 20, 50, buffer=40, months=6)
    assert summary["runway_months"] == pytest.approx(100 / 30)
    assert summary["first_negative_month"] == 4
    assert summary["first_buffer_breach_month"] == 3  # equality at month 2 is not below the reserve
    assert rows.closing_cash.iloc[-1] == -80
    assert cash_runway(100, 50, 20)[1]["runway_months"] is None
    assert cash_runway(10, 0, 0, buffer=20)[1]["first_buffer_breach_month"] == 0


def test_plan_actual_missing_is_not_zero():
    plan = pd.DataFrame(forecast(Business(), months=3))
    plan["period"] = ["2026-10", "2026-11", "2026-12"]
    actual = pd.DataFrame([dict(period="2026-10", currency="USD", revenue=100, total_costs=120, other_income=5)])
    result = plan_actual(actual, plan, "USD")
    assert result.actual_profit.iloc[0] == -15
    assert pd.isna(result.actual_profit.iloc[1])
    assert result.profit_variance.iloc[0] == -15 - plan.operating_profit.iloc[0]
    for invalid in [actual.assign(currency="RUB"), pd.concat([actual, actual]), actual.assign(period="2026-09")]:
        with pytest.raises(ValueError):
            plan_actual(invalid, plan, "USD")


def test_risk_repeatable_zero_spreads_match_baseline():
    b = Business()
    kwargs = dict(samples=100, price_spread=0, cost_spread=0, conversion_spread=0, cac_spread=0)
    frame, summary = risk_simulation(b, **kwargs)
    assert frame.operating_profit.eq(economics(b)["operating_profit"]).all()
    assert summary["profit_p10"] == summary["profit_p90"]
    a, _ = risk_simulation(b, samples=100, seed=123)
    c, _ = risk_simulation(b, samples=100, seed=123)
    pd.testing.assert_frame_equal(a, c)
    assert a.operating_profit.nunique() > 1


@pytest.mark.parametrize("kwargs", [{"samples": 0}, {"seed": -1}, {"price_spread": 1}, {"cost_spread": float("nan")}])
def test_invalid_risk(kwargs):
    with pytest.raises(ValueError):
        risk_simulation(Business(), **kwargs)


def test_promotion_inverse_volume_preserves_profit():
    from business_lab.analytics import promotion

    b = Business()
    result = promotion(b, discount=0.2, volume_lift=0.3, campaign_cost=500)
    required = result["required_orders_to_preserve_profit"]
    adjusted = replace(b, discount=0.2, orders=required, fixed_cost=b.fixed_cost + 500)
    assert economics(adjusted)["operating_profit"] == pytest.approx(economics(b)["operating_profit"])
    assert (
        result["campaign_profit"]
        == economics(replace(b, discount=0.2, orders=b.orders * 1.3, fixed_cost=b.fixed_cost + 500))["operating_profit"]
    )
    assert promotion(b, discount=1)["required_orders_to_preserve_profit"] is None


@pytest.mark.parametrize("kwargs", [{"discount": 1.1}, {"volume_lift": -1.1}, {"campaign_cost": -1}])
def test_invalid_promotion(kwargs):
    from business_lab.analytics import promotion

    with pytest.raises(ValueError):
        promotion(Business(), **kwargs)
