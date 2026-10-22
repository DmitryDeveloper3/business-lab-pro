"""Rebuild reproducible, synthetic portfolio artifacts from the financial engine."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
import plotly.express as px
from dataclasses import asdict
from business_lab.cases import CASES
from business_lab.engine import economics, forecast, simulate
from business_lab.i18n import translator
from business_lab.models import Marketing
from business_lab.report import report
from business_lab.storage import dumps

root = Path(__file__).resolve().parents[1] / "examples"
root.mkdir(exist_ok=True)
for key, case in CASES.items():
    (root / f"{key}.json").write_text(dumps(case["business"]), encoding="utf-8")
channels = []
for channel, share in [("Search", 0.6), ("Social", 0.4)]:
    channels.append(
        dict(
            channel=channel, period="2026-10", currency="USD", **{k: v * share for k, v in asdict(Marketing()).items()}
        )
    )
pd.DataFrame(channels).to_csv(root / "marketing.csv", index=False)
rows = []
for key, case in CASES.items():
    base = economics(case["business"])
    alternate = economics(simulate(case["business"], **case["decision"]))
    rows.append(
        dict(
            case=key,
            baseline_profit=base["operating_profit"],
            decision_profit=alternate["operating_profit"],
            delta=alternate["operating_profit"] - base["operating_profit"],
        )
    )
pd.DataFrame(rows).to_csv(root / "case_results.csv", index=False)
b = CASES["store"]["business"]
a = simulate(b, budget_factor=1.25)
for lang in ("English", "Русский"):
    t = translator(lang)
    trend = pd.DataFrame(forecast(b)).rename(columns=t)
    fig = px.line(
        trend,
        x=t("month"),
        y=[t("revenue"), t("operating_profit")],
        title="Модельный прогноз · USD" if lang == "Русский" else "Model forecast · USD",
    )
    fig.update_layout(yaxis_title="USD", legend_title_text="")
    comparison = pd.DataFrame({t("base"): economics(b), t("alternative"): economics(a)}).T
    compare = px.bar(comparison, y=["revenue", "operating_profit"])
    compare.for_each_trace(lambda trace: trace.update(name=t(trace.name)))
    compare.update_layout(yaxis_title="USD", xaxis_title=t("base"), legend_title_text="")
    filename = "report_ru.html" if lang == "Русский" else "report_en.html"
    (root / filename).write_text(
        report(
            b,
            a,
            [fig, compare],
            t,
            lang == "Русский",
            dict(budget_factor=1.25, scale_penalty=0.25, elasticity=0, paid_share=0.6),
        ),
        encoding="utf-8",
    )
print("Generated four scenario JSON files, marketing CSV, case results and two self-contained HTML reports.")
