"""
Monetisation Agent — designs pricing strategy, Stripe/LemonSqueezy integration,
billing webhooks, and revenue optimisation playbook.

Input:  product_description (str), gateway (str), target_markets (list),
        pricing_model (str), monthly_arpu_target (float)
Output: pricing_tiers, stripe_code, webhook_code, revenue_model, code_path
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from src._helpers import _ts, _llm, _save, _parse_json, _record


def monetization_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    product   = args.get("product_description", "SaaS product")
    gateway   = args.get("gateway", "stripe")
    markets: List[str] = args.get("target_markets", ["US", "EU"])
    model     = args.get("pricing_model", "usage_based")
    arpu      = float(args.get("monthly_arpu_target", 50))

    system = (
        "You are a monetisation expert. Return JSON: "
        "{pricing_tiers:[{name,monthly_usd,annual_usd,features:[str],limits:object}], "
        "stripe_products_code:str, checkout_code:str, webhook_handler_code:str, "
        "revenue_model:{mrr_formula:str,ltv_cac_ratio_target:float,"
        "payback_period_months:int}, "
        "dunning_config:object, revenue_optimization_tips:[str], "
        "tax_handling_notes:str, upsell_opportunities:[str]}. "
        "Output ONLY valid JSON."
    )
    prompt = (
        f"Product: {product}\nGateway: {gateway}\nMarkets: {json.dumps(markets)}\n"
        f"Model: {model}\nARPU target: ${arpu}/mo\n\n"
        "Generate complete monetisation setup."
    )

    data = _parse_json(_llm(prompt, system, "monetization_agent"), {
        "pricing_tiers": [], "stripe_products_code": "", "revenue_model": {},
    })

    ts = _ts()
    stripe_path  = _save("code", f"{gateway}_integration_{ts}.py",  data.get("stripe_products_code", ""))
    checkout_path = _save("code", f"checkout_{ts}.py",              data.get("checkout_code", ""))
    webhook_path  = _save("code", f"billing_webhook_{ts}.py",       data.get("webhook_handler_code", ""))

    _record("monetization_agent", f"{gateway}:{product}", stripe_path)
    return {
        "pricing_tiers":           data.get("pricing_tiers", []),
        "revenue_model":           data.get("revenue_model", {}),
        "revenue_optimization_tips": data.get("revenue_optimization_tips", []),
        "upsell_opportunities":    data.get("upsell_opportunities", []),
        "tax_handling_notes":      data.get("tax_handling_notes", ""),
        "stripe_path":             stripe_path,
        "checkout_path":           checkout_path,
        "webhook_path":            webhook_path,
        "summary": (
            f"Monetisation ({gateway}) for '{product}'. "
            f"{len(data.get('pricing_tiers', []))} tiers. → {stripe_path}."
        ),
    }
