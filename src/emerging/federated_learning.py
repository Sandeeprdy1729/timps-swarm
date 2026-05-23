"""
Federated Learning Agent — designs FL training pipelines using
Flower / PySyft with differential privacy and FedAvg/FedProx.

Input:  model_description (str), data_description (str), n_clients (int),
        framework (str), privacy_budget_epsilon (float)
Output: server_code, client_code, dp_config, aggregation_strategy, code_path
"""
from __future__ import annotations

from typing import Any, Dict

from src._helpers import _ts, _llm, _save, _parse_json, _record


def federated_learning(args: Dict[str, Any]) -> Dict[str, Any]:
    model_desc  = args.get("model_description", "classification model")
    data_desc   = args.get("data_description", "distributed healthcare data")
    n_clients   = int(args.get("n_clients", 10))
    framework   = args.get("framework", "flower")
    epsilon     = float(args.get("privacy_budget_epsilon", 1.0))

    system = (
        "You are a federated learning expert. Return JSON: "
        "{server_code:str (Python), client_code:str, "
        "dp_config:{mechanism,epsilon,delta,noise_multiplier,max_grad_norm}, "
        "aggregation_strategy:str, communication_plan:str, "
        "convergence_analysis:str, privacy_accounting_code:str, "
        "docker_compose_yaml:str, benchmark_script:str}. "
        "Output ONLY valid JSON."
    )
    prompt = (
        f"Model: {model_desc}\nData: {data_desc}\n"
        f"Clients: {n_clients}\nFramework: {framework}\n"
        f"Privacy budget ε={epsilon}\n\nGenerate FL pipeline."
    )

    data = _parse_json(_llm(prompt, system, "federated_learning"), {
        "server_code": "# server stub", "client_code": "", "dp_config": {},
    })

    ts = _ts()
    server_path  = _save("code",    f"fl_server_{framework}_{ts}.py",     data.get("server_code", ""))
    client_path  = _save("code",    f"fl_client_{framework}_{ts}.py",     data.get("client_code", ""))
    dp_path      = _save("code",    f"dp_accounting_{ts}.py",             data.get("privacy_accounting_code", ""))
    docker_path  = _save("scripts", f"fl_docker_{ts}.yml",                data.get("docker_compose_yaml", ""))

    _record("federated_learning", f"{framework}:{model_desc}", server_path)
    return {
        "dp_config":             data.get("dp_config", {}),
        "aggregation_strategy":  data.get("aggregation_strategy", "FedAvg"),
        "communication_plan":    data.get("communication_plan", ""),
        "convergence_analysis":  data.get("convergence_analysis", ""),
        "server_path":           server_path,
        "client_path":           client_path,
        "dp_path":               dp_path,
        "docker_path":           docker_path,
        "summary": (
            f"FL pipeline ({framework}): {n_clients} clients, ε={epsilon}. → {server_path}."
        ),
    }
