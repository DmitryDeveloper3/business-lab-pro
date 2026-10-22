"""Self-contained printable HTML; escaped text and inline Plotly JS."""

from html import escape
import pandas as pd
from .engine import economics, insights


def report(b, alternative, figures, t, ru=False, assumptions=None):
    e = economics(b)
    alt = economics(alternative)
    if b.currency != alternative.currency or b.period != alternative.period:
        raise ValueError("Reports require matching currencies and periods")
    units = [
        "%"
        if k in ("contribution_margin", "profit_margin")
        else ("заказы" if ru else "orders")
        if k in ("break_even_orders", "minimum_orders")
        else b.currency
        for k in e
    ]

    def formatted(value, key):
        if value is None:
            return t("na")
        return f"{value:.1%}" if key in ("contribution_margin", "profit_margin") else f"{value:,.2f}"

    table = pd.DataFrame(
        {
            "Metric" if not ru else "Показатель": [t(k) for k in e],
            t("base"): [formatted(e[k], k) for k in e],
            t("alternative"): [formatted(alt[k], k) for k in e],
            "Единица" if ru else "Unit": units,
        }
    )
    title = "Business decision report" if not ru else "Отчёт для принятия решений"
    summary = "Baseline operating profit" if not ru else "Операционная прибыль базового сценария"
    parts = [
        f'<!doctype html><html lang="{"ru" if ru else "en"}"><meta charset="utf-8"><title>BUSINESS LAB PRO</title>',
        "<style>body{font:15px system-ui;max-width:1100px;margin:40px auto;padding:20px;color:#172d35}table{border-collapse:collapse;width:100%}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left}h1,h2{color:#137d73}@media print{body{margin:0}.plotly-graph-div{break-inside:avoid}button{display:none}}</style>",
        f"<h1>BUSINESS LAB PRO · {title}</h1><p>{escape(t('model'))}</p>",
        f"<h2>{'Краткий вывод' if ru else 'Executive summary'}</h2><p>{summary}: {e['operating_profit']:,.2f} {b.currency}.</p>",
        f"<p>{'Альтернатива: операционная прибыль' if ru else 'Alternative operating profit'}: {alt['operating_profit']:,.2f} {b.currency}; {'изменение' if ru else 'change'}: {alt['operating_profit'] - e['operating_profit']:+,.2f} {b.currency}.</p>",
        table.to_html(index=False, float_format=lambda x: f"{x:,.4f}", na_rep=t("na"), escape=True),
        f"<h2>{'Исходные параметры' if ru else 'Input assumptions'}</h2>",
        pd.DataFrame({t("base"): b.dict(), t("alternative"): alternative.dict()}).rename(index=t).to_html(escape=True),
        f"<h2>{'Выводы и ограничения' if ru else 'Findings and limitations'}</h2>",
    ]
    for name, evidence, action in insights(b, ru):
        parts.append(f"<p><b>{escape(name)}</b>: {escape(evidence)}. {escape(action)}</p>")
    parts.extend(f"<p>{escape(t(k))}</p>" for k in ("limits", "formula", "scale_note"))
    parts.append(
        "<p>"
        + (
            "График прогноза: рост спроса 2% и себестоимости 1% в месяц, реклама и постоянные затраты без роста, без сезонности; горизонт 6 месяцев."
            if ru
            else "Forecast chart: 2% monthly demand growth, 1% monthly unit COGS growth, flat advertising and overhead, no seasonality; horizon 6 months."
        )
        + "</p>"
    )
    if assumptions:
        parts.append(pd.DataFrame({("Значение" if ru else "Value"): assumptions}).rename(index=t).to_html(escape=True))
    else:
        parts.append(
            "<p>"
            + (
                "Альтернатива импортирована как готовая финансовая модель; исходные зависимости спроса неизвестны."
                if ru
                else "Alternative is a realized financial scenario; its original demand response assumptions are unavailable."
            )
            + "</p>"
        )
    for i, fig in enumerate(figures):
        parts.append(fig.to_html(full_html=False, include_plotlyjs=True if i == 0 else False))
    parts.append("</html>")
    return "\n".join(parts)
