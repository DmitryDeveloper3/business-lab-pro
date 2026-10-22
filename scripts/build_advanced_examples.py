"""Generate explicitly synthetic CSV examples for the ten added workbench features."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from business_lab.models import Business
from business_lab.engine import forecast, simulate
from business_lab.analytics import (
    default_skus,
    sku_economics,
    portfolio,
    goal,
    acquisition_ceiling,
    cash_runway,
    plan_actual,
    risk_simulation,
    promotion,
)
from business_lab.exports import csv_bytes, bundle_tables, export_zip

b = Business()
root = Path(__file__).resolve().parents[1] / "examples"
products = default_skus(b)
portfolio_rows, portfolio_totals = portfolio(products, b)
cash, _ = cash_runway(50000, 80000, 95000, buffer=10000)
plan = pd.DataFrame(forecast(b, months=6))
plan["period"] = pd.period_range("2026-10", periods=6, freq="M").astype(str)
actual = pd.DataFrame(
    [
        dict(
            period=row.period,
            currency=b.currency,
            revenue=row.revenue * 0.9,
            total_costs=row.total_costs * 1.03,
            other_income=0.0,
        )
        for row in plan.iloc[:3].itertuples()
    ]
)
risk, risk_summary = risk_simulation(b, samples=1000, seed=42)
frames = dict(
    product_input=products,
    product_economics=sku_economics(products, b.currency),
    portfolio=portfolio_rows,
    portfolio_summary=pd.DataFrame([portfolio_totals]),
    cash_runway=cash,
    actual_input=actual,
    plan_actual=plan_actual(actual, plan, b.currency),
    profit_goal=pd.DataFrame([goal(b, 30000)]),
    acquisition_allowance=pd.DataFrame([acquisition_ceiling(b)]),
    risk_draws=risk,
    risk_assumptions_summary=pd.DataFrame([dict(samples=1000, seed=42, **risk_summary)]),
    promotion_viability=pd.DataFrame([promotion(b, discount=0.15, volume_lift=0.2, campaign_cost=1000)]),
)
extras = {
    key: dict(rows=frame.assign(data_kind="synthetic").to_dict("records"), currency=b.currency)
    for key, frame in frames.items()
}
tables = bundle_tables(b, {"Budget +25% (synthetic)": simulate(b, budget_factor=1.25)}, extras)
manifest = dict(
    schema="csv-bundle-1",
    data_kind="SYNTHETIC DEMONSTRATION ONLY",
    business=b.dict(),
    assumptions=dict(
        demand_growth=0.02,
        monthly_cogs_growth=0.01,
        paid_order_share=0.6,
        cac_saturation=0.25,
        cash_receipts=80000,
        cash_payments=95000,
        opening_cash=50000,
        cash_reserve=10000,
        actual_revenue_factor=0.9,
        actual_cost_factor=1.03,
        risk=dict(
            seed=42,
            samples=1000,
            price_spread=0.1,
            cost_spread=0.15,
            conversion_spread=0.2,
            cac_spread=0.2,
            elasticity=1.0,
            budget_factor=1.0,
        ),
    ),
    notes="Every example is synthetic; the CSV forecast is a deterministic model, not measured history. Cash is independent of operating profit.",
)
(root / "business_lab_example.csv").write_bytes(csv_bytes(tables["scenarios.csv"]))
(root / "business_lab_csv_examples.zip").write_bytes(export_zip(tables, manifest))
(root / "product_input.csv").write_bytes(csv_bytes(products))
(root / "actual_input.csv").write_bytes(csv_bytes(actual))
print(f"Generated synthetic example CSV, {len(tables)}-table ZIP and two import templates.")
