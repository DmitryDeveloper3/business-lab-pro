from io import BytesIO, StringIO
import json
from zipfile import ZipFile
import pandas as pd
import pytest
from business_lab.models import Business
from business_lab.workspace import WorkspaceStore, capture, restore, parse_backup
from business_lab.exports import csv_bytes, bundle_tables, export_zip


def state():
    return dict(
        business=Business(),
        saved={"Decision": Business(price=140)},
        revision=0,
        appearance="dark",
        language="Русский",
        assumptions={"Decision": {"price_factor": 1.1667}},
        cash_inputs={"opening_cash": 1000, "monthly_receipts": 20, "monthly_payments": 40, "buffer": 100, "months": 12},
        cash_currency="USD",
    )


def test_sqlite_survives_new_store_and_updates_same_id(tmp_path):
    path = tmp_path / "data.sqlite3"
    first = WorkspaceStore(path)
    key = first.save("Retail", capture(state()))
    second = WorkspaceStore(path)
    assert second.list_projects()[0]["id"] == key
    assert second.load(key)["business"]["price"] == 120
    revised = state()
    revised["business"] = Business(price=130)
    second.save("Retail edited", capture(revised), key)
    assert len(second.list_projects()) == 1
    assert first.load(key)["business"]["price"] == 130


def test_journal_linkage_and_parameterized_strings(tmp_path):
    store = WorkspaceStore(tmp_path / "data.sqlite3")
    key = store.save("Retail '; DROP TABLE projects; --", capture(state()))
    store.add_decision(key, "Raise price", "Test demand", "2026-11-01", "Pending")
    assert WorkspaceStore(store.path).journal(key)[0]["decision"] == "Raise price"
    assert len(store.list_projects()) == 1
    with pytest.raises(ValueError):
        store.add_decision("missing", "Decision")
    with pytest.raises(ValueError):
        store.add_decision(key, "")


def test_backup_restores_models_and_clears_stale_outputs():
    original = state()
    payload = parse_backup(json.dumps(capture(original)))
    target = dict(business=Business(price=1), saved={}, revision=4, risk_seed=999, export_tables={"old": {}})
    restore(target, payload)
    assert target["business"] == original["business"]
    assert target["saved"] == original["saved"]
    assert target["cash_inputs"] == original["cash_inputs"]
    assert target["revision"] == 5
    assert "export_tables" not in target
    assert "risk_seed" not in target


@pytest.mark.parametrize("raw", ["{}", "null", "{invalid", '{"schema":"workspace-2"}'])
def test_bad_backups(raw):
    with pytest.raises(ValueError):
        parse_backup(raw)


def test_backup_cannot_inject_session_state():
    payload = capture(state())
    payload["tables"]["business"] = "bad"
    with pytest.raises(ValueError):
        parse_backup(json.dumps(payload))


def test_csv_bom_cyrillic_numeric_and_formula_safety():
    source = pd.DataFrame({"name": ["Мой товар", "=1+1", "@SUM(A1:A2)", " +2"], "profit": [10.0, -20.0, 0.0, None]})
    raw = csv_bytes(source)
    assert raw.startswith(b"\xef\xbb\xbf")
    frame = pd.read_csv(StringIO(raw.decode("utf-8-sig")))
    assert frame.name.iloc[0] == "Мой товар"
    assert frame.name.iloc[1] == "'=1+1"
    assert frame.profit.iloc[1] == -20
    assert pd.isna(frame.profit.iloc[-1])


def test_bundle_tables_keep_scenario_currencies_and_manifest():
    tables = bundle_tables(Business(), {"Решение": Business(currency="RUB")})
    assert set(tables["scenarios.csv"].currency) == {"USD", "RUB"}
    raw = export_zip(tables, {"schema": "csv-bundle-1", "note": "Допущения"})
    with ZipFile(BytesIO(raw)) as archive:
        assert set(archive.namelist()) == {*tables, "manifest.json"}
        assert json.loads(archive.read("manifest.json"))["note"] == "Допущения"
        assert archive.read("scenarios.csv").startswith(b"\xef\xbb\xbf")
    with pytest.raises(ValueError):
        export_zip({"../bad.csv": pd.DataFrame()}, {})


@pytest.mark.parametrize(
    "bad",
    [
        {"cash_inputs": {"opening_cash": -1, "monthly_receipts": 0, "monthly_payments": 0}},
        {"sku_input": [{"sku": "broken"}]},
        {"risk_inputs": {"price_spread": 2}},
        {"promotion_inputs": {"discount": 2}},
        {"planning_inputs": {"months": 60, "growth": 0.02}},
    ],
)
def test_nested_backup_validation(bad):
    payload = capture(state())
    payload["tables"].update(bad)
    with pytest.raises(ValueError):
        parse_backup(json.dumps(payload))


def test_csv_preserves_numeric_precision():
    value = 123456789.1234567
    frame = pd.read_csv(BytesIO(csv_bytes(pd.DataFrame({"value": [value]}))))
    assert frame.value.iloc[0] == pytest.approx(value, rel=1e-15)
