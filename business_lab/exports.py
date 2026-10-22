"""Excel-friendly UTF-8 BOM CSV, formula-safe text, and reproducible export bundles."""

from io import BytesIO
import json
from zipfile import ZipFile, ZIP_DEFLATED
import pandas as pd
from .engine import economics, forecast


def csv_bytes(frame):
    frame = frame.copy()

    # Prevent text names/notes from becoming formulas when opened in a spreadsheet.
    def safe(value):
        if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
            return "'" + value
        return value

    for column in frame.columns:
        if frame[column].dtype == object or pd.api.types.is_string_dtype(frame[column].dtype):
            frame[column] = frame[column].map(safe)
    return frame.to_csv(index=False, lineterminator="\n").encode("utf-8-sig")


def scenario_table(b, saved):
    rows = []
    for name, model in [("Current baseline", b), *saved.items()]:
        rows.append(dict(scenario=name, currency=model.currency, period=model.period, **economics(model)))
    return pd.DataFrame(rows)


def bundle_tables(b, saved, extras=None, journal=None):
    tables = {
        "scenarios.csv": scenario_table(b, saved),
        "inputs.csv": pd.DataFrame(
            [dict(scenario="Current baseline", **b.dict()), *[dict(scenario=k, **v.dict()) for k, v in saved.items()]]
        ),
        "forecast_default.csv": pd.DataFrame(forecast(b, paid_share=0.6 if b.ad_spend else 0)).assign(
            currency=b.currency
        ),
    }
    for name, entry in (extras or {}).items():
        # Each export is tagged with the baseline that produced it, so stale analyses are not mislabelled.
        data = pd.DataFrame(entry["rows"])
        data["currency"] = entry["currency"]
        if "period" not in data:
            data["period"] = "month"
        tables[name + ".csv"] = data
    if journal is not None:
        tables["decision_journal.csv"] = pd.DataFrame(
            journal, columns=["id", "project_id", "created_at", "decision", "hypothesis", "next_step", "result"]
        )
    return tables


def export_zip(tables, manifest):
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name, table in tables.items():
            if "/" in name or "\\" in name or not name.endswith(".csv"):
                raise ValueError("Invalid export filename")
            archive.writestr(name, csv_bytes(table))
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False))
    return output.getvalue()
