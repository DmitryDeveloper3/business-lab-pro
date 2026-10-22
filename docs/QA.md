# Verification record — 2026-10-22 (Europe/Moscow)

## Verified locally

- macOS Apple Silicon, Python 3.14.8, isolated `.venv`.
- Installed Streamlit 1.66.1, pandas 3.0.6, NumPy 2.5.4, Plotly 7.1.0, pytest 9.1.1 and Ruff 0.17.1. Exact complete installation is pinned in `requirements.txt`.
- **97 pytest tests pass**, including original financial/marketing checks and advanced workbench models. All thirteen pages are executed through AppTest in English and Russian; the six relevant advanced/export pages also run in light and dark appearance. Tests cover changing financial inputs, saving decisions, loading all four cases, persistent SQLite saves and restoring advanced inputs into widgets.
- Ruff lint, Ruff formatting check and `pip check` pass.
- Standard `python -m streamlit run streamlit_app.py` server started successfully on loopback port 8501. The app was loaded and exercised through an actual browser.
- Browser CSV upload: `examples/marketing.csv` loaded two channel rows for 2026-10, showed KPI calculations and channel screening.
- Browser JSON upload: `examples/scale.json` imported into saved comparisons alongside the current baseline.
- Browser HTML export: the Russian report downloaded successfully; the 4,842,768-byte file contained a Russian executive summary, three Plotly charts and no external script imports. Generated report size can vary with inputs/Plotly updates.
- English and Russian UI and native Light/Dark theme selection verified visually. Explicit light/dark configurations are supplied; the switch is in the top-right main menu (no legacy Settings submenu).
- Responsive views checked at the actual narrow in-app viewport (319 px) and an explicit laptop breakpoint (1366×900). KPI font sizing was corrected after detecting truncation. Screenshots are real browser captures, not mockups.
- JSON round-trip, malformed schema, boolean version, invalid inputs, duplicate rows, mixed months/currencies, missing columns, NaN, infinity and zero denominators are covered.
- Hand-worked financial reconciliation confirms 100 orders × 100 price with 10% returns, 20% discount, 30 COGS, 5 processing, 2.5% fee, 1,000 ads, 2,000 overhead and 100 other income produces 7,200 net revenue and **920 operating profit**.
- Synthetic base store produces **107,160 net revenue**, **57,001 contribution profit** and **24,001 operating profit**. Scaling case doubles ads with CAC saturation and reduces operating profit from **16,001** to **14,521.36**, demonstrating that scaling does not guarantee profitability.
- All example scenarios, case-results CSV and self-contained English/Russian reports rebuild via `python scripts/build_examples.py`.
- Git repository is scoped to this project. Source publication is prepared for `DmitryDeveloper3/business-lab-pro`; hosting verification is tracked separately in `docs/DEPLOYMENT.md`.

## Remaining verification limits

- GitHub Actions on Linux/Python 3.14 passed for published commit 4566f19cee556589036a2fed0711ee39369530e1. Streamlit Community Cloud and other Python minor versions have not yet been verified.
- No load/stress, accessibility audit, penetration test or multi-browser/mobile-device matrix was performed. Narrow viewport checks are not equivalent to testing real mobile hardware.
- HTML generation and download are verified; physical printing/page breaks across browsers and automatic PDF export are not verified. No automatic PDF feature is offered.
- Finder double-click handling of `Launch.command` can depend on macOS terminal/file association settings; the underlying standard Streamlit command was verified.
- No real business data, identity-level attribution, causal elasticity, observed seasonality, tax, inventory timing, capacity, LTV or cohort model is validated. Cash projections use explicit hypothetical receipts/payments; Monte Carlo factors are synthetic distributions, not calibrated real-world probabilities.
- Customer identity cannot be deduplicated from aggregate CSV input; the uploader must supply channel-disjoint counts or interpret sums appropriately.
- Unsaved scenarios persist in the session only. Explicit project saves preserve models, alternatives, assumptions and analysis inputs in local SQLite. Model/input JSON backups exclude the separately exported decision journal. Local database storage is shared by installation and cloud disk persistence is not guaranteed.

## Screenshots

- `dashboard_desktop.png` — light theme, laptop breakpoint, corrected KPI sizing.
- `dashboard_dark.png` — native dark theme, laptop breakpoint.
- `dashboard_ru_dark.png` — Russian dashboard in dark theme.
- `dashboard_narrow.png` — initial narrow-screen responsive card layout.

The temporary test server is stopped after QA. Run `Launch.command` or the documented CLI to start your own session.

## Sidebar preference update

Added persistent-in-session sidebar selectors for USD/EUR/RUB and light/dark appearance. Verified changing USD → RUB → EUR without changing price, navigating to economics and reloading a USD demo case. Financial formulas are unchanged. Saved scenarios retain currency. Theme styles are scoped to the browser session; chart templates and table cells follow the chosen palette. The original native theme remains available for Streamlit-owned chrome.

## Ten advanced functions and CSV export (v1.1)

Verified additions: local project persistence, decision journal, SKU economics, portfolio/shared-cost allocation, target-profit inverse calculations, calendar-month plan/actual comparison, acquisition allowance, cash reserve/runway, seeded risk stress test and discount-campaign viability. No dependency was added.

- Original financial core remains unchanged. Single-SKU contribution reconciles to its company model; portfolio totals subtract shared ads/overhead once, including the zero-allocation-base case.
- Inverse goal and promotion-volume calculations are checked by substituting the result into the financial engine. CAC allowance uses contribution and an explicit purchase horizon rather than fabricated LTV.
- Cash tests distinguish accrual profit from receipts/payments and verify reserve breach, negative balance and no-depletion cases. Missing actual months stay NaN/N/A instead of becoming zero.
- Risk tests verify deterministic seeds, zero-spread baseline identity, sample quantiles and invalid parameters. Distributions are independent triangular assumptions; no predictive probability claim is made.
- SQLite tests reopen the database through a new store instance, update one project UUID, validate journal linkage and prove names/notes are parameterized rather than executed as SQL.
- Backup validation checks nested table/analysis inputs before state mutation. UI tests save, alter and restore price, profit targets, cash payments and promo uplift; stale output tables and widget state are cleared.
- CSV tests cover UTF-8 BOM, Cyrillic, numeric precision, negative numbers, undefined values, escaping formula-like text, preserved scenario currencies, ZIP contents and a JSON manifest.
- Actual browser QA used a separate temporary SQLite database. A synthetic project was saved; a decision was recorded; product portfolio and risk screens rendered successfully. The portfolio example showed 112,250.10 revenue, 61,174.25 contribution and 28,174.25 operating profit after shared costs.
- The CSV export center was exercised through the browser. `scenarios.csv` downloaded (495 bytes), contained a UTF-8 BOM, one USD baseline row and operating profit 24,001.00. The generated example ZIP passed archive integrity checks and contains 15 CSV tables plus manifest.json.
- Actual screenshots: `portfolio_v11.png` and `csv_export_v11.png`. Example artifacts rebuild using `python scripts/build_advanced_examples.py`.

Remaining limits: the complete ZIP was checked programmatically, while the individual CSV was also downloaded in the browser. New product/actual CSV parsers and model/input JSON restore are covered by automation; every malformed-file case has not been replayed manually in the browser. Cloud persistence, multi-user isolation, real business inputs and production security/load testing are not verified. The existing disclosure about shared local storage applies.

## Public deployment preparation

Added `cloud_app.py` as the Community Cloud entrypoint. It enables visitor-session-specific workspace storage without changing the local workflow. Six additional tests verify cross-session isolation, invalid namespace rejection and actual AppTest execution/save/export through the cloud entrypoint. All 97 tests pass locally. Runtime/CI verification on the public host is separate; no successful website deployment is claimed from these local checks alone.

## GitHub publication verification

The complete source is public at https://github.com/DmitryDeveloper3/business-lab-pro . Because the GitHub integration denied writes and local Git had no saved authentication, the audited files were uploaded through the already authenticated GitHub web interface. A public Git fetch verified byte-for-byte content equality with the locally tested files; only `Launch.command` lost its executable bit through web upload, so the README documents `zsh Launch.command` / `chmod +x`.

GitHub Actions run https://github.com/DmitryDeveloper3/business-lab-pro/actions/runs/39755510198 completed successfully on Linux with Python 3.14: dependency installation, `pip check`, Ruff lint/format and pytest all passed. Website deployment remains pending the account holder's Streamlit sign-in and acceptance of service terms. A source repository URL is not claimed as a live application URL.
