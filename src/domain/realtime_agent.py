"""
Realtime Agent — designs real-time communication layers using
WebSocket, SSE, Redis Pub/Sub, or Kafka.

Input:  use_case (str), transport (str), scale (str), framework (str)
Output: server_code, client_code, redis_config, code_path
"""
from __future__ import annotations

from typing import Any, Dict

from src._helpers import _ts, _llm, _save, _parse_json, _record


def realtime_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    use_case  = args.get("use_case", "live chat")
    transport = args.get("transport", "websocket")
    scale     = args.get("scale", "medium")
    framework = args.get("framework", "fastapi")

    system = (
        "You are a real-time systems expert. Return JSON: "
        "{server_code:str, client_code:str, redis_pub_sub_config:object, "
        "message_schema:object, reconnection_strategy:str, "
        "horizontal_scaling_notes:str, backpressure_handling:str, "
        "load_balancer_config:str, estimated_connections_per_node:int}. "
        "Output ONLY valid JSON."
    )
    prompt = (
        f"Use case: {use_case}\nTransport: {transport}\n"
        f"Scale: {scale}\nFramework: {framework}\n\n"
        "Generate production realtime system."
    )

    data = _parse_json(_llm(prompt, system, "realtime_agent"), {
        "server_code": "# server stub", "client_code": "", "redis_pub_sub_config": {},
    })

    ts = _ts()
    server_path = _save("code", f"realtime_server_{transport}_{ts}.py", data.get("server_code", ""))
    client_path = _save("code", f"realtime_client_{transport}_{ts}.js",  data.get("client_code", ""))

    _record("realtime_agent", f"{transport}:{use_case}", server_path)
    return {
        "message_schema":         data.get("message_schema", {}),
        "reconnection_strategy":  data.get("reconnection_strategy", ""),
        "horizontal_scaling_notes": data.get("horizontal_scaling_notes", ""),
        "estimated_connections":  data.get("estimated_connections_per_node", 0),
        "server_path":            server_path,
        "client_path":            client_path,
        "summary": f"Realtime ({transport}/{framework}) for '{use_case}'. Server → {server_path}.",
    }
