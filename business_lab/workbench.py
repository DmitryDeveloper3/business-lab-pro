"""Localized advanced workspaces. UI delegates all mathematics to pure analytics."""

from datetime import datetime
from io import StringIO
import json
import os
import re
import sqlite3
from zoneinfo import ZoneInfo
import pandas as pd
import plotly.express as px
import streamlit as st
from .analytics import (
    SKU_COLUMNS,
    default_skus,
    sku_economics,
    portfolio,
    goal,
    acquisition_ceiling,
    cash_runway,
    plan_actual,
    risk_simulation,
    promotion,
)
from .engine import forecast, marketing
from .exports import csv_bytes, bundle_tables, export_zip
from .excel import excel_bytes
from .workspace import WorkspaceStore, capture, restore, parse_backup


LABELS = {
    "sku": ("SKU / product", "SKU / товар"),
    "price": ("Price", "Цена"),
    "unit_cost": ("Unit COGS", "Себестоимость заказа"),
    "variable_cost": ("Processing / order", "Обработка заказа"),
    "orders": ("Orders", "Заказы"),
    "returns": ("Return fraction", "Доля возвратов"),
    "discount": ("Discount fraction", "Доля скидки"),
    "payment_rate": ("Payment fee fraction", "Доля комиссии"),
    "currency": ("Currency", "Валюта"),
    "period": ("Month", "Месяц"),
    "revenue": ("Net revenue", "Выручка"),
    "total_costs": ("Total operating costs", "Все операционные затраты"),
    "other_income": ("Other income", "Прочие доходы"),
    "contribution_profit": ("Contribution profit", "Маржинальная прибыль"),
    "allocated_shared_costs": ("Allocated ads & overhead", "Распределённые реклама и постоянные затраты"),
    "after_allocated_costs": ("Profit after allocation", "Прибыль после распределения"),
    "planned_revenue": ("Planned revenue", "План выручки"),
    "planned_profit": ("Planned operating profit", "План операционной прибыли"),
    "actual_profit": ("Actual operating profit", "Фактическая операционная прибыль"),
    "revenue_variance": ("Revenue variance", "Отклонение выручки"),
    "profit_variance": ("Profit variance", "Отклонение прибыли"),
    "revenue_variance_rate": ("Revenue variance fraction", "Доля отклонения выручки"),
    "opening_cash": ("Opening cash", "Начальные деньги"),
    "receipts": ("Cash receipts", "Денежные поступления"),
    "payments": ("Cash payments", "Денежные выплаты"),
    "net_cash_flow": ("Net cash flow", "Чистый денежный поток"),
    "closing_cash": ("Closing cash", "Конечные деньги"),
    "below_buffer": ("Below reserve", "Ниже резерва"),
    "month": ("Model month", "Месяц модели"),
    "decision": ("Decision", "Решение"),
    "hypothesis": ("Hypothesis / evidence", "Гипотеза / основание"),
    "next_step": ("Next step / review date", "Следующий шаг / дата проверки"),
    "result": ("Observed outcome", "Наблюдаемый результат"),
    "created_at": ("Recorded at (UTC)", "Записано (UTC)"),
    "operating_profit": ("Operating profit", "Операционная прибыль"),
}


def record_table(name, frame, b):
    st.session_state.setdefault("export_tables", {})[name] = dict(
        rows=json.loads(frame.to_json(orient="records")), currency=b.currency, business=b.dict()
    )


def render_workbench(page, b, lang, t, show_chart, show_table):
    ru = lang == "Русский"

    def L(en, rus):
        return rus if ru else en

    def label(key):
        return LABELS[key][int(ru)] if key in LABELS else t(key)

    def money(value):
        return t("na") if value is None else f"{value:,.2f} {b.currency}"

    def table(frame):
        display = frame.rename(columns=label)
        styled = display.style.format(
            lambda v: f"{v:,.2f}" if isinstance(v, (int, float)) and not isinstance(v, bool) else v, na_rep=t("na")
        )
        show_table(styled, width="stretch")

    def csv_download(frame, filename, title=None):
        st.download_button(
            title or L("Download CSV", "Скачать CSV"), csv_bytes(frame), filename, "text/csv", key="csv_" + filename
        )

    def numeric(key, en, rus, value=0.0, maximum=1e12):
        saved_keys = {
            "goals_target": ("goals_inputs", "target_profit"),
            "acq_orders": ("acquisition_inputs", "expected_orders"),
            "acq_extra": ("acquisition_inputs", "extra_customer_cost"),
            "acq_target": ("acquisition_inputs", "target_customer_profit"),
            "acq_new": ("acquisition_inputs", "paid_new"),
            "acq_other": ("acquisition_inputs", "other_acquisition"),
            "acq_cac": ("acquisition_inputs", "actual_cac"),
        }
        if key in saved_keys:
            group, field = saved_keys[key]
            value = st.session_state.get(group, {}).get(field, value)
        return st.number_input(L(en, rus), min_value=0.0, max_value=float(maximum), value=float(value), key=key)

    def failure(exc):
        st.error(L("Check the input data: ", "Проверьте исходные данные: ") + str(exc))

    if page == "projects":
        if os.getenv("BUSINESS_LAB_PUBLIC_DEMO") != "1":
            st.info(
                L(
                    "Explicit local storage. Projects are shared by sessions using this installation. Changes are saved only by the Save button.",
                    "Явное локальное хранение. Проекты общие для сессий этой установки. Изменения сохраняются только кнопкой сохранения.",
                )
            )
        if os.getenv("BUSINESS_LAB_PUBLIC_DEMO") == "1":
            st.info(
                L(
                    "PUBLIC DEMO: saved projects are isolated to this visitor session and may disappear when the session/server restarts. Download model backups and journal CSV before leaving. No account or cross-device persistence is provided.",
                    "ПУБЛИЧНОЕ ДЕМО: сохранённые проекты изолированы в текущей сессии посетителя и могут исчезнуть после её завершения или перезапуска сервера. Перед выходом скачайте копии моделей и CSV журнала. Аккаунта и хранения между устройствами нет.",
                )
            )
        store = WorkspaceStore()
        try:
            projects = store.list_projects()
        except (OSError, sqlite3.Error) as exc:
            st.error(L("Local database unavailable: ", "Локальная база недоступна: ") + str(exc))
            return
        library, journal = st.tabs(
            [L("Project library", "Библиотека проектов"), L("Decision journal", "Журнал решений")]
        )
        with library:
            name = st.text_input(
                L("Project name", "Название проекта"),
                value=st.session_state.get("project_name", L("My business", "Мой бизнес")),
                key="project_title",
                max_chars=120,
            )
            update = st.checkbox(
                L("Update the active project", "Обновить активный проект"),
                value=False,
                disabled=not st.session_state.get("project_id"),
            )
            if st.button(L("Save project to disk", "Сохранить проект на диск"), key="save_project", type="primary"):
                try:
                    project_id = store.save(
                        name, capture(st.session_state), st.session_state.get("project_id") if update else None
                    )
                    st.session_state.project_id = project_id
                    st.session_state.project_name = name
                    st.success(L("Saved to local SQLite database.", "Сохранено в локальной базе SQLite."))
                    projects = store.list_projects()
                except (ValueError, OSError, sqlite3.Error) as exc:
                    failure(exc)
            if projects:
                index = {p["id"]: p for p in projects}
                selected = st.selectbox(
                    L("Saved project", "Сохранённый проект"),
                    list(index),
                    format_func=lambda k: index[k]["name"] + " · " + index[k]["updated_at"],
                    key="stored_project",
                )
                if st.button(L("Load selected project", "Загрузить выбранный проект"), key="load_project"):
                    try:
                        restore(st.session_state, store.load(selected))
                        st.session_state.project_id = selected
                        st.session_state.project_name = index[selected]["name"]
                        st.session_state.pop("project_title", None)
                        st.rerun()
                    except (ValueError, OSError, sqlite3.Error) as exc:
                        failure(exc)
            backup = json.dumps(capture(st.session_state), ensure_ascii=False, indent=2, allow_nan=False)
            st.download_button(
                L("Download models & inputs JSON backup", "Скачать JSON-копию моделей и параметров"),
                backup,
                "business_lab_project.json",
                "application/json",
            )
            st.caption(
                L(
                    "The JSON backup preserves financial models and analysis inputs. The decision journal is kept in SQLite and exported separately as CSV. Current UI language/theme stay unchanged when restoring.",
                    "JSON-копия сохраняет финансовые модели и параметры анализов. Журнал хранится в SQLite и выгружается отдельно в CSV. Текущий язык и тема при восстановлении не меняются.",
                )
            )
            upload = st.file_uploader(
                L("Restore project JSON backup", "Восстановить проект из JSON"), type="json", key="workspace_upload"
            )
            if st.button(
                L("Apply backup to this session", "Восстановить копию в текущую сессию"), key="restore_backup"
            ):
                try:
                    if upload is None:
                        raise ValueError(L("Select a JSON backup", "Выберите JSON-копию"))
                    restore(st.session_state, parse_backup(upload.getvalue()))
                    st.session_state.pop("project_id", None)
                    st.session_state.pop("project_name", None)
                    st.rerun()
                except (ValueError, TypeError) as exc:
                    failure(exc)
        with journal:
            project_id = st.session_state.get("project_id")
            if not project_id:
                st.info(
                    L(
                        "Save or load a project to attach decisions to it.",
                        "Сохраните или загрузите проект, чтобы привязать к нему решения.",
                    )
                )
            else:
                st.caption(
                    L("Active project: ", "Активный проект: ") + st.session_state.get("project_name", project_id)
                )
                with st.form("decision_journal_form", clear_on_submit=True):
                    decision = st.text_input(label("decision"), max_chars=4000)
                    hypothesis = st.text_area(label("hypothesis"), max_chars=4000)
                    next_step = st.text_input(label("next_step"), max_chars=4000)
                    result = st.text_area(label("result"), max_chars=4000)
                    if st.form_submit_button(L("Record decision", "Записать решение")):
                        try:
                            store.add_decision(project_id, decision, hypothesis, next_step, result)
                            st.success(
                                L(
                                    "Decision recorded. Add a follow-up entry when reviewed.",
                                    "Решение записано. По итогам проверки добавьте следующую запись.",
                                )
                            )
                        except ValueError as exc:
                            failure(exc)
                rows = pd.DataFrame(store.journal(project_id))
                if not rows.empty:
                    table(rows.drop(columns=["id", "project_id"]))
                    csv_download(rows, "decision_journal.csv")

    elif page == "products":
        unit_tab, portfolio_tab = st.tabs(
            [
                L("Product economics", "Экономика товаров"),
                L("Portfolio & cost allocation", "Портфель и распределение затрат"),
            ]
        )
        st.session_state.setdefault("sku_input", default_skus(b).to_dict("records"))
        st.session_state.setdefault("sku_currency", b.currency)
        if st.button(
            L("Reset product template from current baseline", "Обновить товарный шаблон из текущей базы"),
            key="reset_skus",
        ):
            st.session_state.sku_input = default_skus(b).to_dict("records")
            st.session_state.sku_currency = b.currency
            st.session_state.pop("editor_skus", None)
            st.rerun()
        if st.session_state.sku_currency != b.currency:
            st.warning(
                L(
                    "Product currency differs from current baseline. Switch currency back or reset the product template explicitly.",
                    "Валюта товаров отличается от текущей базы. Верните валюту или явно обновите товарный шаблон.",
                )
            )
            return
        with unit_tab:
            st.caption(
                L(
                    "Independent synthetic product template. Edit real SKU inputs; this table does not overwrite baseline orders. Rates are fractions. Returned stock and fee assumptions match the financial engine.",
                    "Независимый синтетический товарный шаблон. Введите реальные SKU; таблица не перезаписывает заказы базовой модели. Ставки — доли единицы. Правила возвратов и комиссий совпадают с финансовым ядром.",
                )
            )
            source = st.file_uploader(L("Import product CSV", "Импорт товарного CSV"), type="csv", key="sku_upload")
            if st.button(L("Apply product CSV", "Применить товарный CSV"), key="apply_sku_csv"):
                try:
                    if source is None:
                        raise ValueError(L("Choose CSV first", "Сначала выберите CSV"))
                    imported = pd.read_csv(StringIO(source.getvalue().decode("utf-8-sig")))
                    sku_economics(imported, b.currency)
                    st.session_state.sku_input = imported.to_dict("records")
                    st.session_state.pop("editor_skus", None)
                    st.rerun()
                except (ValueError, TypeError, UnicodeError) as exc:
                    failure(exc)
            csv_download(
                pd.DataFrame(st.session_state.sku_input),
                "product_input.csv",
                L("Download input CSV / template", "Скачать исходный CSV / шаблон"),
            )
            edited = st.data_editor(
                pd.DataFrame(st.session_state.sku_input),
                num_rows="dynamic",
                hide_index=True,
                column_config={
                    k: st.column_config.TextColumn(label(k))
                    if k == "sku"
                    else st.column_config.NumberColumn(
                        label(k), min_value=0.0, max_value=1.0 if k in ("returns", "discount", "payment_rate") else None
                    )
                    for k in SKU_COLUMNS
                },
                key="editor_skus",
                width="stretch",
            )
            try:
                output = sku_economics(edited, b.currency)
            except (ValueError, TypeError) as exc:
                failure(exc)
                return
            st.session_state.sku_input = edited.to_dict("records")
            keys = ["sku", "orders", "revenue", "contribution_profit", "unit_contribution", "contribution_margin"]
            table(output[keys])
            csv_download(output, "product_economics.csv")
            record_table("product_economics", output, b)
            if (output.unit_contribution < 0).any():
                st.warning(
                    L(
                        "Some SKUs lose contribution per order before advertising and shared overhead.",
                        "Есть товары с отрицательной маржой заказа ещё до рекламы и общих постоянных расходов.",
                    )
                )
        with portfolio_tab:
            allocation = st.selectbox(
                L("Allocate shared costs by", "Распределять общие расходы по"),
                ["revenue", "orders"],
                format_func=label,
                index=["revenue", "orders"].index(st.session_state.get("portfolio_driver", "revenue")),
                key="portfolio_allocation",
            )
            st.session_state.portfolio_driver = allocation
            data, summary = portfolio(edited, b, allocation)
            cols = st.columns(3)
            for col, key in zip(cols, ["revenue", "contribution_profit", "operating_profit"]):
                col.metric(label(key), money(summary[key]))
            st.caption(
                L(
                    "Advertising and fixed costs come from the baseline and are deducted ONCE. Other income is added once at company level. Allocation is a management assumption; an allocated SKU loss is not automatically a reason to discontinue it.",
                    "Реклама и постоянные затраты берутся из базы и вычитаются ОДИН раз. Прочие доходы добавляются один раз на уровне компании. Распределение — управленческое допущение; распределённый убыток SKU сам по себе не основание убрать товар.",
                )
            )
            if summary["unallocated_costs"]:
                st.warning(
                    L(
                        "Zero allocation base: costs remain unallocated in the company total.",
                        "Нулевая база распределения: расходы остаются нераспределёнными в общем итоге.",
                    )
                )
            table(data[["sku", "revenue", "contribution_profit", "allocated_shared_costs", "after_allocated_costs"]])
            show_chart(
                px.bar(
                    data.rename(columns=label),
                    x=label("sku"),
                    y=label("after_allocated_costs"),
                    title=L("Product profit after cost allocation", "Прибыль товаров после распределения расходов"),
                ),
                width="stretch",
            )
            csv_download(data, "portfolio.csv")
            record_table("portfolio", data, b)
            record_table("portfolio_summary", pd.DataFrame([summary]), b)

    elif page == "planning":
        goals_tab, actual_tab = st.tabs([L("Target profit", "Целевая прибыль"), L("Plan vs actual", "План–факт")])
        with goals_tab:
            target = numeric(
                "goals_target", "Target monthly operating profit", "Целевая операционная прибыль за месяц", 30000.0
            )
            result = goal(b, target)
            cols = st.columns(3)
            cols[0].metric(
                L("Minimum placed orders", "Минимум оформленных заказов"),
                t("na") if result["minimum_orders"] is None else f"{result['minimum_orders']:,}",
            )
            cols[1].metric(
                L("Required price at current volume", "Нужная цена при текущем объёме"), money(result["required_price"])
            )
            cols[2].metric(
                L("Maximum ads at current volume", "Максимум рекламы при текущем объёме"),
                money(result["maximum_ad_spend"]),
            )
            st.info(
                L(
                    "Each output is a separate inverse calculation. Orders: hold price, ad spend and unit costs fixed. Price: hold demand fixed, so this is not an elasticity forecast. Ad ceiling: hold order volume fixed, so this is not an acquisition prediction. N/A means the target is infeasible through that lever.",
                    "Каждый результат — отдельный обратный расчёт. Заказы: цена, реклама и удельные затраты фиксированы. Цена: спрос фиксирован, это не прогноз эластичности. Предел рекламы: объём заказов фиксирован, это не прогноз привлечения. Н/Д означает недостижимость цели этим способом.",
                )
            )
            csv_download(pd.DataFrame([result]), "profit_goal.csv")
            st.session_state.goals_inputs = dict(target_profit=target)
            record_table("profit_goal", pd.DataFrame([result]), b)
        with actual_tab:
            start = st.text_input(
                L("First calendar month (YYYY-MM)", "Первый календарный месяц (ГГГГ-ММ)"),
                value=st.session_state.get("actual_start", datetime.now(ZoneInfo("Europe/Moscow")).strftime("%Y-%m")),
                key="actual_month",
            )
            months = st.selectbox(
                L("Plan horizon", "Горизонт плана"),
                [3, 6, 12],
                index=[3, 6, 12].index(st.session_state.get("planning_inputs", {}).get("months", 6)),
                key="actual_horizon",
            )
            growth = st.number_input(
                L("Monthly planned demand growth (fraction)", "Плановый месячный рост спроса (доля)"),
                min_value=-0.9,
                max_value=1.0,
                value=st.session_state.get("planning_inputs", {}).get("growth", 0.02),
                key="actual_growth",
            )
            try:
                if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", start):
                    raise ValueError("Use YYYY-MM")
                plan = pd.DataFrame(forecast(b, months=months, growth=growth, paid_share=0.6 if b.ad_spend else 0))
                plan["period"] = pd.period_range(start, periods=months, freq="M").astype(str)
            except ValueError as exc:
                failure(exc)
                return
            st.session_state.planning_inputs = dict(months=months, growth=growth)
            st.session_state.actual_start = start
            st.session_state.setdefault(
                "actual_input",
                [dict(period=start, currency=b.currency, revenue=0.0, total_costs=0.0, other_income=0.0)],
            )
            st.session_state.setdefault("actual_currency", b.currency)
            st.info(
                L(
                    "Actuals start at zero as a template, not measured business data. Enter total operating costs including advertising exactly once. Missing months remain N/A; they are not treated as zero. Planned COGS grows 1% monthly; other forecast assumptions follow the default engine.",
                    "Нули факта — шаблон, а не измеренные бизнес-данные. Укажите все операционные затраты, включая рекламу, ровно один раз. Отсутствующие месяцы остаются Н/Д, а не считаются нулевыми. Плановая себестоимость растёт на 1% в месяц; остальные допущения — как в стандартном прогнозе.",
                )
            )
            source = st.file_uploader(L("Upload actual CSV", "Загрузить CSV факта"), type="csv", key="actual_upload")
            if st.button(L("Apply actual CSV", "Применить CSV факта"), key="apply_actual_csv"):
                try:
                    if source is None:
                        raise ValueError(L("Choose CSV first", "Сначала выберите CSV"))
                    frame = pd.read_csv(StringIO(source.getvalue().decode("utf-8-sig")))
                    plan_actual(frame, plan, b.currency)
                    st.session_state.actual_input = frame.to_dict("records")
                    st.session_state.actual_currency = b.currency
                    st.session_state.pop("editor_actual", None)
                    st.rerun()
                except (ValueError, TypeError, UnicodeError) as exc:
                    failure(exc)
            actual = st.data_editor(
                pd.DataFrame(st.session_state.actual_input),
                num_rows="dynamic",
                hide_index=True,
                column_config={k: label(k) for k in st.session_state.actual_input[0]},
                key="editor_actual",
                width="stretch",
            )
            csv_download(
                actual, "actual_input.csv", L("Download actual input CSV / template", "Скачать CSV факта / шаблон")
            )
            try:
                joined = plan_actual(actual, plan, b.currency)
            except (ValueError, TypeError) as exc:
                failure(exc)
                return
            st.session_state.actual_input = actual.to_dict("records")
            st.session_state.actual_currency = b.currency
            table(joined)
            show_chart(
                px.line(
                    joined.rename(columns=label),
                    x=label("period"),
                    y=[label("planned_profit"), label("actual_profit")],
                    markers=True,
                    title=L("Operating profit: plan vs actual", "Операционная прибыль: план и факт"),
                ),
                width="stretch",
            )
            csv_download(joined, "plan_actual.csv")
            record_table("plan_actual", joined, b)

    elif page == "decisions":
        cac_tab, cash_tab, promo_tab = st.tabs(
            [
                L("Acquisition allowance", "Допустимая стоимость привлечения"),
                L("Cash reserve & runway", "Денежный запас и срок работы"),
                L("Promotion viability", "Окупаемость промоакции"),
            ]
        )
        with cac_tab:
            st.info(
                L(
                    "Contribution-based allowance over a user-defined purchase horizon. This is not LTV. Fixed overhead and taxes are not allocated to customers. Use paid-customer unit margins when available; the current model uses blended margins.",
                    "Допустимые затраты по марже на заданном Вами горизонте покупок. Это не LTV. Постоянные расходы и налоги не распределены на клиентов. Лучше использовать маржу платных клиентов; здесь берётся средняя маржа текущей модели.",
                )
            )
            expected = numeric(
                "acq_orders",
                "Expected placed orders per acquired customer in chosen horizon",
                "Ожидаемые заказы на привлечённого клиента за выбранный горизонт",
                1.0,
                1000,
            )
            horizon = st.text_input(
                L("Purchase horizon / assumption", "Горизонт покупок / допущение"),
                value=st.session_state.get("acquisition_inputs", {}).get(
                    "horizon", L("First order only", "Только первая покупка")
                ),
                key="acq_horizon",
            )
            extra = numeric(
                "acq_extra",
                "Additional service cost per acquired customer",
                "Дополнительное обслуживание привлечённого клиента",
                0.0,
            )
            target = numeric(
                "acq_target",
                "Required contribution per customer after acquisition",
                "Нужная маржа клиента после привлечения",
                0.0,
            )
            new = numeric("acq_new", "Paid new customers", "Новые платные клиенты", 450.0)
            other = numeric(
                "acq_other", "Other acquisition costs in horizon", "Прочие затраты привлечения на горизонте", 2000.0
            )
            cac = numeric("acq_cac", "Observed / assumed CAC", "Наблюдаемый / предполагаемый CAC", 44.44)
            result = acquisition_ceiling(b, expected, extra, target, new, other, cac)
            columns = st.columns(3)
            columns[0].metric(L("Maximum CAC", "Максимальный CAC"), money(result["maximum_cac"]))
            columns[1].metric(
                L("Direct ad allowance", "Допустимая прямая реклама"), money(result["maximum_direct_ad_spend"])
            )
            columns[2].metric(
                L("Contribution payback orders", "Заказов до покрытия привлечения маржой"),
                t("na")
                if result["contribution_payback_orders"] is None
                else f"{result['contribution_payback_orders']:.2f}",
            )
            if result["cac_headroom"] is None or result["cac_headroom"] < 0:
                st.warning(
                    L(
                        "Acquisition exceeds the contribution allowance under these assumptions.",
                        "Привлечение превышает допустимый по марже уровень при этих допущениях.",
                    )
                )
            frame = pd.DataFrame([dict(horizon=horizon, **result)])
            st.session_state.acquisition_inputs = dict(
                expected_orders=expected,
                horizon=horizon,
                extra_customer_cost=extra,
                target_customer_profit=target,
                paid_new=new,
                other_acquisition=other,
                actual_cac=cac,
            )
            csv_download(frame, "acquisition_allowance.csv")
            record_table("acquisition_allowance", frame, b)
        with cash_tab:
            st.warning(
                L(
                    "Separate CASH model. Enter actual/assumed receipts and payments, including taxes, debt and inventory payments if relevant. Operating profit is never copied into cash automatically. Constant monthly flows do not model payment timing within a month.",
                    "Отдельная ДЕНЕЖНАЯ модель. Укажите фактические/ожидаемые поступления и выплаты, включая налоги, долг и закупки, если применимо. Операционная прибыль не копируется в денежный поток автоматически. Постоянные месячные потоки не учитывают даты платежей внутри месяца.",
                )
            )
            st.session_state.setdefault("cash_currency", b.currency)
            if st.session_state.cash_currency != b.currency:
                st.warning(
                    L(
                        "Cash inputs retain their original currency. Switch back or explicitly start a new cash projection.",
                        "Денежные параметры сохраняют исходную валюту. Верните валюту или явно начните новый денежный прогноз.",
                    )
                )
                if st.button(
                    L("Start cash projection in current currency", "Начать денежный прогноз в текущей валюте"),
                    key="reset_cash_currency",
                ):
                    for key in list(st.session_state):
                        if key.startswith("cash_"):
                            del st.session_state[key]
                    st.rerun()
                return
            defaults = st.session_state.get("cash_inputs", {})
            opening = numeric(
                "cash_opening", "Opening cash balance", "Начальный остаток денег", defaults.get("opening_cash", 50000.0)
            )
            receipts = numeric(
                "cash_receipts",
                "Monthly cash receipts",
                "Денежные поступления за месяц",
                defaults.get("monthly_receipts", 0.0),
            )
            payments = numeric(
                "cash_payments",
                "Monthly cash payments",
                "Денежные выплаты за месяц",
                defaults.get("monthly_payments", 0.0),
            )
            buffer = numeric(
                "cash_buffer", "Minimum cash reserve", "Минимальный денежный резерв", defaults.get("buffer", 10000.0)
            )
            months = st.slider(
                L("Cash projection months", "Месяцев денежного прогноза"),
                3,
                36,
                defaults.get("months", 12),
                key="cash_months",
            )
            inputs = dict(
                opening_cash=opening, monthly_receipts=receipts, monthly_payments=payments, buffer=buffer, months=months
            )
            rows, summary = cash_runway(**inputs)
            st.session_state.cash_inputs = inputs
            cols = st.columns(3)
            cols[0].metric(label("net_cash_flow"), money(summary["net_cash_flow"]))
            cols[1].metric(
                L("Cash runway months", "Денежного запаса, месяцев"),
                t("na") if summary["runway_months"] is None else f"{summary['runway_months']:.2f}",
            )
            cols[2].metric(
                L("First month below reserve", "Первый месяц ниже резерва"),
                t("na") if summary["first_buffer_breach_month"] is None else str(summary["first_buffer_breach_month"]),
            )
            st.caption(
                L(
                    "N/A runway means no cash depletion at these constant flows; it is not a guarantee of unlimited business lifetime. Month 0 denotes a reserve already breached at opening.",
                    "Н/Д срока означает отсутствие истощения денег при заданных постоянных потоках, а не гарантию бесконечного срока бизнеса. Месяц 0 — резерв нарушен уже в начальном остатке.",
                )
            )
            table(rows)
            show_chart(
                px.line(
                    rows.rename(columns=label),
                    x=label("month"),
                    y=label("closing_cash"),
                    markers=True,
                    title=L("Cash balance projection", "Проекция остатка денег"),
                ),
                width="stretch",
            )
            csv_download(rows, "cash_runway.csv")
            record_table("cash_runway", rows, b)

        with promo_tab:
            st.info(
                L(
                    "Compare an absolute order discount and an assumed order lift with the current baseline. The tool solves the lift needed to preserve current operating profit. No demand increase is guaranteed; ad spend stays fixed and campaign cost is added once to fixed costs.",
                    "Сравните абсолютную скидку на заказ и предполагаемый прирост заказов с текущей базой. Инструмент рассчитывает прирост для сохранения текущей операционной прибыли. Рост спроса не гарантирован; реклама фиксирована, дополнительные затраты акции добавляются к постоянным расходам один раз.",
                )
            )
            defaults = st.session_state.get("promotion_inputs", {})
            discount = st.slider(
                L("Campaign discount fraction", "Доля скидки по акции"),
                0.0,
                1.0,
                defaults.get("discount", 0.1),
                0.01,
                key="promo_discount",
            )
            lift = st.number_input(
                L("Assumed order volume lift (fraction)", "Предполагаемый прирост заказов (доля)"),
                min_value=-1.0,
                max_value=5.0,
                value=defaults.get("volume_lift", 0.15),
                key="promo_lift",
            )
            cost = numeric(
                "promo_cost",
                "Additional campaign cost",
                "Дополнительные затраты акции",
                defaults.get("campaign_cost", 0.0),
            )
            inputs = dict(discount=discount, volume_lift=lift, campaign_cost=cost)
            result = promotion(b, **inputs)
            st.session_state.promotion_inputs = inputs
            columns = st.columns(3)
            columns[0].metric(
                L("Campaign operating profit", "Операционная прибыль с акцией"), money(result["campaign_profit"])
            )
            columns[1].metric(L("Incremental profit", "Изменение прибыли"), money(result["incremental_profit"]))
            columns[2].metric(
                L("Required order lift to preserve profit", "Прирост заказов для сохранения прибыли"),
                t("na") if result["required_volume_lift"] is None else f"{result['required_volume_lift']:.1%}",
            )
            if result["incremental_profit"] < 0:
                st.warning(
                    L(
                        "The campaign reduces operating profit under the selected volume assumption.",
                        "При выбранном объёме заказов акция снижает операционную прибыль.",
                    )
                )
            if result["campaign_unit_contribution"] <= 0:
                st.warning(
                    L(
                        "Nonpositive order contribution: scaling this campaign cannot create sustainable profitability.",
                        "Неположительная маржа заказа: масштабирование этой акции не создаёт устойчивой прибыльности.",
                    )
                )
            csv_download(pd.DataFrame([result]), "promotion_viability.csv")
            record_table("promotion_viability", pd.DataFrame([result]), b)

    elif page == "risk":
        st.warning(
            L(
                "Synthetic Monte Carlo stress test, NOT a calibrated probability forecast. Independent triangular factor distributions have mode 1 and bounds 1 ± spread. Correlations, market data and capacity constraints are absent. Loss frequency describes ONLY these assumptions.",
                "Синтетический стресс-тест Монте-Карло, НЕ откалиброванный вероятностный прогноз. Независимые треугольные распределения множителей имеют моду 1 и границы 1 ± разброс. Корреляции, рыночные данные и ограничения мощностей не учтены. Частота убытка относится ТОЛЬКО к этим допущениям.",
            )
        )
        with st.expander(L("Stress-test assumptions", "Параметры стресс-теста"), expanded=False):
            inputs = {}
            defaults = st.session_state.get("risk_inputs", {})
            for key, en, rus, default in [
                ("price_spread", "Price spread", "Разброс цены", 0.1),
                ("cost_spread", "COGS spread", "Разброс себестоимости", 0.15),
                ("conversion_spread", "Paid conversion spread", "Разброс платной конверсии", 0.2),
                ("cac_spread", "CAC spread", "Разброс CAC", 0.2),
            ]:
                inputs[key] = st.slider(L(en, rus), 0.0, 0.8, defaults.get(key, default), 0.05, key="risk_" + key)
            inputs["elasticity"] = st.slider(
                L("Price elasticity", "Ценовая эластичность"),
                0.0,
                4.0,
                defaults.get("elasticity", 1.0),
                0.1,
                key="risk_elasticity",
            )
            inputs["budget_factor"] = st.slider(
                L("Budget stress factor", "Стресс-множитель бюджета"),
                0.1,
                3.0,
                defaults.get("budget_factor", 1.0),
                0.1,
                key="risk_budget",
            )
            inputs["scale_penalty"] = st.slider(
                L("CAC saturation", "Насыщение CAC"),
                0.0,
                2.0,
                defaults.get("scale_penalty", 0.25),
                0.05,
                key="risk_scale",
            )
            inputs["samples"] = st.select_slider(
                L("Simulation draws", "Количество испытаний"),
                [500, 1000, 3000, 5000],
                value=defaults.get("samples", 1000),
                key="risk_samples",
            )
            inputs["seed"] = int(
                st.number_input(
                    L("Reproducible seed", "Начальное значение генератора"),
                    0,
                    2**32 - 1,
                    defaults.get("seed", 42),
                    key="risk_seed",
                )
            )
        data, summary = risk_simulation(b, **inputs)
        st.session_state.risk_inputs = inputs
        cols = st.columns(4)
        cols[0].metric(L("Model loss frequency", "Модельная частота убытка"), f"{summary['loss_frequency']:.1%}")
        for col, key, title in zip(cols[1:], ["profit_p10", "profit_median", "profit_p90"], ["P10", "P50", "P90"]):
            col.metric(title + " · " + t("operating_profit"), money(summary[key]))
        show_chart(
            px.histogram(
                data.rename(columns=label),
                x=label("operating_profit"),
                nbins=45,
                title=L("Synthetic operating profit distribution", "Синтетическое распределение операционной прибыли"),
            ),
            width="stretch",
        )
        st.caption(
            L(
                "P10/P50/P90 are sample quantiles, not confidence limits for real profit.",
                "P10/P50/P90 — квантили модельной выборки, не доверительные границы реальной прибыли.",
            )
        )
        csv_download(data, "risk_draws.csv")
        csv_download(pd.DataFrame([dict(**inputs, **summary)]), "risk_assumptions_summary.csv")
        record_table("risk_draws", data, b)
        record_table("risk_assumptions_summary", pd.DataFrame([dict(**inputs, **summary)]), b)


def render_export_center(b, lang):
    ru = lang == "Русский"

    def L(en, rus):
        return rus if ru else en

    st.subheader(L("Excel & CSV export center", "Центр выгрузки Excel и CSV"))
    st.caption(
        L(
            "Excel is a formatted workbook; CSV is a plain data file (UTF-8 with BOM). Both preserve numeric values and source currencies. Undefined results stay blank.",
            "Excel — оформленная книга, CSV — файл данных (UTF-8 с BOM). Оба формата сохраняют числа и исходную валюту. Неопределённые результаты остаются пустыми.",
        )
    )
    journal = None
    if st.session_state.get("project_id"):
        try:
            journal = WorkspaceStore().journal(st.session_state.project_id)
        except (OSError, sqlite3.Error):
            st.warning(L("Journal unavailable in this export.", "Журнал недоступен для этой выгрузки."))
    extras = st.session_state.get("export_tables", {})
    tables = bundle_tables(b, st.session_state.saved, extras, journal)
    if st.session_state.get("marketing_data") is not None:
        m = st.session_state.marketing_data
        metadata = dict(
            currency=st.session_state.get("marketing_currency", b.currency),
            period=st.session_state.get("marketing_period", "month"),
        )
        tables["marketing_inputs.csv"] = pd.DataFrame([dict(**m.__dict__, **metadata)])
        tables["marketing_kpis.csv"] = pd.DataFrame([dict(**marketing(m), **metadata)])
    selected = st.selectbox(L("Table to export", "Таблица для выгрузки"), list(tables), key="export_table")
    with st.expander(L("Preview selected table (first 50 rows)", "Предпросмотр таблицы (первые 50 строк)")):
        st.dataframe(tables[selected].head(50), width="stretch")
    st.download_button(
        L("Download selected CSV", "Скачать выбранный CSV"),
        csv_bytes(tables[selected]),
        selected,
        "text/csv",
        key="download_selected_csv",
    )
    provenance = {
        name: {"currency": item["currency"], "source_business": item["business"]} for name, item in extras.items()
    }
    manifest = dict(
        schema="csv-bundle-1",
        created_at=datetime.now(ZoneInfo("UTC")).isoformat(),
        business=b.dict(),
        analyses=provenance,
        default_forecast=dict(
            months=6,
            demand_growth=0.02,
            cost_growth=0.01,
            budget_growth=0.0,
            fixed_growth=0.0,
            conversion_growth=0.0,
            seasonality=0.0,
            scale_penalty=0.25,
            paid_share=0.6 if b.ad_spend else 0.0,
        ),
        assumptions=st.session_state.get("assumptions", {}),
        notes="Model outputs, not audited actuals. Cash is separate. Saved scenario currencies are preserved. CSV headers are stable technical identifiers.",
    )
    st.download_button(
        L("Download formatted Excel (.xlsx)", "Скачать оформленный Excel (.xlsx)"),
        excel_bytes(tables, manifest, lang, LABELS),
        "business_lab_report.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="download_excel_bundle",
        type="primary",
    )
    st.caption(
        L(
            "Complete workbook: KPI overview, profit chart, table of contents, filters, frozen headers and source assumptions. A snapshot of current calculations; additional analyses appear after visiting their workspaces.",
            "Полная книга: обзор KPI, график прибыли, содержание, фильтры, закреплённые заголовки и исходные допущения. Снимок текущих расчётов; дополнительные анализы появляются после посещения соответствующих разделов.",
        )
    )
    st.download_button(
        L("Download selected table as Excel", "Скачать выбранную таблицу в Excel"),
        excel_bytes({selected: tables[selected]}, {**manifest, "exported_table": selected}, lang, LABELS),
        selected.removesuffix(".csv") + ".xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="download_selected_excel",
    )
    st.caption(L("Tables in the complete workbook: ", "Таблиц в полной книге: ") + str(len(tables)))
    st.download_button(
        L("Download all CSV tables (ZIP)", "Скачать все таблицы CSV (ZIP)"),
        export_zip(tables, manifest),
        "business_lab_csv.zip",
        "application/zip",
        key="download_csv_bundle",
    )
    if any(entry["business"] != b.dict() for entry in extras.values()):
        st.warning(
            L(
                "Some analyses were calculated from an earlier/different baseline. Source inputs are recorded in manifest.json; revisit each workspace to recalculate.",
                "Часть анализов рассчитана по прежней/другой базе. Исходные параметры записаны в manifest.json; откройте нужные разделы для пересчёта.",
            )
        )
    st.caption(
        L(
            "Additional tables appear after visiting the corresponding workspaces. Scenarios, inputs and the explicitly labelled default forecast are always included.",
            "Дополнительные таблицы появляются после посещения соответствующих разделов. Сценарии, исходные параметры и явно обозначенный стандартный прогноз включены всегда.",
        )
    )
