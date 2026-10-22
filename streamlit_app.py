"""BUSINESS LAB PRO — local-first, transparent e-commerce decision support."""

from dataclasses import asdict, replace
from io import StringIO
import json
import math
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from business_lab.models import Business, Marketing
from business_lab.engine import economics, marketing, simulate, sensitivity, forecast, insights
from business_lab.cases import CASES
from business_lab.i18n import translator
from business_lab.storage import dumps, loads, read_marketing
from business_lab.report import report
from business_lab.appearance import css as appearance_css, palette
from business_lab.workbench import render_workbench, render_export_center
from business_lab.exports import csv_bytes, scenario_table

st.set_page_config(page_title="BUSINESS LAB PRO", page_icon="◈", layout="wide")
if "business" not in st.session_state:
    st.session_state.business = Business()
    st.session_state.saved = {}
    st.session_state.revision = 0

lang = st.sidebar.selectbox("Language / Язык", ["English", "Русский"], key="language")
ru = lang == "Русский"
t = translator(lang)


def L(en, rus):
    return rus if ru else en


st.sidebar.markdown("## ◈ BUSINESS LAB PRO")
mode = st.sidebar.selectbox(
    L("Theme", "Тема"),
    ["light", "dark"],
    format_func=lambda value: {"light": L("Light", "Светлая"), "dark": L("Dark", "Тёмная")}[value],
    key="appearance",
)
st.markdown(appearance_css(mode), unsafe_allow_html=True)
colors = palette(mode)
current_business = st.session_state.business
currency = st.sidebar.selectbox(
    L("Currency", "Валюта"),
    ["USD", "EUR", "RUB"],
    index=["USD", "EUR", "RUB"].index(current_business.currency),
    key=f"currency_{st.session_state.revision}",
)
if currency != current_business.currency:
    st.session_state.business = replace(current_business, currency=currency)
    st.session_state.revision += 1
    st.rerun()
st.sidebar.caption(L("Currency labels only · no exchange-rate conversion", "Валюта сумм · без пересчёта по курсу"))
st.sidebar.caption(L("DECISION INTELLIGENCE / E-COMMERCE", "АНАЛИТИКА РЕШЕНИЙ / E-COMMERCE"))
pages = [
    "dashboard",
    "economics",
    "marketing",
    "scenarios",
    "breakeven",
    "forecast",
    "products",
    "planning",
    "decisions",
    "risk",
    "projects",
    "reports",
    "settings",
]
page = st.sidebar.radio(
    L("Workspace", "Рабочая область"),
    pages,
    format_func=t,
    index=pages.index(st.session_state.get("current_page", "dashboard")),
    key="navigation_" + lang,
)
st.session_state.current_page = page
st.sidebar.download_button(
    L("Download scenario CSV", "Скачать CSV сценариев"),
    csv_bytes(scenario_table(st.session_state.business, st.session_state.saved)),
    "business_scenarios.csv",
    "text/csv",
    key="sidebar_csv",
    width="stretch",
)
case_id = st.sidebar.selectbox(
    L("Synthetic business case", "Демонстрационный кейс"),
    list(CASES),
    format_func=lambda k: CASES[k]["ru" if ru else "en"],
    key="demo_case",
)
if st.sidebar.button(L("Load case", "Загрузить кейс"), width="stretch"):
    st.session_state.business = CASES[case_id]["business"]
    st.session_state.revision += 1
    st.session_state.active_case = case_id
    st.rerun()

b = st.session_state.business
e = economics(b)
case = CASES[st.session_state.get("active_case", "store")]
# Zero baseline advertising cannot identify a paid acquisition response.
paid_default = 0.6 if b.ad_spend else 0.0
alternative = simulate(b, budget_factor=1.25, paid_share=paid_default)
a = economics(alternative)

st.markdown(
    """<style>
.block-container{padding-top:4rem;max-width:1500px}
[data-testid="stMetric"]{border:1px solid #7f98952e;border-radius:12px;padding:16px;background:#718c870a}
[data-testid="stMetricLabel"]{font-size:.78rem;letter-spacing:.02em}
[data-testid="stMetricValue"],[data-testid="stMetricValue"]>div{font-size:clamp(1.1rem,1.65vw,1.6rem);white-space:normal;overflow:visible;text-overflow:clip;line-height:1.3}
h1{letter-spacing:-.04em}h2{letter-spacing:-.025em}
[data-testid="stSidebar"]{border-right:1px solid #7f98952e}
@media(max-width:700px){.block-container{padding:4rem 1rem 1rem}[data-testid="stMetric"]{padding:10px}}
</style>""",
    unsafe_allow_html=True,
)
st.caption(t("model"))
st.title(t(page))
st.caption(L("Understand the economics. Make the decision.", "Понимайте экономику. Принимайте решения."))


def fmt(v, percent=False, money=True):
    if v is None or not math.isfinite(v):
        return t("na")
    if percent:
        return f"{v:.1%}"
    return f"{v:,.2f}" + (f" {b.currency}" if money else "")


def metrics(data, keys, compare=None):
    for offset in range(0, len(keys), 4):
        columns = st.columns(min(4, len(keys) - offset))
        for col, key in zip(columns, keys[offset : offset + 4]):
            pct = key in ("profit_margin", "contribution_margin", "ctr", "visitor_to_lead", "lead_to_customer")
            money = key not in ("break_even_orders", "minimum_orders", "roas")
            delta = None
            if compare and data[key] is not None and compare[key] is not None:
                delta = fmt(data[key] - compare[key], pct, money)
            col.metric(t(key), fmt(data[key], pct, money), delta)


def show_table(data, **kwargs):
    styled = data.style if isinstance(data, pd.DataFrame) else data
    st.dataframe(styled.set_properties(**{"background-color": colors["surface"], "color": colors["text"]}), **kwargs)


def show_chart(fig, **kwargs):
    fig.update_layout(
        template="plotly_dark" if mode == "dark" else "plotly_white",
        paper_bgcolor=colors["background"],
        plot_bgcolor=colors["background"],
        font_color=colors["text"],
    )
    st.plotly_chart(fig, theme=None, **kwargs)


def chart(fig, title, y_money=True):
    fig.update_layout(
        title=title,
        font=dict(family="Arial, sans-serif"),
        margin=dict(l=12, r=12, t=55, b=30),
        legend_title_text="",
        colorway=["#168779", "#627de3", "#e4a849", "#d26363"],
        yaxis_title=b.currency if y_money else None,
    )
    return fig


def trend_fig(rows):
    df = pd.DataFrame(rows).rename(columns=t)
    return chart(
        px.line(df, x=t("month"), y=[t("revenue"), t("operating_profit")], markers=True),
        L("Modelled revenue & profit · not historical data", "Модельная выручка и прибыль · не история"),
    )


def expenses_fig():
    keys = ["cogs", "variable_costs", "payment_fees", "marketing_spend"]
    df = pd.DataFrame(
        {
            L("Cost", "Расход"): [t(k) for k in keys] + [t("fixed_cost")],
            b.currency: [e[k] for k in keys] + [b.fixed_cost],
        }
    )
    return chart(
        px.bar(df, x=b.currency, y=L("Cost", "Расход"), orientation="h"),
        L("Operating cost structure", "Структура операционных расходов"),
        False,
    )


def comparison_fig(models):
    rows = [
        {L("Scenario", "Сценарий"): name, **{t(key): economics(model)[key] for key in ("revenue", "operating_profit")}}
        for name, model in models.items()
    ]
    return chart(
        px.bar(
            pd.DataFrame(rows), x=L("Scenario", "Сценарий"), y=[t("revenue"), t("operating_profit")], barmode="group"
        ),
        L("Decision comparison", "Сравнение решений"),
    )


def show_insights(model):
    findings = insights(model, ru)
    for title, evidence, action in findings:
        st.warning(f"**{title} · {evidence}**\n\n{action}")
    if not findings:
        st.success(
            L(
                "Positive operating economics under current assumptions. This does not prove demand or eliminate risk.",
                "При текущих допущениях операционная экономика положительна. Это не доказывает спрос и не устраняет риски.",
            )
        )
    st.info(t("scale_note"))


def table_models(models):
    df = pd.DataFrame({name: economics(model) for name, model in models.items()})
    df.index = [t(k) for k in df.index]
    styled = df.style.format("{:,.2f}", na_rep=t("na"))
    styled = styled.format(
        "{:.1%}", subset=pd.IndexSlice[[t("contribution_margin"), t("profit_margin")], :], na_rep=t("na")
    )
    show_table(styled, width="stretch")
    st.caption(L("Margins are percentages; money is in ", "Маржа показана в процентах; денежные суммы в ") + b.currency)


if page == "dashboard":
    st.markdown(f"**{case['ru' if ru else 'en']}** — {case['task_ru' if ru else 'task_en']}")
    metrics(
        e,
        [
            "revenue",
            "gross_profit",
            "contribution_profit",
            "operating_profit",
            "contribution_margin",
            "profit_margin",
            "marketing_spend",
            "break_even_revenue",
        ],
    )
    demo_m = st.session_state.get(
        "marketing_data", Marketing(ad_spend=b.ad_spend, attributed_revenue=e["revenue"] * 0.6)
    )
    if st.session_state.get("marketing_currency", b.currency) == b.currency:
        metrics(marketing(demo_m), ["paid_cac", "roas"])
    if "marketing_data" in st.session_state:
        st.caption(
            L(
                "Acquisition KPIs use the last valid Marketing Analytics dataset; this ledger is independent of the financial model.",
                "KPI привлечения используют последние корректные данные маркетингового раздела; эта модель независима от финансовой.",
            )
        )
    st.caption(
        L(
            "Default CAC and ROAS use a separate synthetic acquisition dataset (450 paid new, 2,000 other acquisition costs, 60% revenue attribution). Edit or upload actual data in Marketing Analytics; it does not overwrite the financial ledger.",
            "По умолчанию CAC и ROAS используют отдельные синтетические данные (450 новых платных, 2 000 прочих затрат, 60% рекламной выручки). Введите реальные данные в маркетинговом разделе; они не перезаписывают финансовую модель.",
        )
    )
    left, right = st.columns([1.6, 1])
    with left:
        show_chart(trend_fig(forecast(b, paid_share=paid_default)), width="stretch")
    with right:
        show_chart(expenses_fig(), width="stretch")
    show_chart(
        comparison_fig(
            {t("base"): b, L("Budget +25% · CAC saturation 0.25", "Бюджет +25% · насыщение CAC 0,25"): alternative}
        ),
        width="stretch",
    )
    show_insights(b)
    with st.expander(L("Case decision & risk", "Решение и риски кейса")):
        decision = simulate(b, **case["decision"], paid_share=paid_default)
        table_models({t("base"): b, t("alternative"): decision})
        st.write(case["risk_ru" if ru else "risk_en"])
        delta = economics(decision)["operating_profit"] - e["operating_profit"]
        st.write(L("Modelled operating profit change: ", "Модельное изменение операционной прибыли: ") + fmt(delta))

elif page == "economics":
    st.info(
        L(
            "Edit and apply monthly inputs. Price represents an average basket with one blended COGS amount per order.",
            "Измените и примените месячные параметры. Цена — средний чек с усреднённой себестоимостью на заказ.",
        )
    )
    with st.form("economics_inputs"):
        columns = st.columns(3)
        values = {}
        for i, (key, value) in enumerate(b.dict().items()):
            if key in ("currency", "period"):
                continue
            with columns[i % 3]:
                values[key] = st.number_input(
                    t(key),
                    min_value=0.0,
                    max_value=1.0 if key in ("returns", "discount", "payment_rate") else 1e9,
                    value=float(value),
                    format="%.4f" if key in ("returns", "discount", "payment_rate") else "%.2f",
                    key=f"econ_{key}_{st.session_state.revision}",
                )
        st.caption(L("Selected currency: ", "Выбранная валюта: ") + b.currency)
        st.caption(
            L(
                "Changing currency relabels values; no FX conversion. Rates use fractions: 0.05 = 5%.",
                "Смена валюты меняет обозначение без конвертации. Доли: 0,05 = 5%.",
            )
        )
        if st.form_submit_button(L("Apply monthly model", "Применить модель месяца"), type="primary"):
            try:
                st.session_state.business = Business(**values, currency=b.currency)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    metrics(
        e,
        [
            "revenue",
            "cogs",
            "gross_profit",
            "contribution_profit",
            "operating_profit",
            "profit_per_order",
            "revenue_per_order",
            "unit_contribution",
        ],
    )
    st.write(t("formula"))
    st.warning(t("limits"))

elif page == "marketing":
    st.info(
        L(
            "Independent acquisition ledger. The funnel is lead-based and channel-period customers must be deduplicated before import. Uploads do not change the financial model.",
            "Отдельная модель привлечения. Воронка основана на лидах; до импорта устраните пересечения клиентов между каналами. Загрузка не меняет финансовую модель.",
        )
    )
    source = st.file_uploader(L("Upload marketing CSV", "Загрузить маркетинговый CSV"), type="csv")
    demo_rows = []
    for channel, share in [("Search", 0.6), ("Social", 0.4)]:
        row = {k: v * share for k, v in asdict(Marketing()).items()}
        demo_rows.append(dict(channel=channel, period="2026-10", currency=b.currency, **row))
    st.download_button(
        L("Download CSV template", "Скачать шаблон CSV"),
        csv_bytes(pd.DataFrame(demo_rows)),
        "marketing_template.csv",
        "text/csv",
    )
    frame = None
    if source:
        try:
            frame = read_marketing(StringIO(source.getvalue().decode("utf-8-sig")))
        except (ValueError, TypeError, UnicodeError, pd.errors.ParserError) as exc:
            st.error(L("Invalid CSV: ", "Ошибка CSV: ") + str(exc))
            st.stop()
    if frame is not None:
        if frame.currency.iloc[0] != b.currency:
            st.error(
                L(
                    "CSV currency differs from the financial model. Change currency explicitly before comparison.",
                    "Валюта CSV отличается от финансовой модели. Явно смените валюту перед сравнением.",
                )
            )
            st.stop()
        st.caption(L("CSV month: ", "Месяц CSV: ") + str(frame.period.iloc[0]))
        channel = st.selectbox(L("Channel", "Канал"), [L("All channels", "Все каналы")] + frame.channel.tolist())
        selected = frame if channel == L("All channels", "Все каналы") else frame[frame.channel == channel]
        m = Marketing(**selected[list(asdict(Marketing()))].sum().to_dict())
        show_table(frame, width="stretch")
    else:
        with st.expander(
            L("Manual acquisition inputs · synthetic defaults", "Ручные данные привлечения · демо по умолчанию"),
            expanded=True,
        ):
            cols = st.columns(3)
            values = {}
            for i, (key, value) in enumerate(asdict(Marketing()).items()):
                values[key] = cols[i % 3].number_input(t(key), min_value=0.0, value=float(value), key="m_" + key)
            try:
                m = Marketing(**values)
            except ValueError as exc:
                st.error(L("Inconsistent funnel: ", "Несогласованная воронка: ") + str(exc))
                st.stop()
    st.session_state.marketing_data = m
    st.session_state.marketing_period = str(frame.period.iloc[0]) if frame is not None else "month"
    st.session_state.marketing_currency = b.currency
    kpis = marketing(m)
    metrics(kpis, list(kpis))
    names = [t(k) for k in ("impressions", "clicks", "visitors", "leads")] + [L("New customers", "Новые покупатели")]
    vals = [m.impressions, m.clicks, m.visitors, m.leads, m.paid_new + m.organic_new]
    fig = go.Figure(go.Funnel(y=names, x=vals, textinfo="value+percent initial"))
    show_chart(
        chart(fig, L("Acquisition funnel · new customers", "Воронка привлечения · новые покупатели"), False),
        width="stretch",
    )
    st.caption(
        L(
            "Orders include repeat purchases and may exceed unique customers. Therefore orders are shown separately from the descending acquisition funnel.",
            "Заказы включают повторные покупки и могут превышать число клиентов, поэтому показаны отдельно от убывающей воронки.",
        )
    )
    st.write(f"{t('orders')}: {m.orders:,.0f} · {t('repeat_customers')}: {m.repeat_customers:,.0f}")
    st.write(
        L(
            "Order CPA uses all orders (a blended cost per order). Paid CAC includes direct spend and other paid acquisition costs. Blended CAC divides those same measured costs by all new customers; unmeasured organic acquisition costs are excluded.",
            "CPA заказа использует все заказы (общая стоимость заказа). Платный CAC включает рекламу и прочие затраты платного привлечения. Общий CAC делит эти же измеренные затраты на всех новых клиентов; неизмеренные расходы органического привлечения не учтены.",
        )
    )
    if frame is not None and e["contribution_margin"] is not None:
        proxy = frame[["channel", "attributed_revenue", "ad_spend", "acquisition_other"]].copy()
        proxy[L("Estimated contribution after acquisition", "Оценка маржинальной прибыли после привлечения")] = (
            proxy.attributed_revenue * e["contribution_margin"] - proxy.ad_spend - proxy.acquisition_other
        )
        show_table(proxy.rename(columns=lambda k: L("Channel", "Канал") if k == "channel" else t(k)), width="stretch")
        st.caption(
            L(
                "Channel estimate uses the financial model’s blended contribution margin, assumes attributed revenue is net of discounts/returns, and excludes shared overhead. This is a screening proxy, not an audited channel P&L. Verify product mix and attribution.",
                "Оценка каналов использует среднюю маржинальность финансовой модели и выручку после скидок и возвратов; общие постоянные расходы исключены. Это предварительная оценка, а не подтверждённая прибыль канала. Проверьте товарную структуру и атрибуцию.",
            )
        )
        if (proxy.iloc[:, -1] < 0).any():
            st.warning(
                L(
                    "At least one channel has negative estimated contribution after acquisition. Review CAC and attributed revenue; the estimate depends on blended product margins.",
                    "Хотя бы один канал имеет отрицательную оценку маржинальной прибыли после привлечения. Проверьте CAC и рекламную выручку; оценка зависит от средней товарной маржи.",
                )
            )
    st.warning(
        L(
            "ROAS is revenue efficiency, not profitability. Channel profit cannot be inferred without allocated costs, returns and attribution validation.",
            "ROAS характеризует выручку, а не прибыльность. Без распределения затрат, возвратов и проверки атрибуции прибыль канала неизвестна.",
        )
    )
    if kpis["paid_cac"] is not None and kpis["paid_cac"] > max(0, e["unit_contribution"]):
        st.warning(
            L(
                "Paid CAC exceeds contribution from one placed order. First-order payback is at risk. Compare actual paid customer contribution and repeat purchases; blended product economics are only a proxy.",
                "Платный CAC превышает маржу одного оформленного заказа. Есть риск неокупаемости первой покупки. Проверьте маржу платных клиентов и повторные покупки; усреднённая экономика — лишь приближение.",
            )
        )

elif page == "scenarios":
    st.info(t("scale_note"))
    cols = st.columns(3)
    args = {}
    for i, key in enumerate(
        ["price_factor", "cost_factor", "budget_factor", "conversion_factor", "cac_factor", "fixed_factor"]
    ):
        args[key] = cols[i % 3].slider(t(key), 0.1, 3.0, 1.0, 0.05, key="s_" + key)
    scale = st.slider(
        L("CAC saturation above baseline budget", "Насыщение CAC при росте бюджета"), 0.0, 2.0, 0.25, 0.05
    )
    elasticity = st.slider(
        L("Price demand elasticity (0 = disabled)", "Ценовая эластичность спроса (0 = выключена)"), 0.0, 4.0, 1.0, 0.1
    )
    paid_share = st.slider(L("Baseline paid order share", "Базовая доля платных заказов"), 0.0, 1.0, paid_default, 0.05)
    repeat = st.slider(
        L("Incremental repeat-order uplift", "Дополнительный прирост повторных заказов"), 0.0, 1.0, 0.0, 0.05
    )
    returns = st.slider(t("returns"), 0.0, 1.0, b.returns, 0.01)
    common = dict(
        scale_penalty=scale, elasticity=elasticity, paid_share=paid_share, repeat_lift=repeat, returns=returns
    )
    try:
        alt = simulate(b, **args, **common)
        models = {
            t("pessimistic"): simulate(
                b,
                price_factor=0.95,
                cost_factor=1.1,
                cac_factor=1.2,
                conversion_factor=0.9,
                scale_penalty=scale,
                elasticity=elasticity,
                paid_share=paid_share,
            ),
            t("base"): b,
            t("optimistic"): simulate(
                b,
                price_factor=1.05,
                cost_factor=0.95,
                cac_factor=0.9,
                conversion_factor=1.1,
                scale_penalty=scale,
                elasticity=elasticity,
                paid_share=paid_share,
            ),
            t("alternative"): alt,
        }
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
    metrics(economics(alt), ["revenue", "operating_profit", "profit_margin", "break_even_revenue"], e)
    show_chart(comparison_fig(models), width="stretch")
    table_models(models)
    with st.expander(L("Preset assumptions", "Допущения готовых сценариев")):
        st.write(
            L(
                "Pessimistic: price −5%, COGS +10%, CAC +20%, conversion −10%. Optimistic: price +5%, COGS −5%, CAC −10%, conversion +10%. Both use selected elasticity, saturation and paid share; other inputs remain baseline.",
                "Пессимистичный: цена −5%, себестоимость +10%, CAC +20%, конверсия −10%. Оптимистичный: цена +5%, себестоимость −5%, CAC −10%, конверсия +10%. Оба используют выбранные эластичность, насыщение и долю платных заказов; остальные параметры базовые.",
            )
        )
    sens = pd.DataFrame(sensitivity(b, **args, **common))
    sens["parameter"] = sens.parameter.map(t)
    sens["change"] = sens.change.map({-0.1: "−10%", 0.1: "+10%"})
    sens = sens.rename(
        columns={
            "parameter": L("Parameter", "Параметр"),
            "change": L("Shock", "Изменение"),
            "profit_delta": t("profit_delta"),
        }
    )
    fig = px.bar(
        sens,
        y=L("Parameter", "Параметр"),
        x=t("profit_delta"),
        color=L("Shock", "Изменение"),
        orientation="h",
        barmode="group",
    )
    show_chart(
        chart(
            fig,
            L(
                "One-at-a-time sensitivity around alternative · ±10%",
                "Чувствительность альтернативы · по одному фактору ±10%",
            ),
            False,
        ),
        width="stretch",
    )
    name = st.text_input(L("Scenario name", "Название сценария"), value=L("My decision", "Моё решение"))
    if st.button(L("Save alternative to comparison", "Сохранить альтернативу для сравнения")):
        if not name.strip():
            st.error(L("Enter a name", "Введите название"))
        elif name in st.session_state.saved:
            st.error(L("Name already exists. Use a unique name.", "Название уже существует. Укажите уникальное."))
        else:
            st.session_state.saved[name] = alt
            st.session_state.setdefault("assumptions", {})[name] = dict(args, **common)
            st.success(
                L(
                    "Saved for this browser session. Export JSON for durable storage.",
                    "Сохранено в сессии браузера. Для постоянного хранения экспортируйте JSON.",
                )
            )
    if st.session_state.saved:
        st.subheader(L("Your saved decisions", "Ваши сохранённые решения"))
        compatible = {k: v for k, v in st.session_state.saved.items() if v.currency == b.currency}
        show_chart(comparison_fig({t("base"): b, **compatible}), width="stretch")
        table_models({t("base"): b, **compatible})
        if len(compatible) != len(st.session_state.saved):
            st.warning(L("Scenarios in different currencies are excluded.", "Сценарии в другой валюте исключены."))
    show_insights(alt)

elif page == "breakeven":
    metrics(e, ["unit_contribution", "break_even_orders", "minimum_orders", "break_even_revenue"])
    if e["break_even_orders"] is None:
        st.warning(
            L(
                "No sustainable break-even with nonpositive unit contribution. Inspect price, returns and variable costs.",
                "Устойчивая безубыточность недостижима при неположительной марже заказа. Проверьте цену, возвраты и переменные расходы.",
            )
        )
    upper = max(b.orders * 2, (e["break_even_orders"] or 0) * 1.4, 100)
    grid = [upper * i / 80 for i in range(81)]
    rows = []
    for q in grid:
        result = economics(replace(b, orders=q))
        rows.append(
            {t("orders"): q, t("revenue"): result["revenue"] + b.other_income, t("total_costs"): result["total_costs"]}
        )
    fig = px.line(pd.DataFrame(rows), x=t("orders"), y=[t("revenue"), t("total_costs")])
    if e["break_even_orders"] is not None:
        fig.add_vline(x=e["break_even_orders"], line_dash="dash", annotation_text=t("break_even_orders"))
    show_chart(
        chart(
            fig,
            L(
                "Revenue + other income vs total costs · fixed ad spend",
                "Выручка + прочие доходы и расходы · реклама фиксирована",
            ),
        ),
        width="stretch",
    )
    st.caption(
        L(
            "Revenue line includes other operating income to align the intersection with operating break-even. The revenue KPI excludes other income.",
            "Линия выручки включает прочие операционные доходы для корректного пересечения. KPI выручки их не включает.",
        )
    )
    elasticity = st.slider(
        L("Price elasticity (0 = constant demand)", "Эластичность цены (0 = постоянный спрос)"), 0.0, 4.0, 1.0, 0.1
    )
    fixed = st.slider(L("Fixed cost factor", "Множитель постоянных расходов"), 0.2, 3.0, 1.0, 0.1)
    price_rows = []
    for i in range(31):
        factor = 0.5 + i * 0.05
        result_b = simulate(b, price_factor=factor, elasticity=elasticity, fixed_factor=fixed, paid_share=paid_default)
        result = economics(result_b)
        price_rows.append(
            {
                t("price"): result_b.price,
                t("operating_profit"): result["operating_profit"],
                t("break_even_revenue"): result["break_even_revenue"],
                t("orders"): result_b.orders,
                t("contribution_margin"): result["contribution_margin"],
            }
        )
    show_chart(
        chart(
            px.line(pd.DataFrame(price_rows), x=t("price"), y=[t("operating_profit"), t("break_even_revenue")]),
            L("Pricing & overhead sensitivity", "Чувствительность к цене и постоянным затратам"),
        ),
        width="stretch",
    )
    show_table(pd.DataFrame(price_rows), width="stretch")
    st.write(t("formula"))

elif page == "forecast":
    st.warning(
        L(
            "Deterministic model scenario. Not machine learning, a confidence interval or a prediction. Month 1 equals the current baseline; growth starts in month 2.",
            "Детерминированный модельный сценарий. Не машинное обучение, доверительный интервал или предсказание. Месяц 1 равен текущей базе; рост начинается с месяца 2.",
        )
    )
    months = st.select_slider(L("Horizon (months)", "Горизонт (месяцы)"), [3, 6, 12], value=6)
    cols = st.columns(3)
    growth = cols[0].slider(L("Monthly demand growth", "Месячный рост спроса"), -0.5, 0.5, 0.02, 0.01)
    cost_g = cols[1].slider(L("Monthly unit COGS growth", "Месячный рост себестоимости заказа"), -0.2, 0.3, 0.01, 0.01)
    budget_g = cols[2].slider(L("Monthly ad budget growth", "Месячный рост рекламного бюджета"), -0.3, 0.5, 0.0, 0.01)
    fixed_g = cols[0].slider(L("Monthly fixed cost growth", "Месячный рост постоянных затрат"), -0.2, 0.3, 0.0, 0.01)
    conversion_g = cols[1].slider(
        L("Monthly paid conversion growth", "Месячный рост платной конверсии"), -0.2, 0.3, 0.0, 0.01
    )
    season = cols[2].slider(L("Synthetic seasonal amplitude", "Амплитуда условной сезонности"), 0.0, 0.8, 0.0, 0.05)
    scale = st.slider(L("CAC saturation coefficient", "Коэффициент насыщения CAC"), 0.0, 2.0, 0.25, 0.05)
    rows = forecast(b, months, growth, cost_g, budget_g, fixed_g, conversion_g, season, scale, paid_default)
    show_chart(trend_fig(rows), width="stretch")
    table = pd.DataFrame(rows)[
        ["month", "orders", "revenue", "total_costs", "operating_profit", "profit_margin"]
    ].rename(columns=t)
    show_table(table.style.format("{:,.2f}").format("{:.1%}", subset=[t("profit_margin")]), width="stretch")
    st.caption(
        L(
            "Demand growth multiplies all orders after acquisition effects. Seasonality = 1 + amplitude × sin(2π × elapsed months / 12), with a synthetic phase. Baseline volume is edited in Business Economics. Avoid counting the same growth in both demand and conversion.",
            "Рост спроса умножает все заказы после эффектов привлечения. Сезонность = 1 + амплитуда × sin(2π × прошедшие месяцы / 12), фаза условная. Начальный объём задаётся в экономике бизнеса. Не учитывайте один рост одновременно в спросе и конверсии.",
        )
    )
    st.download_button(L("Export forecast CSV", "Экспорт прогноза CSV"), csv_bytes(table), "forecast.csv", "text/csv")

elif page in ("projects", "products", "planning", "decisions", "risk"):
    render_workbench(page, b, lang, t, show_chart, show_table)

elif page == "reports":
    render_export_center(b, lang)
    st.divider()
    st.info(
        L(
            "Exports stay on your device. Unsaved comparisons remain in this session; save a project or download a backup to keep them.",
            "Экспорт остаётся на Вашем устройстве. Несохранённые сравнения хранятся в сессии; сохраните проект или скачайте резервную копию.",
        )
    )
    choices = {L("Current baseline", "Текущая база"): b, **st.session_state.saved}
    chosen = st.selectbox(L("Scenario to export", "Сценарий для экспорта"), list(choices))
    export_b = choices[chosen]
    st.download_button(
        L("Save scenario JSON", "Сохранить сценарий JSON"), dumps(export_b), "scenario.json", "application/json"
    )
    upload = st.file_uploader(L("Import scenario JSON", "Импортировать сценарий JSON"), type="json")
    import_name = st.text_input(
        L("Imported scenario name", "Имя импортируемого сценария"), value=L("Imported", "Импорт")
    )
    if st.button(L("Import to comparison", "Импортировать для сравнения")):
        try:
            if not upload or not import_name.strip():
                raise ValueError(L("Choose JSON and enter a name", "Выберите JSON и укажите имя"))
            if import_name in st.session_state.saved:
                raise ValueError(L("Name already exists", "Название уже существует"))
            st.session_state.saved[import_name] = loads(upload.getvalue())
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    if st.button(L("Apply selected scenario as baseline", "Применить выбранный сценарий как базу")):
        st.session_state.business = export_b
        st.session_state.revision += 1
        st.rerun()
    compatible = {k: v for k, v in choices.items() if v.currency == b.currency}
    selected = st.multiselect(
        L("Compare saved scenarios", "Сравнить сохранённые сценарии"), list(compatible), default=list(compatible)[:2]
    )
    if selected:
        table_models({key: compatible[key] for key in selected})
    comparison = st.selectbox(
        L("Report alternative", "Альтернатива для отчёта"),
        [L("Budget +25%", "Бюджет +25%")] + list(st.session_state.saved),
    )
    alt = alternative if comparison == L("Budget +25%", "Бюджет +25%") else st.session_state.saved[comparison]
    if alt.currency != b.currency:
        st.error(L("Choose matching currencies", "Выберите одинаковую валюту"))
    else:
        figs = [
            trend_fig(forecast(b, paid_share=paid_default)),
            expenses_fig(),
            comparison_fig({t("base"): b, comparison: alt}),
        ]
        st.download_button(
            L("Print-ready HTML report", "HTML-отчёт для печати"),
            report(
                b,
                alt,
                figs,
                t,
                ru,
                st.session_state.get("assumptions", {}).get(
                    comparison,
                    {"budget_factor": 1.25, "scale_penalty": 0.25, "elasticity": 0, "paid_share": paid_default},
                )
                if alt == alternative
                else st.session_state.get("assumptions", {}).get(comparison),
            ),
            "business_report.html",
            "text/html",
        )
    result = pd.DataFrame(
        [dict(metric=key, value=value, currency=b.currency, period="month") for key, value in e.items()]
    )
    result["label"] = result.metric.map(t)
    result["unit"] = result.metric.map(
        lambda k: (
            "fraction"
            if k in ("contribution_margin", "profit_margin")
            else "orders"
            if k in ("break_even_orders", "minimum_orders")
            else b.currency
        )
    )
    st.download_button(L("Export KPI CSV", "Экспорт KPI CSV"), csv_bytes(result), "business_metrics.csv", "text/csv")
    if st.session_state.get("assumptions"):
        st.download_button(
            L("Export decision assumptions", "Экспорт допущений решений"),
            json.dumps(st.session_state.assumptions, indent=2),
            "decision_assumptions.json",
            "application/json",
        )

elif page == "settings":
    st.subheader(L("Model boundaries", "Границы модели"))
    st.write(t("limits"))
    st.write(t("formula"))
    st.write(t("scale_note"))
    st.info(
        L(
            "Choose language, light/dark appearance and currency in the sidebar. Currency changes labels without converting amounts. Saved scenarios retain their original currencies.",
            "Язык, светлая/тёмная тема и валюта выбираются в боковой панели. Валюта меняет обозначение без пересчёта сумм. Сохранённые сценарии сохраняют исходную валюту.",
        )
    )
    st.subheader(L("LTV & cohorts", "LTV и когорты"))
    st.write(
        L(
            "LTV is intentionally not calculated: the monthly dataset does not identify cohorts, retention, lifetime or contribution by customer. An average basket is insufficient. Repeat-order uplift is a scenario assumption, not measured retention.",
            "LTV не рассчитывается: месячные данные не определяют когорты, удержание, срок жизни и маржу клиента. Одного среднего чека недостаточно. Прирост повторных заказов — сценарное допущение, а не измеренное удержание.",
        )
    )
    st.subheader(L("Synthetic case library", "Библиотека демонстрационных кейсов"))
    for item in CASES.values():
        with st.expander(item["ru" if ru else "en"]):
            st.write(item["task_ru" if ru else "task_en"])
            st.json(item["business"].dict())
            table_models(
                {t("base"): item["business"], t("alternative"): simulate(item["business"], **item["decision"])}
            )
            st.write(item["risk_ru" if ru else "risk_en"])
    st.caption("BUSINESS LAB PRO · v1.1 · Python / Streamlit / Plotly")

st.divider()
st.caption(t("limits"))
