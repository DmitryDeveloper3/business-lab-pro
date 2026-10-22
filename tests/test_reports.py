import plotly.graph_objects as go
import pytest
from business_lab.models import Business
from business_lab.engine import simulate
from business_lab.i18n import translator, TEXT
from business_lab.report import report


@pytest.mark.parametrize("language", ["English", "Русский"])
def test_report_self_contained(language):
    b = Business()
    raw = report(b, simulate(b), [go.Figure(go.Bar(x=["One"], y=[10]))], translator(language), language == "Русский")
    assert "<html lang=" in raw
    assert "plotly.js" in raw.lower()
    assert "<script src=" not in raw
    assert "24,001.00" in raw
    assert ("ограничения" if language == "Русский" else "limitations") in raw
    assert ("Операционная прибыль" if language == "Русский" else "Operating profit") in raw


def test_translation_catalog_complete():
    assert all(len(pair) == 2 and all(pair) for pair in TEXT.values())
