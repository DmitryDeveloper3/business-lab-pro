"""Public Streamlit deployment entry point; isolate local workspaces by visitor session."""

import os
from pathlib import Path
import runpy

os.environ["BUSINESS_LAB_PUBLIC_DEMO"] = "1"
runpy.run_path(str(Path(__file__).with_name("streamlit_app.py")), run_name="__main__")
