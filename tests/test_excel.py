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
