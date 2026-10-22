"""Exercise actual Streamlit widgets and all page scripts without paid services."""

from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest


@pytest.mark.parametrize("language", ["English", "Русский"])
def test_all_pages(language):
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "streamlit_app.py", default_timeout=30).run()
    app.selectbox(key="language").set_value(language).run()
    for page in ["dashboard", "economics", "marketing", "scenarios", "breakeven", "forecast", "reports", "settings"]:
        app.radio(key="navigation_" + language).set_value(page).run()
        assert not app.exception, (page, app.exception)


def test_economics_edit_and_scenario_save():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "streamlit_app.py", default_timeout=30).run()
    app.radio(key="navigation_English").set_value("economics").run()
    app.number_input(key="econ_price_0").set_value(150)
    app.button[0]  # sidebar case button
    next(x for x in app.button if x.label == "Apply monthly model").click().run()
    assert app.session_state["business"].price == 150
    app.radio(key="navigation_English").set_value("scenarios").run()
    app.slider(key="s_budget_factor").set_value(2.0).run()
    next(x for x in app.button if x.label == "Save alternative to comparison").click().run()
    assert len(app.session_state["saved"]) == 1
    app.text_input[0].set_value("Second decision").run()
    app.slider(key="s_price_factor").set_value(1.2).run()
    next(x for x in app.button if x.label == "Save alternative to comparison").click().run()
    assert len(app.session_state["saved"]) == 2
    app.radio(key="navigation_English").set_value("reports").run()
    assert not app.exception


@pytest.mark.parametrize("case", ["store", "loss", "scale", "price"])
def test_load_cases(case):
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "streamlit_app.py", default_timeout=30).run()
    # Use the stable case widget key regardless of sidebar preferences.
    app.selectbox(key="demo_case").set_value(case)
    next(x for x in app.button if x.label == "Load case").click().run()
    assert not app.exception
    assert app.session_state["active_case"] == case


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_sidebar_currency_and_theme(mode):
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "streamlit_app.py", default_timeout=30).run()
    app.selectbox(key="appearance").set_value(mode).run()
    app.selectbox(key="currency_0").set_value("RUB").run()
    assert app.session_state["business"].currency == "RUB"
    assert app.session_state["business"].price == 120
    app.radio(key="navigation_English").set_value("economics").run()
    assert not app.exception
    assert any("RUB" in item.value for item in app.metric)
    app.selectbox(key="currency_1").set_value("EUR").run()
    assert app.session_state["business"].currency == "EUR"
    app.selectbox(key="demo_case").set_value("scale")
    next(x for x in app.button if x.label == "Load case").click().run()
    assert app.session_state["business"].currency == "USD"
    assert not app.exception
