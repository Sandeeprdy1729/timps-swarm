"""
AI/ML Agents — 7 specialist agents for teams building AI products.

  prompt_engineer     — find & rewrite prompts in codebases with CoT, few-shot
  dataset_agent       — validate, clean, augment training datasets
  model_evaluator     — write eval harnesses + benchmark suites for any model
  rag_designer        — design optimal RAG pipelines (chunking, retrieval, reranking)
  finetuning_agent    — generate full fine-tuning pipelines (LoRA / MLX / Axolotl)
  ai_safety_agent     — OWASP LLM Top 10 audit for AI applications
  vector_db_agent     — schema design for Qdrant / Pinecone / Weaviate

All follow the same contract: fn(args: dict) -> dict
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from src.llm_router import LLMRouter
from src.memory import record_run

logger = logging.getLogger(__name__)

_GEN = Path(os.getenv("GENERATED_DIR", "generated"))


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _llm(prompt: str, system: str, agent: str = "default") -> str:
    try:
        return LLMRouter().call(agent, prompt, system)
    except Exception as exc:
        logger.error("LLM error [%s]: %s", agent, exc)
        return f"# LLM error: {exc}"


def _strip_fences(text: str, lang: str = "") -> str:
    pattern = rf"```{re.escape(lang)}\s*([\s\S]*?)```"
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m else text.strip()


def _save(sub: str, name: str, content: str) -> str:
    path = _GEN / sub / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


# ─────────────────────────────────────────────────────────────────────────────
# 1 — PROMPT ENGINEER
# Finds hardcoded prompts in a codebase and rewrites them properly.
# ─────────────────────────────────────────────────────────────────────────────

def prompt_engineer(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scan a codebase for hardcoded prompts and rewrite them with best practices.

    Args:
      code (str): Source code to scan OR
      path (str): Path to scan.
      task (str): What the AI application does (for context).
      style (str): 'chain_of_thought' | 'few_shot' | 'structured_output' | 'auto'.
    """
    code    = args.get("code", "")
    path_str = args.get("path", "")
    task    = args.get("task", "AI application")
    style   = args.get("style", "auto")

    if not code and path_str:
        p = Path(path_str)
        if p.is_file():
            code = p.read_text(encoding="utf-8", errors="ignore")
        elif p.is_dir():
            parts = []
            for f in list(p.rglob("*.py"))[:10]:
                parts.append(f.read_text(encoding="utf-8", errors="ignore")[:1000])
            code = "\n\n".join(parts)

    system = (
        "You are a prompt engineering expert. Scan code for LLM prompts and rewrite them using: "
        "chain-of-thought reasoning, XML tags for structure, few-shot examples, output schemas, "
        "proper temperature/top_p guidance, and system/user separation. "
        "Return JSON: {found_prompts: [{location, original, issues: [string]}], "
        "rewritten_prompts: [{location, original, rewritten, techniques_applied: [string], "
        "expected_quality_gain: string}], "
        "missing_system_prompts: [string], "
        "unstructured_outputs: [string], "
        "instrumented_code: string, "
        "benchmark_plan: string}. Output ONLY valid JSON."
    )
    prompt = (
        f"Application task: {task}\nPreferred style: {style}\n\n"
        f"Source code:\n```python\n{code[:7000]}\n```"
    )

    raw = _llm(prompt, system, "prompt_engineer")
    try:
        data = json.loads(_strip_fences(raw, "json"))
    except json.JSONDecodeError:
        data = {"found_prompts": [], "rewritten_prompts": [], "instrumented_code": raw}

    rewritten = data.get("rewritten_prompts", [])

    report = (
        f"# Prompt Engineer Report — {_ts()}\n\n"
        f"**Task:** {task}  **Style:** {style}\n"
        f"**Prompts found:** {len(data.get('found_prompts', []))}  "
        f"**Rewritten:** {len(rewritten)}\n\n"
        "## Rewrites\n"
        + "\n".join(
            f"### {r.get('location', '?')}\n"
            f"**Original:** `{r.get('original', '')[:100]}`\n"
            f"**Techniques:** {', '.join(r.get('techniques_applied', []))}\n"
            f"**Expected gain:** {r.get('expected_quality_gain', '')}\n"
            f"```python\n{r.get('rewritten', '')}\n```\n"
            for r in rewritten
        )
        + "\n\n## Missing System Prompts\n"
        + "\n".join(f"- {m}" for m in data.get("missing_system_prompts", []))
        + "\n\n## Benchmark Plan\n"
        + data.get("benchmark_plan", "")
    )

    report_path = _save("reports", f"prompt_engineer_{_ts()}.md", report)
    if data.get("instrumented_code"):
        _save("code", f"prompts_rewritten_{_ts()}.py", data["instrumented_code"])

    record_run("prompt_engineer", task, report[:400])
    return {
        "found_prompts": data.get("found_prompts", []),
        "rewritten_prompts": rewritten,
        "missing_system_prompts": data.get("missing_system_prompts", []),
        "instrumented_code": data.get("instrumented_code", ""),
        "benchmark_plan": data.get("benchmark_plan", ""),
        "report_path": report_path,
        "summary": (
            f"Found {len(data.get('found_prompts', []))} prompts, "
            f"rewrote {len(rewritten)} with {style} style."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2 — DATASET AGENT
# Validates, cleans, and augments training datasets.
# ─────────────────────────────────────────────────────────────────────────────

def dataset_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate, clean, and optionally augment a training dataset.

    Args:
      dataset_path (str): Path to JSONL/CSV/JSON dataset.
      task_type (str): 'classification' | 'generation' | 'qa' | 'ner' | 'ranking'.
      augment (bool): Generate synthetic examples to balance classes (default False).
      target_count (int): Target records per class for augmentation (default 100).
    """
    dataset_path = args.get("dataset_path", "")
    task_type    = args.get("task_type", "generation")
    augment      = args.get("augment", False)
    target_count = int(args.get("target_count", 100))

    # Read dataset
    raw_data = ""
    record_count = 0
    if dataset_path and Path(dataset_path).exists():
        try:
            content = Path(dataset_path).read_text(encoding="utf-8", errors="ignore")
            lines = [l for l in content.splitlines() if l.strip()]
            record_count = len(lines)
            raw_data = "\n".join(lines[:50])  # first 50 for analysis
        except Exception as exc:
            raw_data = f"Error reading: {exc}"
    elif args.get("sample_data"):
        raw_data = str(args["sample_data"])[:3000]

    system = (
        "You are a dataset quality expert. Analyse a dataset sample for: "
        "class imbalance (Gini coefficient), label noise, duplicate records, schema violations, "
        "missing values, unicode issues, and annotation quality. "
        "Return JSON: {quality_score: int (0-100), "
        "issues: [{type, severity, count, description, fix}], "
        "class_distribution: {label: count}, "
        "recommended_splits: {train: float, val: float, test: float}, "
        "cleaned_sample: string (first 5 cleaned records in JSONL), "
        "augmentation_suggestions: [string], "
        "data_card: string (markdown summary)}. Output ONLY valid JSON."
    )
    prompt = (
        f"Task type: {task_type}  Total records: {record_count}\n"
        f"Augment: {augment}  Target per class: {target_count}\n\n"
        f"Dataset sample:\n{raw_data[:4000]}"
    )

    raw = _llm(prompt, system, "dataset_agent")
    try:
        data = json.loads(_strip_fences(raw, "json"))
    except json.JSONDecodeError:
        data = {"quality_score": 0, "issues": [], "data_card": raw}

    data_card = data.get("data_card", "")
    cleaned   = data.get("cleaned_sample", "")

    card_path    = _save("datasets", f"data_card_{_ts()}.md", data_card)
    cleaned_path = _save("datasets", f"cleaned_{_ts()}.jsonl", cleaned)

    record_run("dataset_agent", dataset_path or "inline", data_card[:400])
    return {
        "quality_score": data.get("quality_score", 0),
        "issues": data.get("issues", []),
        "class_distribution": data.get("class_distribution", {}),
        "recommended_splits": data.get("recommended_splits", {}),
        "augmentation_suggestions": data.get("augmentation_suggestions", []),
        "data_card": data_card,
        "card_path": card_path,
        "cleaned_path": cleaned_path,
        "summary": (
            f"Quality score: {data.get('quality_score', 0)}/100. "
            f"{len(data.get('issues', []))} issues found. "
            f"Data card at {card_path}."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3 — MODEL EVALUATOR
# Generates comprehensive eval harnesses for any LLM or ML model.
# ─────────────────────────────────────────────────────────────────────────────

def model_evaluator(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate an evaluation harness for an ML model or LLM.

    Args:
      model_description (str): What the model does.
      model_type (str): 'llm' | 'classifier' | 'regressor' | 'rag' | 'embedding'.
      task (str): The downstream task (e.g. 'sentiment analysis', 'code generation').
      metrics (list[str]): Desired metrics (auto-selected if empty).
    """
    model_desc  = args.get("model_description", "an AI model")
    model_type  = args.get("model_type", "llm")
    task        = args.get("task", "general")
    metrics     = args.get("metrics", [])

    system = (
        "You are an ML evaluation expert. Generate a complete eval harness including: "
        "accuracy metrics, edge case tests, adversarial inputs, latency benchmarks, "
        "failure mode analysis. Return JSON: "
        "{eval_script: string (complete pytest file), "
        "benchmark_script: string (latency/throughput test), "
        "adversarial_inputs: [{input, expected_behaviour, attack_type}], "
        "metrics_config: {primary: [string], secondary: [string], guardrails: [string]}, "
        "evaluation_report_template: string, "
        "ragas_config: string (for RAG evals, else empty)}. Output ONLY valid JSON."
    )
    prompt = (
        f"Model: {model_desc}\nType: {model_type}\nTask: {task}\n"
        f"Required metrics: {', '.join(metrics) or 'auto-select'}\n\n"
        "Generate the full evaluation harness."
    )

    raw = _llm(prompt, system, "model_evaluator")
    try:
        data = json.loads(_strip_fences(raw, "json"))
    except json.JSONDecodeError:
        data = {"eval_script": raw, "adversarial_inputs": [], "metrics_config": {}}

    eval_path  = _save("tests", f"eval_harness_{_ts()}.py", data.get("eval_script", ""))
    bench_path = _save("tests", f"benchmark_{_ts()}.py",    data.get("benchmark_script", ""))
    adv_path   = _save("datasets", f"adversarial_inputs_{_ts()}.json",
                        json.dumps(data.get("adversarial_inputs", []), indent=2))

    record_run("model_evaluator", f"{model_type}:{task}", eval_path)
    return {
        "eval_script": data.get("eval_script", ""),
        "benchmark_script": data.get("benchmark_script", ""),
        "adversarial_inputs": data.get("adversarial_inputs", []),
        "metrics_config": data.get("metrics_config", {}),
        "ragas_config": data.get("ragas_config", ""),
        "eval_path": eval_path,
        "benchmark_path": bench_path,
        "adversarial_path": adv_path,
        "summary": (
            f"Eval harness for {model_type} ({task}) generated. "
            f"{len(data.get('adversarial_inputs', []))} adversarial inputs. "
            f"Scripts at {eval_path}."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4 — RAG DESIGNER
# Designs optimal RAG pipelines end-to-end.
# ─────────────────────────────────────────────────────────────────────────────

def rag_designer(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Design an optimal Retrieval-Augmented Generation pipeline.

    Args:
      doc_description (str): What documents will be indexed.
      query_examples (list[str]): Example queries users will ask.
      context_window (int): Target LLM context window in tokens (default 8192).
      latency_slo_ms (int): Max acceptable latency in ms (default 500).
      framework (str): 'llamaindex' | 'langchain' | 'custom' (default 'llamaindex').
    """
    doc_desc    = args.get("doc_description", "enterprise documents")
    queries     = args.get("query_examples", ["What is the policy on X?"])
    ctx_window  = int(args.get("context_window", 8192))
    latency_slo = int(args.get("latency_slo_ms", 500))
    framework   = args.get("framework", "llamaindex")

    system = (
        "You are a RAG architecture expert. Design the optimal RAG pipeline. "
        "Return JSON: {chunking: {strategy: string, chunk_size: int, overlap: int, rationale: string}, "
        "embedding: {model: string, dimensions: int, provider: string, rationale: string}, "
        "retrieval: {method: string, top_k: int, reranker: string, hybrid_alpha: float}, "
        "rag_config_yaml: string (complete config file), "
        "pipeline_code: string (Python implementation), "
        "index_setup_code: string, "
        "query_pipeline_code: string, "
        "performance_estimates: {index_time_per_doc_ms: int, query_latency_ms: int, "
        "storage_per_1k_docs_mb: float}, "
        "tradeoffs: [string]}. Output ONLY valid JSON."
    )
    prompt = (
        f"Document corpus: {doc_desc}\n"
        f"Example queries: {json.dumps(queries[:5])}\n"
        f"LLM context window: {ctx_window} tokens\n"
        f"Latency SLO: {latency_slo}ms\n"
        f"Framework: {framework}\n\n"
        "Design the optimal RAG pipeline."
    )

    raw = _llm(prompt, system, "rag_designer")
    try:
        data = json.loads(_strip_fences(raw, "json"))
    except json.JSONDecodeError:
        data = {"rag_config_yaml": raw, "pipeline_code": "", "chunking": {}, "embedding": {}}

    config_path   = _save("rag", f"rag_config_{_ts()}.yaml",   data.get("rag_config_yaml", ""))
    pipeline_path = _save("rag", f"rag_pipeline_{_ts()}.py",   data.get("pipeline_code", ""))
    index_path    = _save("rag", f"index_setup_{_ts()}.py",    data.get("index_setup_code", ""))
    query_path    = _save("rag", f"query_pipeline_{_ts()}.py", data.get("query_pipeline_code", ""))

    record_run("rag_designer", doc_desc, config_path)
    return {
        "chunking":   data.get("chunking", {}),
        "embedding":  data.get("embedding", {}),
        "retrieval":  data.get("retrieval", {}),
        "performance_estimates": data.get("performance_estimates", {}),
        "tradeoffs":  data.get("tradeoffs", []),
        "config_path": config_path,
        "pipeline_path": pipeline_path,
        "index_path": index_path,
        "query_path": query_path,
        "summary": (
            f"RAG pipeline designed: {data.get('chunking', {}).get('strategy', '?')} chunking, "
            f"{data.get('embedding', {}).get('model', '?')} embeddings, "
            f"{data.get('retrieval', {}).get('method', '?')} retrieval. "
            f"Config at {config_path}."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5 — FINE-TUNING AGENT
# Generates complete fine-tuning pipelines for LoRA/MLX/Axolotl/Unsloth.
# ─────────────────────────────────────────────────────────────────────────────

def finetuning_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a complete fine-tuning pipeline for an LLM.

    Args:
      base_model (str): e.g. 'qwen2.5:7b', 'llama-3.1-8b', 'mistral-7b'.
      task_description (str): What the model should learn.
      dataset_path (str): Path to training dataset.
      framework (str): 'mlx' | 'axolotl' | 'unsloth' | 'transformers' (default 'axolotl').
      lora_rank (int): LoRA rank (default 16).
      target_hardware (str): 'apple_silicon' | 'nvidia_a100' | 'nvidia_rtx' | 'cpu'.
    """
    base_model    = args.get("base_model", "qwen2.5:7b")
    task_desc     = args.get("task_description", "general task")
    dataset_path  = args.get("dataset_path", "")
    framework     = args.get("framework", "axolotl")
    lora_rank     = int(args.get("lora_rank", 16))
    hardware      = args.get("target_hardware", "nvidia_a100")

    system = (
        "You are an LLM fine-tuning expert. Generate a complete fine-tuning pipeline. "
        "Return JSON: {lora_config: object (YAML-serialisable dict), "
        "train_script: string (Python training script), "
        "dataset_formatter: string (Python script to format data), "
        "eval_script: string, "
        "push_script: string (HuggingFace Hub push), "
        "estimated_training_time: string, "
        "estimated_cost: string, "
        "hyperparameter_notes: string, "
        "config_yaml: string (complete Axolotl/MLX config)}. Output ONLY valid JSON."
    )
    prompt = (
        f"Base model: {base_model}\n"
        f"Task: {task_desc}\n"
        f"Framework: {framework}\n"
        f"LoRA rank: {lora_rank}\n"
        f"Hardware: {hardware}\n"
        f"Dataset: {dataset_path or 'not specified'}\n\n"
        "Generate the complete fine-tuning pipeline."
    )

    raw = _llm(prompt, system, "finetuning_agent")
    try:
        data = json.loads(_strip_fences(raw, "json"))
    except json.JSONDecodeError:
        data = {"config_yaml": raw, "train_script": "", "lora_config": {}}

    lora_cfg = data.get("lora_config", {})
    try:
        import yaml
        lora_yaml = yaml.dump(lora_cfg, default_flow_style=False)
    except ImportError:
        lora_yaml = json.dumps(lora_cfg, indent=2)

    config_path   = _save("finetune", f"lora_config_{_ts()}.yaml",       data.get("config_yaml", lora_yaml))
    train_path    = _save("finetune", f"train_{_ts()}.py",               data.get("train_script", ""))
    format_path   = _save("finetune", f"dataset_formatter_{_ts()}.py",   data.get("dataset_formatter", ""))
    eval_path     = _save("finetune", f"eval_{_ts()}.py",                data.get("eval_script", ""))
    push_path     = _save("finetune", f"push_to_hub_{_ts()}.sh",         data.get("push_script", ""))

    record_run("finetuning_agent", f"{base_model}/{task_desc}", config_path)
    return {
        "lora_config": lora_cfg,
        "estimated_training_time": data.get("estimated_training_time", "unknown"),
        "estimated_cost": data.get("estimated_cost", "unknown"),
        "hyperparameter_notes": data.get("hyperparameter_notes", ""),
        "config_path": config_path,
        "train_path": train_path,
        "format_path": format_path,
        "eval_path": eval_path,
        "push_path": push_path,
        "summary": (
            f"Fine-tuning pipeline for {base_model} ({framework}) generated. "
            f"Estimated time: {data.get('estimated_training_time', '?')}. "
            f"Config at {config_path}."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 6 — AI SAFETY AGENT
# OWASP LLM Top 10 audit for AI applications.
# ─────────────────────────────────────────────────────────────────────────────

def ai_safety_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Audit an AI application for safety and alignment issues.

    Args:
      code (str): Source code to audit OR
      path (str): Path to scan.
      app_description (str): What the AI app does (for context).
      strictness (str): 'standard' | 'strict' | 'paranoid' (default 'standard').
    """
    code         = args.get("code", "")
    path_str     = args.get("path", "")
    app_desc     = args.get("app_description", "an AI application")
    strictness   = args.get("strictness", "standard")

    if not code and path_str:
        p = Path(path_str)
        if p.is_file():
            code = p.read_text(encoding="utf-8", errors="ignore")
        elif p.is_dir():
            parts = []
            for f in list(p.rglob("*.py"))[:10]:
                parts.append(f.read_text(encoding="utf-8", errors="ignore")[:800])
            code = "\n\n".join(parts)

    system = (
        "You are an AI safety expert specialising in OWASP LLM Top 10. "
        "Audit the code for all 10 LLM vulnerabilities plus alignment issues. "
        "Return JSON: {overall_risk: 'critical'|'high'|'medium'|'low', "
        "findings: [{id: 'LLM01'|..., title: string, severity: string, "
        "code_location: string, description: string, fix: string, cwe: string}], "
        "prompt_injection_vectors: [string], "
        "sensitive_data_exposure: [string], "
        "excessive_agency_risks: [string], "
        "guardrail_recommendations: [string], "
        "remediation_code: string, "
        "compliance_notes: string}. Output ONLY valid JSON.\n\n"
        "OWASP LLM Top 10:\n"
        "LLM01: Prompt Injection\nLLM02: Insecure Output Handling\n"
        "LLM03: Training Data Poisoning\nLLM04: Model Denial of Service\n"
        "LLM05: Supply Chain Vulnerabilities\nLLM06: Sensitive Info Disclosure\n"
        "LLM07: Insecure Plugin Design\nLLM08: Excessive Agency\n"
        "LLM09: Overreliance\nLLM10: Model Theft"
    )
    prompt = (
        f"Application: {app_desc}\nStrictness: {strictness}\n\n"
        f"Source code:\n```python\n{code[:7000]}\n```"
    )

    raw = _llm(prompt, system, "ai_safety_agent")
    try:
        data = json.loads(_strip_fences(raw, "json"))
    except json.JSONDecodeError:
        data = {"overall_risk": "unknown", "findings": [], "guardrail_recommendations": [raw]}

    findings = data.get("findings", [])
    critical = [f for f in findings if f.get("severity") in ("critical", "high")]

    report = (
        f"# AI Safety Audit — {_ts()}\n\n"
        f"**Application:** {app_desc}  **Risk Level:** {data.get('overall_risk', '?').upper()}\n"
        f"**Findings:** {len(findings)} ({len(critical)} critical/high)\n\n"
        "## Findings\n"
        + "\n".join(
            f"### {f.get('id', '?')}: {f.get('title', '?')} [{f.get('severity', '?').upper()}]\n"
            f"**Location:** {f.get('code_location', 'N/A')}\n"
            f"**Description:** {f.get('description', '')}\n"
            f"**Fix:** {f.get('fix', '')}\n"
            for f in findings
        )
        + "\n\n## Guardrail Recommendations\n"
        + "\n".join(f"- {g}" for g in data.get("guardrail_recommendations", []))
    )

    report_path = _save("reports", f"ai_safety_{_ts()}.md", report)
    if data.get("remediation_code"):
        _save("code", f"ai_safety_fixes_{_ts()}.py", data["remediation_code"])

    record_run("ai_safety_agent", app_desc, f"Risk: {data.get('overall_risk')} | {len(findings)} findings")
    return {
        "overall_risk": data.get("overall_risk", "unknown"),
        "findings": findings,
        "critical_count": len(critical),
        "prompt_injection_vectors": data.get("prompt_injection_vectors", []),
        "sensitive_data_exposure": data.get("sensitive_data_exposure", []),
        "excessive_agency_risks": data.get("excessive_agency_risks", []),
        "guardrail_recommendations": data.get("guardrail_recommendations", []),
        "report_path": report_path,
        "summary": (
            f"AI safety audit complete. Risk: {data.get('overall_risk', '?').upper()}. "
            f"{len(findings)} findings ({len(critical)} critical/high). "
            f"Report at {report_path}."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 7 — VECTOR DB AGENT
# Schema design and query code for Qdrant / Pinecone / Weaviate.
# ─────────────────────────────────────────────────────────────────────────────

def vector_db_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Design an optimal vector database schema and generate integration code.

    Args:
      data_description (str): What data will be embedded and stored.
      query_patterns (list[str]): Typical query types.
      provider (str): 'qdrant' | 'pinecone' | 'weaviate' | 'pgvector' (default 'qdrant').
      embedding_dim (int): Vector dimensions (default 1536).
      expected_scale (str): 'small (<100k)' | 'medium (<10M)' | 'large (>10M)'.
    """
    data_desc    = args.get("data_description", "text documents")
    queries      = args.get("query_patterns", ["semantic search"])
    provider     = args.get("provider", "qdrant")
    emb_dim      = int(args.get("embedding_dim", 1536))
    scale        = args.get("expected_scale", "medium (<10M)")

    system = (
        "You are a vector database architect. Design optimal schema and generate production code. "
        "Return JSON: {collection_schema: object, "
        "hnsw_config: {m: int, ef_construct: int, ef: int}, "
        "metadata_fields: [{name, type, indexed: bool, rationale}], "
        "upsert_code: string (Python), "
        "query_code: string (Python, includes hybrid search if appropriate), "
        "batch_import_code: string, "
        "index_config: object, "
        "performance_tips: [string], "
        "estimated_storage_gb_per_1m_docs: float}. Output ONLY valid JSON."
    )
    prompt = (
        f"Provider: {provider}\nData: {data_desc}\n"
        f"Query patterns: {json.dumps(queries[:5])}\n"
        f"Embedding dimensions: {emb_dim}\n"
        f"Expected scale: {scale}\n\n"
        "Design the optimal vector DB schema and integration."
    )

    raw = _llm(prompt, system, "vector_db_agent")
    try:
        data = json.loads(_strip_fences(raw, "json"))
    except json.JSONDecodeError:
        data = {"upsert_code": raw, "query_code": "", "collection_schema": {}}

    schema_path = _save("vector_db", f"{provider}_schema_{_ts()}.json",
                         json.dumps(data.get("collection_schema", {}), indent=2))
    upsert_path = _save("vector_db", f"{provider}_upsert_{_ts()}.py",
                         data.get("upsert_code", ""))
    query_path  = _save("vector_db", f"{provider}_query_{_ts()}.py",
                         data.get("query_code", ""))
    batch_path  = _save("vector_db", f"{provider}_batch_import_{_ts()}.py",
                         data.get("batch_import_code", ""))

    record_run("vector_db_agent", f"{provider}:{data_desc}", schema_path)
    return {
        "collection_schema": data.get("collection_schema", {}),
        "hnsw_config": data.get("hnsw_config", {}),
        "metadata_fields": data.get("metadata_fields", []),
        "performance_tips": data.get("performance_tips", []),
        "estimated_storage_gb": data.get("estimated_storage_gb_per_1m_docs", 0),
        "schema_path": schema_path,
        "upsert_path": upsert_path,
        "query_path": query_path,
        "batch_path": batch_path,
        "summary": (
            f"Vector DB schema for {provider} designed. "
            f"{len(data.get('metadata_fields', []))} metadata fields. "
            f"Upsert + query code at {upsert_path} / {query_path}."
        ),
    }


# ── Dispatch table ────────────────────────────────────────────────────────────

AIML_AGENTS: Dict[str, Any] = {
    "prompt_engineer":  prompt_engineer,
    "dataset_agent":    dataset_agent,
    "model_evaluator":  model_evaluator,
    "rag_designer":     rag_designer,
    "finetuning_agent": finetuning_agent,
    "ai_safety_agent":  ai_safety_agent,
    "vector_db_agent":  vector_db_agent,
}
