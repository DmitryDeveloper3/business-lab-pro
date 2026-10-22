from io import BytesIO
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import pandas as pd

from business_lab.excel import excel_bytes
from business_lab.exports import bundle_tables
from business_lab.models import Business


NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def test_excel_preserves_numbers_blanks_and_formula_like_names():
    frame = pd.DataFrame(
        {"scenario": ["=1+1", "@SUM(A1)", "Русский"], "profit": [-20.5, None, 0.0], "margin": [0.25, None, -0.1]}
    )
    with ZipFile(BytesIO(excel_bytes({"scenarios.csv": frame}, {"business": {"currency": "RUB"}}, "Русский"))) as z:
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
        assert not sheet.findall(".//s:f", NS)
        assert sheet.find(".//s:c[@r='B6']/s:v", NS).text == "-20.5"
        assert sheet.find(".//s:c[@r='B7']/s:v", NS) is None
        assert sheet.find(".//s:c[@r='B8']/s:v", NS).text == "0"
        assert sheet.find(".//s:c[@r='C6']/s:v", NS).text == "0.25"
        assert sheet.find(".//s:pane", NS).get("state") == "frozen"
        assert sheet.find(".//s:conditionalFormatting", NS) is not None
        table = ET.fromstring(z.read("xl/tables/table1.xml"))
        assert table.find("s:autoFilter", NS) is not None
        strings = z.read("xl/sharedStrings.xml").decode()
        assert "=1+1" in strings and "Русский" in strings
        assert "0.0%" in z.read("xl/styles.xml").decode()


def test_excel_real_bundle_and_empty_duplicate_sheet_names():
    tables = bundle_tables(Business(), {"Решение": Business(currency="RUB")})
    tables.update({"a/b.csv": pd.DataFrame(), "a:b.csv": pd.DataFrame({"id": []})})
    with ZipFile(BytesIO(excel_bytes(tables, {"notes": "Model snapshot"}))) as z:
        workbook = ET.fromstring(z.read("xl/workbook.xml"))
        names = [s.get("name") for s in workbook.find("s:sheets", NS)]
        assert len(names) == len(tables) + 2
        assert len({n.casefold() for n in names}) == len(names)
        assert all(len(n) <= 31 for n in names)
        assert z.testzip() is None


def test_overview_chart_excludes_foreign_currency_and_preserves_source_values():
    tables = bundle_tables(Business(), {"USD decision": Business(price=135), "EUR decision": Business(currency="EUR")})
    with ZipFile(BytesIO(excel_bytes(tables, {"business": Business().dict()}, "Русский"))) as z:
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
        assert sheet.find(".//s:c[@r='B6']/s:v", NS).text == "107160"
        assert sheet.find(".//s:c[@r='B9']/s:v", NS).text == "24001"
        chart = ET.fromstring(z.read("xl/charts/chart1.xml"))
        chart_ns = {"c": "http://schemas.openxmlformats.org/drawingml/2006/chart"}
        series = chart.findall(".//c:ser", chart_ns)
        assert len(series) == 2
        assert "EUR decision" not in z.read("xl/charts/chart1.xml").decode()
        assert sheet.find(".//s:hyperlinks", NS) is not None


def test_zero_fractional_orders_and_metadata_remain_readable():
    tables = {
        "forecast.csv": pd.DataFrame({"orders": [12.75, 0.0], "profit_margin": [0.25, 0.0], "profit": [None, -50.0]})
    }
    long_note = "Длинное пояснение " * 200
    with ZipFile(BytesIO(excel_bytes(tables, {"analysis": {"source": {"price": 120.25}}, "notes": long_note}))) as z:
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
        assert sheet.find(".//s:c[@r='A6']/s:v", NS).text == "12.75"
        assert sheet.find(".//s:c[@r='A7']/s:v", NS).text == "0"
        styles = ET.fromstring(z.read("xl/styles.xml"))
        formats = {n.get("numFmtId"): n.get("formatCode") for n in styles.findall("s:numFmts/s:numFmt", NS)}
        style = list(styles.find("s:cellXfs", NS))[int(sheet.find(".//s:c[@r='A6']", NS).get("s"))]
        assert ".00" in formats[style.get("numFmtId")]
        assert "—" not in z.read("xl/styles.xml").decode()
        strings = ET.fromstring(z.read("xl/sharedStrings.xml"))
        values = ["".join(si.itertext()) for si in strings]
        assert "analysis.source.price" in values
        metadata = ET.fromstring(z.read("xl/worksheets/sheet2.xml"))
        chunks = [
            values[int(cell.find("s:v", NS).text)]
            for cell in metadata.findall(".//s:c", NS)
            if cell.get("r").startswith("B") and cell.get("t") == "s" and int(cell.get("r")[1:]) >= 7
        ]
        assert long_note == "".join(chunks)
