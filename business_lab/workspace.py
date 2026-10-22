"""Explicit local SQLite persistence, portable JSON backup and decision journal."""

from datetime import datetime, timezone
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from uuid import uuid4
from .models import Business, Marketing
from .analytics import promotion
from .analytics import sku_economics, plan_actual, cash_runway, risk_simulation, goal, acquisition_ceiling
import pandas as pd
import re


TABLE_KEYS = (
    "sku_input",
    "sku_currency",
    "actual_input",
    "actual_currency",
    "actual_start",
    "cash_inputs",
    "risk_inputs",
    "cash_currency",
    "goals_inputs",
    "acquisition_inputs",
    "planning_inputs",
    "promotion_inputs",
    "portfolio_driver",
)


def validate_payload(payload):
    if not isinstance(payload, dict) or payload.get("schema") != "workspace-1":
        raise ValueError("Unsupported workspace schema")
    Business(**payload["business"])
    if set(payload.get("tables", {})) - set(TABLE_KEYS):
        raise ValueError("Unknown workspace table key")
    if not isinstance(payload.get("assumptions", {}), dict) or not isinstance(payload.get("preferences", {}), dict):
        raise ValueError("Invalid workspace metadata")
    if not isinstance(payload.get("saved", {}), dict) or not isinstance(payload.get("tables", {}), dict):
        raise ValueError("Invalid workspace scenarios or tables")
    for name, fields in payload.get("saved", {}).items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Scenario names must be nonempty text")
        Business(**fields)
    if payload.get("marketing") is not None:
        Marketing(**payload["marketing"])
        if payload.get("marketing_currency") not in ("USD", "EUR", "RUB"):
            raise ValueError("Invalid marketing currency")
    tables = payload.get("tables", {})
    for key in ("sku_currency", "actual_currency", "cash_currency"):
        if key in tables and tables[key] not in ("USD", "EUR", "RUB"):
            raise ValueError("Invalid workspace table currency")
    if tables.get("portfolio_driver", "revenue") not in ("revenue", "orders"):
        raise ValueError("Invalid portfolio allocation driver")
    if "sku_input" in tables:
        sku_economics(pd.DataFrame(tables["sku_input"]), tables.get("sku_currency", payload["business"]["currency"]))
    if "actual_input" in tables:
        actual = pd.DataFrame(tables["actual_input"])
        if "period" not in actual:
            raise ValueError("Actual rows need periods")
        dummy_plan = pd.DataFrame({"period": actual.period, "revenue": 0.0, "operating_profit": 0.0})
        plan_actual(actual, dummy_plan, tables.get("actual_currency", payload["business"]["currency"]))
    if "actual_start" in tables and (
        not isinstance(tables["actual_start"], str)
        or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", tables["actual_start"])
    ):
        raise ValueError("Invalid plan start month")
    for key in (
        "cash_inputs",
        "risk_inputs",
        "goals_inputs",
        "acquisition_inputs",
        "planning_inputs",
        "promotion_inputs",
    ):
        if key in tables and not isinstance(tables[key], dict):
            raise ValueError("Invalid analysis input object")
    baseline = Business(**payload["business"])
    if "promotion_inputs" in tables:
        cfg = tables["promotion_inputs"]
        promotion(baseline, **cfg)
        if cfg.get("volume_lift", 0.15) > 5 or cfg.get("campaign_cost", 0) > 1e12:
            raise ValueError("Promotion inputs exceed editor range")
    if "cash_inputs" in tables:
        cfg = tables["cash_inputs"]
        cash_runway(**cfg)
        if not 3 <= cfg.get("months", 12) <= 36 or any(
            cfg.get(k, 0) > 1e12 for k in ("opening_cash", "monthly_receipts", "monthly_payments", "buffer")
        ):
            raise ValueError("Cash inputs exceed editor range")
    if "risk_inputs" in tables:
        cfg = tables["risk_inputs"]
        risk_simulation(baseline, **cfg)
        if (
            cfg.get("samples", 1000) not in (500, 1000, 3000, 5000)
            or any(cfg.get(k, 0) > 0.8 for k in ("price_spread", "cost_spread", "conversion_spread", "cac_spread"))
            or not 0 <= cfg.get("elasticity", 1) <= 4
            or not 0.1 <= cfg.get("budget_factor", 1) <= 3
            or not 0 <= cfg.get("scale_penalty", 0.25) <= 2
        ):
            raise ValueError("Risk inputs exceed editor range")
    if "goals_inputs" in tables:
        goal(baseline, **tables["goals_inputs"])
        if tables["goals_inputs"].get("target_profit", 0) > 1e12:
            raise ValueError("Goal exceeds editor range")
    if "acquisition_inputs" in tables:
        inputs = dict(tables["acquisition_inputs"])
        horizon = inputs.pop("horizon", "")
        if not isinstance(horizon, str) or len(horizon) > 4000:
            raise ValueError("Invalid purchase horizon text")
        acquisition_ceiling(baseline, **inputs)
        if inputs.get("expected_orders", 1) > 1000 or any(v > 1e12 for v in inputs.values()):
            raise ValueError("Acquisition inputs exceed editor range")
    if "planning_inputs" in tables:
        cfg = tables["planning_inputs"]
        if (
            set(cfg) != {"months", "growth"}
            or cfg["months"] not in (3, 6, 12)
            or not isinstance(cfg["growth"], (int, float))
            or not -0.9 <= cfg["growth"] <= 1
        ):
            raise ValueError("Invalid plan configuration")
    # JSON round-trip rejects non-finite values in nested metadata too.
    json.dumps(payload, allow_nan=False)
    return payload


def capture(state):
    marketing = state.get("marketing_data")
    return validate_payload(
        dict(
            schema="workspace-1",
            business=state["business"].dict(),
            saved={k: v.dict() for k, v in state.get("saved", {}).items()},
            assumptions=state.get("assumptions", {}),
            marketing=marketing.__dict__ if marketing else None,
            marketing_currency=state.get("marketing_currency"),
            marketing_period=state.get("marketing_period", "month"),
            tables={k: state[k] for k in TABLE_KEYS if k in state},
            preferences={k: state[k] for k in ("language", "appearance") if k in state},
        )
    )


def parse_backup(raw):
    try:
        return validate_payload(json.loads(raw))
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid workspace backup") from exc


def restore(state, payload):
    validate_payload(payload)
    state["business"] = Business(**payload["business"])
    state["saved"] = {k: Business(**v) for k, v in payload.get("saved", {}).items()}
    state["assumptions"] = payload.get("assumptions", {})
    for key in list(state):
        if (
            key in TABLE_KEYS
            or key.startswith(("editor_", "cash_", "risk_", "actual_", "goals_", "acq_", "promo_"))
            or key in ("marketing_data", "marketing_currency", "marketing_period", "export_tables")
        ):
            del state[key]
    if payload.get("marketing") is not None:
        state["marketing_data"] = Marketing(**payload["marketing"])
        state["marketing_currency"] = payload["marketing_currency"]
        state["marketing_period"] = payload.get("marketing_period", "month")
    state.update(payload.get("tables", {}))
    state["revision"] = state.get("revision", 0) + 1
    # Appearance/language remain the user's current UI choices; backup records them as provenance.


def public_session_path(namespace, root=None):
    if not isinstance(namespace, str) or not re.fullmatch(r"[0-9a-f]{32}", namespace):
        raise ValueError("Invalid visitor workspace namespace")
    return Path(root or Path(tempfile.gettempdir()) / "business_lab_public_sessions") / namespace / "workspace.sqlite3"


class WorkspaceStore:
    def __init__(self, path=None):
        if path is not None:
            self.path = Path(path)
        elif os.getenv("BUSINESS_LAB_PUBLIC_DEMO") == "1":
            # A random server-side session key prevents one visitor listing another's projects.
            # Never put session-dependent directories in os.environ: it is process-global.
            import streamlit as st

            namespace = st.session_state.setdefault("visitor_namespace", uuid4().hex)
            self.path = public_session_path(namespace)
        else:
            self.path = (
                Path(os.getenv("BUSINESS_LAB_DATA_DIR", Path(__file__).resolve().parents[1] / ".local"))
                / "workspace.sqlite3"
            )

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.executescript("""CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, payload TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS journal (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL, created_at TEXT NOT NULL,
            decision TEXT NOT NULL, hypothesis TEXT NOT NULL, next_step TEXT NOT NULL, result TEXT NOT NULL);""")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def list_projects(self):
        with self.connect() as con:
            return [
                dict(row) for row in con.execute("SELECT id,name,updated_at FROM projects ORDER BY updated_at DESC")
            ]

    def save(self, name, payload, project_id=None):
        if not isinstance(name, str) or not name.strip() or len(name) > 120:
            raise ValueError("Project name must contain 1..120 characters")
        validate_payload(payload)
        project_id = project_id or str(uuid4())
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.connect() as con:
            con.execute(
                "INSERT INTO projects VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,payload=excluded.payload,updated_at=excluded.updated_at",
                (project_id, name.strip(), json.dumps(payload, ensure_ascii=False, allow_nan=False), now),
            )
        return project_id

    def load(self, project_id):
        with self.connect() as con:
            row = con.execute("SELECT payload FROM projects WHERE id=?", (project_id,)).fetchone()
        if row is None:
            raise ValueError("Project not found")
        return parse_backup(row["payload"])

    def add_decision(self, project_id, decision, hypothesis="", next_step="", result=""):
        if not decision.strip() or any(len(v) > 4000 for v in (decision, hypothesis, next_step, result)):
            raise ValueError("Decision required; fields must not exceed 4000 characters")
        with self.connect() as con:
            if not con.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone():
                raise ValueError("Save or load a project before recording a decision")
            con.execute(
                "INSERT INTO journal VALUES(?,?,?,?,?,?,?)",
                (
                    str(uuid4()),
                    project_id,
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    decision.strip(),
                    hypothesis.strip(),
                    next_step.strip(),
                    result.strip(),
                ),
            )

    def journal(self, project_id):
        with self.connect() as con:
            return [
                dict(row)
                for row in con.execute(
                    "SELECT * FROM journal WHERE project_id=? ORDER BY created_at DESC", (project_id,)
                )
            ]
