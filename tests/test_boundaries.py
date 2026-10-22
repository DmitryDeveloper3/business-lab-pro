from dataclasses import replace
from io import StringIO
import json
import pytest
from business_lab.models import Business
from business_lab.engine import economics, forecast, simulate
from business_lab.storage import dumps, loads, read_marketing
from business_lab.report import report
from business_lab.i18n import translator


def test_full_return_processing_remains():
    e = economics(Business(returns=1, orders=100, variable_cost=7))
    assert e["revenue"] == e["cogs"] == e["payment_fees"] == 0
    assert e["contribution_profit"] == -700
    assert e["break_even_orders"] is None


def test_flat_zero_cost_break_even():
    e = economics(Business(price=0, unit_cost=0, variable_cost=0, ad_spend=0, fixed_cost=0))
    assert e["break_even_orders"] == 0
    assert e["operating_profit"] == 0


def test_zero_ad_baseline_organic_forecast():
    b = Business(ad_spend=0)
    assert simulate(b, paid_share=0, budget_factor=2).orders == b.orders
    assert len(forecast(b, paid_share=0)) == 6


@pytest.mark.parametrize("options", [{"months": 5}, {"growth": -1}, {"seasonality": 1}, {"cost_growth": float("nan")}])
def test_invalid_forecast(options):
    with pytest.raises(ValueError):
        forecast(Business(), **options)


def test_schema_boolean_rejected():
    data = json.loads(dumps(Business()))
    data["schema"] = True
    with pytest.raises(ValueError):
        loads(json.dumps(data))


def test_report_rejects_currency_mismatch():
    with pytest.raises(ValueError):
        report(Business(), replace(Business(), currency="RUB"), [], translator("English"))


def test_csv_rejects_mixed_periods_and_currencies():
    from pathlib import Path

    raw = (Path(__file__).resolve().parents[1] / "examples/marketing.csv").read_text()
    for bad in (
        raw.replace("Social,2026-10", "Social,2026-11"),
        raw.replace("Social,2026-10,USD", "Social,2026-10,EUR"),
    ):
        with pytest.raises(ValueError):
            read_marketing(StringIO(bad))
