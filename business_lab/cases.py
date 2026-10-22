"""Reproducible synthetic monthly cases, not market benchmarks."""

from dataclasses import replace
from .models import Business

CASES = {
    "store": dict(
        en="E-commerce store",
        ru="Интернет-магазин",
        business=Business(),
        task_en="Compare channel efficiency before changing acquisition spend.",
        task_ru="Сравните эффективность каналов перед изменением бюджета.",
        decision=dict(budget_factor=1.2),
        risk_en="Attribution is illustrative; overhead is shared and not allocated to channels.",
        risk_ru="Атрибуция условная; общие постоянные расходы не распределены по каналам.",
    ),
    "loss": dict(
        en="Unprofitable campaign",
        ru="Убыточная кампания",
        business=replace(Business(), ad_spend=65000),
        task_en="Evaluate a 30% budget reduction while preserving organic demand.",
        task_ru="Оцените сокращение рекламы на 30% с сохранением органического спроса.",
        decision=dict(budget_factor=0.7),
        risk_en="Lower spend may change audience mix; the CAC assumption needs validation.",
        risk_ru="Сокращение бюджета меняет состав аудитории; допущение CAC требует проверки.",
    ),
    "scale": dict(
        en="Scaling decision",
        ru="Решение о масштабировании",
        business=replace(Business(), ad_spend=22000, fixed_cost=19000),
        task_en="Compare doubling the budget with 25% CAC deterioration.",
        task_ru="Сравните удвоение бюджета при ухудшении CAC на 25%.",
        decision=dict(budget_factor=2),
        risk_en="CAC saturation is a user assumption, not a universal marketing law.",
        risk_ru="Насыщение CAC — допущение пользователя, а не универсальный закон маркетинга.",
    ),
    "price": dict(
        en="Pricing strategy",
        ru="Ценовая стратегия",
        business=Business(),
        task_en="Evaluate a 15% price increase with demand elasticity 1.5.",
        task_ru="Оцените повышение цены на 15% при эластичности спроса 1,5.",
        decision=dict(price_factor=1.15, elasticity=1.5),
        risk_en="Constant elasticity is hypothetical; test price changes with real customers.",
        risk_ru="Постоянная эластичность условна; проверьте изменение цены на реальных клиентах.",
    ),
}
