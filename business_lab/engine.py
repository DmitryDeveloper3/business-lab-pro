"""Pure financial functions; no UI or state dependencies."""

from dataclasses import replace
import math
from .models import Business, Marketing


def ratio(a, b):
    return a / b if b else None


def economics(b: Business):
    fulfilled = b.orders * (1 - b.returns)
    revenue = fulfilled * b.price * (1 - b.discount)
    cogs = fulfilled * b.unit_cost
    gross = revenue - cogs
    variable = b.orders * b.variable_cost
    fees = revenue * b.payment_rate
    contribution = gross - variable - fees
    operating = contribution - b.ad_spend - b.fixed_cost + b.other_income
    unit_margin = (1 - b.returns) * (b.price * (1 - b.discount) * (1 - b.payment_rate) - b.unit_cost) - b.variable_cost
    burden = max(0, b.fixed_cost + b.ad_spend - b.other_income)
    be_orders = burden / unit_margin if unit_margin > 0 else (0.0 if burden == 0 and unit_margin == 0 else None)
    return dict(
        revenue=revenue,
        cogs=cogs,
        gross_profit=gross,
        variable_costs=variable,
        payment_fees=fees,
        contribution_profit=contribution,
        contribution_margin=ratio(contribution, revenue),
        operating_profit=operating,
        profit_margin=ratio(operating, revenue),
        marketing_spend=b.ad_spend,
        break_even_orders=be_orders,
        minimum_orders=math.ceil(be_orders) if be_orders is not None else None,
        break_even_revenue=be_orders * (1 - b.returns) * b.price * (1 - b.discount) if be_orders is not None else None,
        profit_per_order=ratio(operating, b.orders),
        revenue_per_order=ratio(revenue, b.orders),
        unit_contribution=unit_margin,
        total_costs=cogs + variable + fees + b.ad_spend + b.fixed_cost,
    )


def marketing(m: Marketing):
    return dict(
        ctr=ratio(m.clicks, m.impressions),
        cpc=ratio(m.ad_spend, m.clicks),
        visitor_to_lead=ratio(m.leads, m.visitors),
        lead_to_customer=ratio(m.paid_new + m.organic_new, m.leads),
        cpa=ratio(m.ad_spend, m.orders),
        paid_cac=ratio(m.ad_spend + m.acquisition_other, m.paid_new),
        blended_cac=ratio(m.ad_spend + m.acquisition_other, m.paid_new + m.organic_new),
        roas=ratio(m.attributed_revenue, m.ad_spend),
    )


def simulate(
    b: Business,
    *,
    budget_factor=1.0,
    price_factor=1.0,
    cost_factor=1.0,
    conversion_factor=1.0,
    cac_factor=1.0,
    scale_penalty=0.25,
    elasticity=0.0,
    paid_share=0.6,
    repeat_lift=0.0,
    fixed_factor=1.0,
    returns=None,
):
    for v in (
        budget_factor,
        price_factor,
        cost_factor,
        conversion_factor,
        cac_factor,
        scale_penalty,
        elasticity,
        fixed_factor,
    ):
        if not math.isfinite(v) or v < 0:
            raise ValueError("Scenario factors must be finite and nonnegative")
    if price_factor <= 0 or cac_factor <= 0 or not 0 <= paid_share <= 1 or not 0 <= repeat_lift <= 1:
        raise ValueError("Invalid price/CAC factor or share")
    if b.ad_spend == 0 and paid_share > 0:
        raise ValueError("Zero baseline ad spend requires paid share = 0")
    efficiency = cac_factor * (1 + scale_penalty * max(0, budget_factor - 1))
    paid_orders = b.orders * paid_share * budget_factor / efficiency * conversion_factor
    organic_orders = b.orders * (1 - paid_share)
    orders = (paid_orders + organic_orders) * price_factor ** (-elasticity) * (1 + repeat_lift)
    return replace(
        b,
        orders=orders,
        price=b.price * price_factor,
        unit_cost=b.unit_cost * cost_factor,
        ad_spend=b.ad_spend * budget_factor,
        fixed_cost=b.fixed_cost * fixed_factor,
        returns=b.returns if returns is None else returns,
    )


def forecast(
    b,
    months=6,
    growth=0.02,
    cost_growth=0.01,
    budget_growth=0.0,
    fixed_growth=0.0,
    conversion_growth=0.0,
    seasonality=0.0,
    scale_penalty=0.25,
    paid_share=0.6,
):
    if months not in (3, 6, 12) or any(
        not math.isfinite(v) or v <= -1 for v in (growth, cost_growth, budget_growth, fixed_growth, conversion_growth)
    ):
        raise ValueError("Invalid forecast horizon or growth")
    if not 0 <= seasonality < 1:
        raise ValueError("Seasonality must be in [0,1)")
    rows = []
    for t in range(months):
        model = simulate(
            b,
            budget_factor=(1 + budget_growth) ** t,
            cost_factor=(1 + cost_growth) ** t,
            conversion_factor=(1 + conversion_growth) ** t,
            fixed_factor=(1 + fixed_growth) ** t,
            scale_penalty=scale_penalty,
            paid_share=paid_share,
        )
        model = replace(
            model, orders=model.orders * (1 + growth) ** t * (1 + seasonality * math.sin(2 * math.pi * t / 12))
        )
        rows.append(dict(month=t + 1, orders=model.orders, **economics(model)))
    return rows


def sensitivity(b, **kwargs):
    baseline = economics(simulate(b, **kwargs))["operating_profit"]
    rows = []
    for key in ("price_factor", "cost_factor", "budget_factor", "conversion_factor", "cac_factor", "fixed_factor"):
        for change in (-0.1, 0.1):
            args = dict(kwargs)
            args[key] = args.get(key, 1.0) * (1 + change)
            rows.append(
                dict(
                    parameter=key,
                    change=change,
                    profit_delta=economics(simulate(b, **args))["operating_profit"] - baseline,
                )
            )
    return rows


def insights(b, ru=False):
    e = economics(b)
    out = []
    if e["unit_contribution"] <= 0:
        out.append(
            (
                "Неположительная маржа заказа" if ru else "Nonpositive unit contribution",
                f"{e['unit_contribution']:.2f} {b.currency}",
                "Рост заказов не покрывает переменные затраты. Проверьте цену и себестоимость; спрос может снизиться."
                if ru
                else "More orders cannot cover variable costs. Review price and cost; demand may fall.",
            )
        )
    if e["operating_profit"] < 0:
        out.append(
            (
                "Операционный убыток" if ru else "Operating loss",
                f"{e['operating_profit']:.2f} {b.currency}",
                "Маржи недостаточно для покрытия рекламы и постоянных расходов. Сравните сокращение затрат и рост спроса; расходы считаются постоянными в периоде."
                if ru
                else "Contribution does not cover advertising and overhead. Compare cost reductions and demand growth; costs are fixed within the period.",
            )
        )
    if e["contribution_margin"] is not None and e["contribution_margin"] < 0.3:
        out.append(
            (
                "Низкая маржинальность" if ru else "Thin contribution margin",
                f"{e['contribution_margin']:.1%}",
                "Порог предупреждения 30% условный. Проверьте скидки, возвраты и комиссии; норматив зависит от бизнеса."
                if ru
                else "The 30% warning threshold is illustrative. Review discounts, returns and fees; appropriate margins vary by business.",
            )
        )
    if e["break_even_orders"] is not None and b.orders < e["break_even_orders"]:
        out.append(
            (
                "Недостаточно заказов" if ru else "Orders below break-even",
                f"{b.orders:.0f} / {e['break_even_orders']:.1f}",
                "Порог предполагает неизменные цену, расходы и рекламный бюджет. Рост привлечения может увеличить CAC."
                if ru
                else "Threshold assumes constant price, costs and ad budget. Acquisition growth may increase CAC.",
            )
        )
    return out
