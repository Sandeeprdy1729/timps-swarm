"""
Dataset Agent — validates, cleans, and optionally augments training datasets.
Checks class imbalance, label noise, duplicates, schema violations.

Input:  dataset_path (str), task_type (str), augment (bool), target_count (int)
Output: quality_score, issues, class_distribution, data_card, card_path
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from src._helpers import _ts, _llm, _save, _parse_json, _record


def dataset_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    dataset_path = args.get("dataset_path", "")
    task_type    = args.get("task_type", "generation")
    augment      = args.get("augment", False)
    target_count = int(args.get("target_count", 100))

    raw_data = ""
    record_count = 0
    if dataset_path and Path(dataset_path).exists():
        try:
            content = Path(dataset_path).read_text(encoding="utf-8", errors="ignore")
            lines = [l for l in content.splitlines() if l.strip()]
            record_count = len(lines)
            raw_data = "\n".join(lines[:50])
        except Exception as exc:
            raw_data = f"Error reading: {exc}"
    elif args.get("sample_data"):
        raw_data = str(args["sample_data"])[:3000]

    system = (
        "You are a dataset quality expert. Analyse for: class imbalance, label noise, "
        "duplicates, schema violations, missing values, unicode issues. Return JSON: "
        "{quality_score:int(0-100), issues:[{type,severity,count,description,fix}], "
        "class_distribution:{label:count}, recommended_splits:{train,val,test}, "
        "cleaned_sample:str, augmentation_suggestions:[str], data_card:str}. "
        "Output ONLY valid JSON."
    )
    prompt = (
        f"Task: {task_type}  Records: {record_count}  Augment: {augment}  "
        f"Target/class: {target_count}\n\nSample:\n{raw_data[:4000]}"
    )

    data = _parse_json(_llm(prompt, system, "dataset_agent"), {
        "quality_score": 0, "issues": [], "data_card": "No data provided.",
    })

    card_path    = _save("datasets", f"data_card_{_ts()}.md",     data.get("data_card", ""))
    cleaned_path = _save("datasets", f"cleaned_{_ts()}.jsonl",    data.get("cleaned_sample", ""))

    _record("dataset_agent", dataset_path or "inline", f"Quality: {data.get('quality_score',0)}")
    return {
        "quality_score":         data.get("quality_score", 0),
        "issues":                data.get("issues", []),
        "class_distribution":    data.get("class_distribution", {}),
        "recommended_splits":    data.get("recommended_splits", {}),
        "augmentation_suggestions": data.get("augmentation_suggestions", []),
        "data_card":             data.get("data_card", ""),
        "card_path":             card_path,
        "cleaned_path":          cleaned_path,
        "summary": (
            f"Quality: {data.get('quality_score', 0)}/100. "
            f"{len(data.get('issues', []))} issues. "
            f"Data card → {card_path}."
        ),
    }
