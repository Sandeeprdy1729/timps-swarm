"""
IndieHacker Agent — India-specific GTM and monetisation for bootstrapped products.
INR pricing tiers, Razorpay integration, GST invoicing, community seeding,
Product Hunt India strategy, IndiaStack advantage playbook.

Input:  product_description (str), target_segment (str), monthly_rev_target_inr (int)
Output: pricing_tiers, razorpay_config, gst_invoice_template, gtm_plan,
        community_strategy, code_path
"""
from __future__ import annotations

import json
from typing import Any, Dict

from src._helpers import _ts, _llm, _save, _parse_json, _record


def indiehacker_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    product    = args.get("product_description", "SaaS product")
    segment    = args.get("target_segment", "SMBs in India")
    rev_target = int(args.get("monthly_rev_target_inr", 100000))

    system = (
        "You are an Indian indie-hacker mentor. Return JSON: "
        "{pricing_tiers:[{name,price_inr:int,features:[str],usd_equivalent}], "
        "razorpay_integration_code:str, "
        "gst_invoice_template:str, "
        "gtm_plan:{channels:[{name,action,cost_inr,expected_signups}],"
        "launch_timeline:[{week:int,action}]}, "
        "community_strategy:{communities:[{name,platform,approach}],content_calendar:[str]}, "
        "indiastack_advantages:[str], "
        "indianisation_checklist:[str], "
        "breakeven_analysis:{fixed_costs_inr:int,variable_cost_per_user:int,"
        "breakeven_users:int}}. Output ONLY valid JSON."
    )
    prompt = (
        f"Product: {product}\nTarget: {segment}\n"
        f"Monthly revenue target: ₹{rev_target:,}\n\n"
        "Create India-optimised GTM and monetisation plan."
    )

    data = _parse_json(_llm(prompt, system, "indiehacker_agent"), {
        "pricing_tiers": [], "gtm_plan": {}, "community_strategy": {},
    })

    ts = _ts()
    plan_path   = _save("reports", f"indiehacker_gtm_{ts}.md",
                         json.dumps(data.get("gtm_plan", {}), indent=2))
    code_path   = _save("code", f"razorpay_integration_{ts}.py",
                         data.get("razorpay_integration_code", ""))
    invoice_path = _save("reports", f"gst_invoice_template_{ts}.html",
                          data.get("gst_invoice_template", ""))

    _record("indiehacker_agent", product, plan_path)
    return {
        "pricing_tiers":            data.get("pricing_tiers", []),
        "gtm_plan":                 data.get("gtm_plan", {}),
        "community_strategy":       data.get("community_strategy", {}),
        "indiastack_advantages":    data.get("indiastack_advantages", []),
        "indianisation_checklist":  data.get("indianisation_checklist", []),
        "breakeven_analysis":       data.get("breakeven_analysis", {}),
        "plan_path":                plan_path,
        "code_path":                code_path,
        "invoice_path":             invoice_path,
        "summary": (
            f"India GTM for '{product}'. "
            f"{len(data.get('pricing_tiers', []))} INR tiers. "
            f"GTM → {plan_path}."
        ),
    }
