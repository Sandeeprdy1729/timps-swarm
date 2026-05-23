"""
Model Evaluator — generates comprehensive eval harnesses, benchmark suites,
and adversarial test cases for any LLM or ML model.

Input:  model_description (str), model_type (str), task (str), metrics (list)
Output: eval_script, benchmark_script, adversarial_inputs, metrics_config,
        eval_path, benchmark_path
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from src._helpers import _ts, _llm, _save, _parse_json, _record


def model_evaluator(args: Dict[str, Any]) -> Dict[str, Any]:
    model_desc = args.get("model_description", "an AI model")
    model_type = args.get("model_type", "llm")
    task       = args.get("task", "general")
    metrics: List[str] = args.get("metrics", [])

    system = (
        "You are an ML evaluation expert. Generate a complete eval harness: "
        "accuracy metrics, edge cases, adversarial inputs, latency benchmarks. "
        "Return JSON: {eval_script:str (pytest file), benchmark_script:str, "
        "adversarial_inputs:[{input,expected_behaviour,attack_type}], "
        "metrics_config:{primary:[str],secondary:[str],guardrails:[str]}, "
        "ragas_config:str}. Output ONLY valid JSON."
    )
    prompt = (
        f"Model: {model_desc}\nType: {model_type}\nTask: {task}\n"
        f"Metrics: {', '.join(metrics) or 'auto'}\n\n"
        "Generate the full evaluation harness."
    )

    data = _parse_json(_llm(prompt, system, "model_evaluator"), {
        "eval_script": "# eval stub", "adversarial_inputs": [], "metrics_config": {},
    })

    eval_path  = _save("tests", f"eval_harness_{_ts()}.py",  data.get("eval_script", ""))
    bench_path = _save("tests", f"benchmark_{_ts()}.py",     data.get("benchmark_script", ""))
    adv_path   = _save("datasets", f"adversarial_{_ts()}.json",
                        json.dumps(data.get("adversarial_inputs", []), indent=2))

    _record("model_evaluator", f"{model_type}:{task}", eval_path)
    return {
        "eval_script":        data.get("eval_script", ""),
        "benchmark_script":   data.get("benchmark_script", ""),
        "adversarial_inputs": data.get("adversarial_inputs", []),
        "metrics_config":     data.get("metrics_config", {}),
        "ragas_config":       data.get("ragas_config", ""),
        "eval_path":          eval_path,
        "benchmark_path":     bench_path,
        "adversarial_path":   adv_path,
        "summary": (
            f"Eval harness for {model_type} ({task}). "
            f"{len(data.get('adversarial_inputs', []))} adversarial inputs. → {eval_path}."
        ),
    }
