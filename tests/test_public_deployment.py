from pathlib import Path
from uuid import uuid4
import pytest
from streamlit.testing.v1 import AppTest
from business_lab.models import Business
from business_lab.workspace import WorkspaceStore, public_session_path, capture


def test_public_workspaces_are_isolated(tmp_path):
    a = WorkspaceStore(public_session_path(uuid4().hex, root=tmp_path))
    b = WorkspaceStore(public_session_path(uuid4().hex, root=tmp_path))
    key = a.save("Private visitor model", capture(dict(business=Business(price=999), saved={})))
    assert a.load(key)["business"]["price"] == 999
    assert b.list_projects() == []
    with pytest.raises(ValueError):
        b.load(key)


@pytest.mark.parametrize("namespace", ["../shared", "", "a" * 31, "not-a-uuid"])
def test_invalid_public_namespace(namespace):
    with pytest.raises(ValueError):
        public_session_path(namespace)


def test_cloud_entrypoint_and_session_persistence(monkeypatch):
    monkeypatch.setenv("BUSINESS_LAB_PUBLIC_DEMO", "1")
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "cloud_app.py", default_timeout=30).run()
    app.radio(key="navigation_English").set_value("projects").run()
    assert not app.exception
    namespace = app.session_state["visitor_namespace"]
    app.button(key="save_project").click().run()
    assert not app.exception
    assert app.session_state["visitor_namespace"] == namespace
    app.radio(key="navigation_English").set_value("reports").run()
    assert not app.exception
