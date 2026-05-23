"""
GraphQL Agent — designs schema, generates resolvers, DataLoader patterns,
subscriptions, and federation config for GraphQL APIs.

Input:  domain_description (str), entities (list), subscriptions (bool),
        federation (bool), framework (str)
Output: schema, resolvers_code, dataloader_code, schema_path
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from src._helpers import _ts, _llm, _save, _parse_json, _record


def graphql_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    domain        = args.get("domain_description", "e-commerce platform")
    entities: List[str] = args.get("entities", ["User", "Product", "Order"])
    subscriptions = args.get("subscriptions", False)
    federation    = args.get("federation", False)
    framework     = args.get("framework", "strawberry")

    system = (
        "You are a GraphQL expert. Return JSON: "
        "{schema:str (SDL), resolvers_code:str, dataloader_code:str, "
        "subscriptions_code:str, federation_config:str, "
        "n_plus_one_analysis:[{query,fix}], "
        "persisted_queries_config:str, error_handling_pattern:str, "
        "auth_directives:str}. Output ONLY valid JSON."
    )
    prompt = (
        f"Domain: {domain}\nEntities: {json.dumps(entities)}\n"
        f"Subscriptions: {subscriptions}\nFederation: {federation}\n"
        f"Framework: {framework}\n\nDesign complete GraphQL API."
    )

    data = _parse_json(_llm(prompt, system, "graphql_agent"), {
        "schema": "# stub", "resolvers_code": "", "dataloader_code": "",
    })

    ts = _ts()
    schema_path     = _save("code", f"graphql_schema_{ts}.graphql",      data.get("schema", ""))
    resolvers_path  = _save("code", f"graphql_resolvers_{framework}_{ts}.py", data.get("resolvers_code", ""))
    loader_path     = _save("code", f"graphql_dataloaders_{ts}.py",      data.get("dataloader_code", ""))
    subs_path       = _save("code", f"graphql_subscriptions_{ts}.py",    data.get("subscriptions_code", ""))

    _record("graphql_agent", f"{framework}:{domain}", schema_path)
    return {
        "n_plus_one_analysis":     data.get("n_plus_one_analysis", []),
        "auth_directives":         data.get("auth_directives", ""),
        "schema_path":             schema_path,
        "resolvers_path":          resolvers_path,
        "dataloader_path":         loader_path,
        "subscriptions_path":      subs_path,
        "summary": f"GraphQL API ({framework}) for '{domain}'. Schema → {schema_path}.",
    }
