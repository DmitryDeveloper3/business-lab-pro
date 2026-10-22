# Public deployment

Repository: https://github.com/DmitryDeveloper3/business-lab-pro

Deployment target: Streamlit Community Cloud.

- Repository: `DmitryDeveloper3/business-lab-pro`
- Branch: `main`
- Entrypoint: `cloud_app.py`
- Python: 3.14 (the locally tested version; select it in Advanced settings)
- No paid API or secrets are required.

The public entrypoint isolates project storage by random visitor session. Public demo saves are temporary; download financial backups and decision-journal CSV before closing. Local execution through `Launch.command` retains the existing on-disk SQLite workflow.

Local `.venv`, `.local` databases, secrets and caches are excluded. Large self-contained HTML reports are generated locally with `python scripts/build_examples.py` rather than committed. All distributed examples and screenshots use synthetic data.

The Streamlit sign-in screen requires the account holder to accept its Terms of Service. Deployment must only be marked successful after the host build has passed and the resulting app URL responds. Repository publication alone is not a deployed Python website.

## Current verified state

- Complete source and examples published on GitHub.
- Linux/Python 3.14 CI passed: https://github.com/DmitryDeveloper3/business-lab-pro/actions/runs/39755510198 .
- Community Cloud deployment is pending account-holder sign-in and acceptance of Streamlit service terms.
- No live app URL has been verified yet.
