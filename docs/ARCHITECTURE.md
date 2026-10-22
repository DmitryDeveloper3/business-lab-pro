# Architecture and accounting decisions

The UI orchestrates immutable models and pure functions. A Business instance is a monthly snapshot; scenario transforms produce a new instance, preserving the original. Streamlit session state holds the current baseline, saved alternatives, scenario drivers and the last valid marketing dataset. Calculation modules never access that state.

Validation is at the boundary: dataclasses reject invalid monetary/rate inputs; CSV ingestion enforces a strict single-month single-currency channel schema; scenario JSON requires a recognized version and exact fields. Economically adverse but legal values (cost above price, zero sales, 100% returns, losses) are allowed.

Financial results use Python double precision and round for display only. This is appropriate for scenario analysis, not payment settlement, a tax ledger or audited accounting. Fractional expected orders are permitted in forecasts; break-even additionally reports whole orders.

Contribution is before advertising. This separation makes the fixed-ad-budget break-even curve interpretable and avoids counting acquisition twice. The marketing ledger intentionally remains separate: attributed revenue may be a subset of company revenue, and acquisition customers differ from order counts. Channel screening applies a blended contribution ratio to net attributed revenue and subtracts measured acquisition costs; this proxy is explicitly caveated and does not allocate fixed company overhead.

Reports escape text, contain no arbitrary templates from uploads and embed Plotly once. Financial JSON is data only; no pickle or executable deserialization is used. Explicit local persistence uses SQLite; there is no backend account, outbound API or secret requirement. The ignored local database is shared by sessions on that installation; cloud persistence is not guaranteed. Streamlit serves the app locally or on Community Cloud.

Forecasts are deterministic transformations with compounded monthly factors. The baseline is month one, making baseline/forecast reconciliation testable. Sensitivity shocks one factor at a time around the custom alternative. It is not a causal estimate or probabilistic risk distribution. The selected demand elasticity can reverse the benefit of price increases; CAC saturation makes budget and demand nonlinear.

Extension path: add an explicitly typed business driver model and engine adapter for SaaS/service firms, then map its results to the shared KPI/report layer. Do not reuse the e-commerce order engine as subscription accounting without implementing revenue recognition, renewal and churn rules.

## Advanced workbench

`analytics.py` contains pure additional financial and cash models. `workbench.py` renders the new local workspaces. `workspace.py` serializes validated financial baselines, saved alternatives and analysis input objects to SQLite, with atomic parameterized queries and explicit connection cleanup. JSON restoration validates nested analytical inputs before modifying session state; widget keys and stale export tables are cleared so controls repopulate from restored values. Decision journal entries are attached to project UUIDs and remain separate from the model/input backup.

`exports.py` preserves numeric types, exports UTF-8 BOM CSV, escapes formula-like text and bundles files with machine-readable provenance. Each analysis export is associated with the source baseline and currency; the export center flags outputs generated from a different baseline. Product inputs and cash inputs preserve their currency and require explicit reset on currency mismatch. Shared advertising/overhead is subtracted once in portfolio totals; allocation by SKU is a management view, not a causal decision rule.

Cash uses explicit receipts and payments, not accrual operating profit. Risk sampling uses a seeded NumPy generator and independent triangular stress factors; these are hypothetical distributions, not calibrated real-world probabilities. Promo volume response is entered by the user; the inverse threshold uses contribution per order and additional campaign costs to preserve baseline operating profit.
