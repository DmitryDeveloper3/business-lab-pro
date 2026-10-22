"""Strict, versioned scenario persistence and channel-period CSV validation."""

from dataclasses import asdict
import json
import pandas as pd
from .models import Business, Marketing

SCHEMA = 1


def dumps(b: Business):
    return json.dumps({"schema": SCHEMA, "business": asdict(b)}, ensure_ascii=False, indent=2, allow_nan=False)


def loads(raw):
    try:
        data = json.loads(raw)
        if (
            not isinstance(data, dict)
            or set(data) != {"schema", "business"}
            or type(data["schema"]) is not int
            or data["schema"] != SCHEMA
        ):
            raise ValueError("Unsupported scenario schema")
        if set(data["business"]) != set(asdict(Business())):
            raise ValueError("Scenario fields are missing or unknown")
        return Business(**data["business"])
    except (TypeError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid scenario JSON") from exc


def read_marketing(source):
    frame = pd.read_csv(source)
    required = ["channel", "period", "currency", *asdict(Marketing()).keys()]
    if set(frame.columns) != set(required) or frame.empty:
        raise ValueError("CSV must contain exactly: " + ", ".join(required))
    if frame.isna().any().any() or frame.duplicated(["channel", "period", "currency"]).any():
        raise ValueError("Missing values or duplicate channel-period rows")
    if frame.currency.nunique() != 1 or frame.currency.iloc[0] not in ("USD", "EUR", "RUB"):
        raise ValueError("Use one supported currency per file")
    if not frame.period.astype(str).str.fullmatch(r"\d{4}-(0[1-9]|1[0-2])").all() or frame.period.nunique() != 1:
        raise ValueError("Use one calendar month, YYYY-MM")
    if frame.channel.astype(str).str.strip().eq("").any():
        raise ValueError("Channel cannot be blank")
    for key in asdict(Marketing()):
        frame[key] = pd.to_numeric(frame[key], errors="raise")
    for _, row in frame.iterrows():
        Marketing(**{key: row[key] for key in asdict(Marketing())})
    return frame
