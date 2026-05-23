"""
Edge Agent — generates Cloudflare Workers / Vercel Edge Functions /
Fastly Compute code with KV storage, caching strategies, and geo-routing.

Input:  use_case (str), platform (str), regions (list), cache_strategy (str),
        request_description (str)
Output: worker_code, wrangler_config, cache_headers, deployment_script, code_path
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from src._helpers import _ts, _llm, _save, _parse_json, _record


def edge_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    use_case  = args.get("use_case", "API gateway")
    platform  = args.get("platform", "cloudflare_workers")
    regions: List[str] = args.get("regions", ["us-east", "eu-west", "ap-southeast"])
    cache_strat = args.get("cache_strategy", "stale-while-revalidate")
    req_desc  = args.get("request_description", "handle API requests")

    system = (
        "You are an edge computing expert. Return JSON: "
        "{worker_code:str, wrangler_config_toml:str, "
        "cache_header_rules:[{path_pattern,cache_control,cdn_cache_control}], "
        "kv_schema:object, geo_routing_rules:[{region,handler}], "
        "rate_limiting_code:str, deployment_script:str, "
        "observability_config:object, cold_start_optimizations:[str]}. "
        "Output ONLY valid JSON."
    )
    prompt = (
        f"Use case: {use_case}\nPlatform: {platform}\n"
        f"Regions: {json.dumps(regions)}\nCache: {cache_strat}\n"
        f"Request: {req_desc}\n\nGenerate edge function."
    )

    data = _parse_json(_llm(prompt, system, "edge_agent"), {
        "worker_code": "// edge stub", "wrangler_config_toml": "", "cache_header_rules": [],
    })

    ext_map = {"cloudflare_workers": "js", "vercel_edge": "ts", "fastly": "js"}
    ext = ext_map.get(platform, "js")
    ts = _ts()
    code_path     = _save("code",    f"edge_{platform}_{ts}.{ext}",        data.get("worker_code", ""))
    config_path   = _save("code",    f"wrangler_{ts}.toml",                data.get("wrangler_config_toml", ""))
    deploy_path   = _save("scripts", f"edge_deploy_{platform}_{ts}.sh",    data.get("deployment_script", ""))
    rate_path     = _save("code",    f"edge_rate_limit_{ts}.{ext}",        data.get("rate_limiting_code", ""))

    _record("edge_agent", f"{platform}:{use_case}", code_path)
    return {
        "cache_header_rules":       data.get("cache_header_rules", []),
        "geo_routing_rules":        data.get("geo_routing_rules", []),
        "cold_start_optimizations": data.get("cold_start_optimizations", []),
        "code_path":                code_path,
        "config_path":              config_path,
        "deploy_path":              deploy_path,
        "summary": f"Edge function ({platform}) for '{use_case}'. → {code_path}.",
    }
