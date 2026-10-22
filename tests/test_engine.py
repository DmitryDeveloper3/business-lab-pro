from dataclasses import replace
import math
import pytest
from business_lab.models import Business, Marketing
from business_lab.engine import economics, marketing, simulate, forecast
from business_lab.storage import dumps, loads, read_marketing
from io import StringIO
import pandas as pd
from dataclasses import asdict


def test_hand_worked_finance():
    b = Business(
        price=100,
        unit_cost=30,
        variable_cost=5,
        orders=100,
        returns=0.1,
        discount=0.2,
        payment_rate=0.025,
        ad_spend=1000,
        fixed_cost=2000,
        other_income=100,
    )
    e = economics(b)
    assert e["revenue"] == 7200
    assert e["cogs"] == 2700
    assert e["gross_profit"] == 4500
    assert e["payment_fees"] == 180
    assert e["contribution_profit"] == 3820
    assert e["operating_profit"] == 920
    assert e["total_costs"] == 6380
    assert e["break_even_orders"] == pytest.approx(2900 / 38.2)
    assert economics(replace(b, orders=e["break_even_orders"]))["operating_profit"] == pytest.approx(0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"orders": -1},
        {"returns": 1.01},
        {"price": float("nan")},
        {"ad_spend": float("inf")},
        {"discount": -0.1},
        {"price": True},
        {"currency": "XXX"},
        {"period": "year"},
    ],
)
def test_invalid_business(kwargs):
    with pytest.raises(ValueError):
        Business(**kwargs)


def test_zero_and_loss_allowed():
    e = economics(Business(orders=0))
    assert e["profit_margin"] is None
    assert e["profit_per_order"] is None
    assert e["operating_profit"] == -33000
    assert economics(Business(price=1))["break_even_orders"] is None
    assert economics(Business(returns=1))["revenue"] == 0
    assert economics(Business(discount=1))["revenue"] == 0


def test_no_double_count_and_monotonic():
    b = Business()
    e = economics(b)
    assert e["operating_profit"] == pytest.approx(e["revenue"] - e["total_costs"] + b.other_income)
    assert economics(replace(b, ad_spend=b.ad_spend + 100))["operating_profit"] == pytest.approx(
        e["operating_profit"] - 100
    )


def test_marketing_bases():
    e = marketing(Marketing())
    assert e["ctr"] == 0.03
    assert e["cpc"] == 1.5
    assert e["cpa"] == 18
    assert e["paid_cac"] == pytest.approx(20000 / 450)
    assert e["blended_cac"] == pytest.approx(20000 / 600)
    assert e["roas"] == pytest.approx(55000 / 18000)
    z = Marketing(**{key: 0 for key in asdict(Marketing())})
    assert all(v is None for v in marketing(z).values())


def test_invalid_funnel():
    with pytest.raises(ValueError):
        Marketing(clicks=500000)


def test_saturation_and_elasticity():
    b = Business()
    assert simulate(b) == b
    assert simulate(b, budget_factor=2).orders == pytest.approx(1360)
    assert simulate(b, budget_factor=2).orders < simulate(b, budget_factor=2, scale_penalty=0).orders
    assert simulate(b, price_factor=2, elasticity=2).orders == 250
    assert simulate(b, budget_factor=0).orders == 400
    with pytest.raises(ValueError):
        simulate(replace(b, ad_spend=0))


def test_forecast_consistency():
    b = Business()
    rows = forecast(b, 12, growth=0, cost_growth=0)
    assert len(rows) == 12
    assert all(r["operating_profit"] == economics(b)["operating_profit"] for r in rows)
    assert forecast(b)[0]["revenue"] == economics(b)["revenue"]
    assert all(math.isfinite(r["operating_profit"]) for r in forecast(b, growth=-0.9))


def test_scenario_roundtrip():
    b = Business(price=0, returns=1, currency="RUB")
    assert loads(dumps(b)) == b
    for raw in ("{}", "[]", "null", "{bad", dumps(b).replace('"schema": 1', '"schema": 2')):
        with pytest.raises(ValueError):
            loads(raw)


def csv_frame():
    return pd.DataFrame([dict(channel="Search", period="2026-10", currency="USD", **asdict(Marketing()))])


def test_csv_roundtrip():
    f = csv_frame()
    assert len(read_marketing(StringIO(f.to_csv(index=False)))) == 1


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "negative", "nan", "currency", "period", "text"])
def test_bad_csv(mutation):
    f = csv_frame()
    if mutation == "duplicate":
        f = pd.concat([f, f])
    elif mutation == "missing":
        f = f.drop(columns="clicks")
    elif mutation == "negative":
        f.loc[0, "ad_spend"] = -1
    elif mutation == "nan":
        f.loc[0, "ad_spend"] = float("nan")
    elif mutation == "currency":
        f.loc[0, "currency"] = "GBP"
    elif mutation == "period":
        f.loc[0, "period"] = "2026-13"
    else:
        f["clicks"] = "oops"
    with pytest.raises((ValueError, TypeError)):
        read_marketing(StringIO(f.to_csv(index=False)))
