from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"


@pytest.mark.parametrize("language", ["English", "Русский"])
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_new_workspaces(language, theme, tmp_path, monkeypatch):
    monkeypatch.setenv("BUSINESS_LAB_DATA_DIR", str(tmp_path))
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.selectbox(key="language").set_value(language).run()
    app.selectbox(key="appearance").set_value(theme).run()
    for page in ("products", "planning", "decisions", "risk", "projects", "reports"):
        app.radio(key="navigation_" + language).set_value(page).run()
        assert not app.exception, (page, app.exception)
    assert "download_selected_csv" in [button.key for button in app.get("download_button")]


def test_save_load_project_in_ui(tmp_path, monkeypatch):
    monkeypatch.setenv("BUSINESS_LAB_DATA_DIR", str(tmp_path))
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.radio(key="navigation_English").set_value("projects").run()
    app.button(key="save_project").click().run()
    assert not app.exception
    key = app.session_state["project_id"]
    app.radio(key="navigation_English").set_value("economics").run()
    app.number_input(key="econ_price_0").set_value(180)
    next(x for x in app.button if x.label == "Apply monthly model").click().run()
    assert app.session_state["business"].price == 180
    app.radio(key="navigation_English").set_value("projects").run()
    app.selectbox(key="stored_project").set_value(key)
    app.button(key="load_project").click().run()
    assert not app.exception
    assert app.session_state["business"].price == 120
    assert app.session_state["revision"] == 1


def test_restore_advanced_inputs_repopulates_controls(tmp_path, monkeypatch):
    monkeypatch.setenv("BUSINESS_LAB_DATA_DIR", str(tmp_path))
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.radio(key="navigation_English").set_value("planning").run()
    app.number_input(key="goals_target").set_value(45000).run()
    app.radio(key="navigation_English").set_value("decisions").run()
    app.number_input(key="cash_payments").set_value(12000).run()
    app.number_input(key="promo_lift").set_value(0.4).run()
    app.radio(key="navigation_English").set_value("projects").run()
    app.button(key="save_project").click().run()
    key = app.session_state["project_id"]
    app.radio(key="navigation_English").set_value("planning").run()
    app.number_input(key="goals_target").set_value(10000).run()
    app.radio(key="navigation_English").set_value("decisions").run()
    app.number_input(key="cash_payments").set_value(1000).run()
    app.radio(key="navigation_English").set_value("projects").run()
    app.selectbox(key="stored_project").set_value(key)
    app.button(key="load_project").click().run()
    assert not app.exception
    app.radio(key="navigation_English").set_value("planning").run()
    assert app.number_input(key="goals_target").value == 45000
    app.radio(key="navigation_English").set_value("decisions").run()
    assert app.number_input(key="cash_payments").value == 12000
    assert app.number_input(key="promo_lift").value == 0.4
    assert not app.exception
