#!/bin/zsh
set -eu
cd "${0:A:h}"
if [[ ! -x .venv/bin/python ]]; then
  echo "Create .venv with Python 3.14 and install requirements.txt first. See README_RU.md."
  read -r "?Press Enter to close."
  exit 1
fi
exec .venv/bin/python -m streamlit run streamlit_app.py --server.address 127.0.0.1
