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
- Public app verified running on 2026-10-22: https://cloudapppy-olp4fpzzp6rp6t8ty6uacf.streamlit.app/
- Community Cloud build completed with Python 3.14.8. Russian interface, RUB selection, dark theme and the CSV export screen were verified in the live app.
- The host automatically replaced pyarrow 26.0.0 with 24.0.0 during provisioning as a platform compatibility safeguard.

## Excel export

Reports & Export includes a formatted XLSX snapshot with an overview, separate native tables, filters, frozen headers, percentage formats and per-analysis provenance. XlsxWriter is a pinned runtime dependency. User text is never evaluated as formulas. 101 local tests passed after the final review; the downloaded public workbook was checked as a valid XLSX archive.

The final polish adds selected-table XLSX, a same-currency profit chart, linked workbook contents, explicit zeros, decimal forecast orders and improved dark-theme contrast. See QA.md for verification scope.
