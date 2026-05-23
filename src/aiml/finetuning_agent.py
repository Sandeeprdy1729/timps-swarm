"""
Fine-tuning Agent — generates complete fine-tuning pipelines
for LoRA / MLX / Axolotl / Unsloth with config, train script, formatter, eval.

Input:  base_model (str), task_description (str), framework (str),
        lora_rank (int), target_hardware (str), dataset_path (str)
Output: lora_config, config_path, train_path, format_path, eval_path
"""
from __future__ import annotations

import json
from typing import Any, Dict

from src._helpers import _ts, _llm, _save, _parse_json, _record


def finetuning_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    base_model   = args.get("base_model", "qwen2.5:7b")
    task_desc    = args.get("task_description", "general task")
    dataset_path = args.get("dataset_path", "")
    framework    = args.get("framework", "axolotl")
    lora_rank    = int(args.get("lora_rank", 16))
    hardware     = args.get("target_hardware", "nvidia_a100")

    system = (
        "You are an LLM fine-tuning expert. Return JSON: "
        "{lora_config:object, train_script:str, dataset_formatter:str, "
        "eval_script:str, push_script:str, estimated_training_time:str, "
        "estimated_cost:str, hyperparameter_notes:str, config_yaml:str}. "
        "Output ONLY valid JSON."
    )
    prompt = (
        f"Base model: {base_model}\nTask: {task_desc}\nFramework: {framework}\n"
        f"LoRA rank: {lora_rank}\nHardware: {hardware}\n"
        f"Dataset: {dataset_path or 'not specified'}\n\n"
        "Generate the complete fine-tuning pipeline."
    )

    data = _parse_json(_llm(prompt, system, "finetuning_agent"), {
        "config_yaml": "# config stub", "train_script": "", "lora_config": {},
    })

    lora_cfg = data.get("lora_config", {})
    try:
        import yaml
        lora_yaml = yaml.dump(lora_cfg, default_flow_style=False)
    except ImportError:
        lora_yaml = json.dumps(lora_cfg, indent=2)

    ts = _ts()
    config_path = _save("finetune", f"lora_config_{ts}.yaml",      data.get("config_yaml", lora_yaml))
    train_path  = _save("finetune", f"train_{ts}.py",              data.get("train_script", ""))
    format_path = _save("finetune", f"dataset_formatter_{ts}.py",  data.get("dataset_formatter", ""))
    eval_path   = _save("finetune", f"eval_{ts}.py",               data.get("eval_script", ""))
    push_path   = _save("finetune", f"push_to_hub_{ts}.sh",        data.get("push_script", ""))

    _record("finetuning_agent", f"{base_model}/{task_desc}", config_path)
    return {
        "lora_config":             lora_cfg,
        "estimated_training_time": data.get("estimated_training_time", "unknown"),
        "estimated_cost":          data.get("estimated_cost", "unknown"),
        "hyperparameter_notes":    data.get("hyperparameter_notes", ""),
        "config_path":  config_path,
        "train_path":   train_path,
        "format_path":  format_path,
        "eval_path":    eval_path,
        "push_path":    push_path,
        "summary": (
            f"Fine-tune pipeline: {base_model} via {framework}. "
            f"Est. time: {data.get('estimated_training_time', '?')}. → {config_path}."
        ),
    }
