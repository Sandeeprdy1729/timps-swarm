"""
RAG Designer — designs optimal Retrieval-Augmented Generation pipelines:
chunking strategy, embedding model, retrieval method, re-ranking, context sizing.

Input:  doc_description (str), query_examples (list), context_window (int),
        latency_slo_ms (int), framework (str)
Output: chunking, embedding, retrieval, config_path, pipeline_path
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from src._helpers import _ts, _llm, _save, _parse_json, _record


def rag_designer(args: Dict[str, Any]) -> Dict[str, Any]:
    doc_desc    = args.get("doc_description", "enterprise documents")
    queries: List[str] = args.get("query_examples", ["What is the policy on X?"])
    ctx_window  = int(args.get("context_window", 8192))
    latency_slo = int(args.get("latency_slo_ms", 500))
    framework   = args.get("framework", "llamaindex")

    system = (
        "You are a RAG architecture expert. Return JSON: "
        "{chunking:{strategy,chunk_size:int,overlap:int,rationale}, "
        "embedding:{model,dimensions:int,provider,rationale}, "
        "retrieval:{method,top_k:int,reranker,hybrid_alpha:float}, "
        "rag_config_yaml:str, pipeline_code:str, index_setup_code:str, "
        "query_pipeline_code:str, "
        "performance_estimates:{index_time_per_doc_ms:int,query_latency_ms:int,"
        "storage_per_1k_docs_mb:float}, tradeoffs:[str]}. Output ONLY valid JSON."
    )
    prompt = (
        f"Corpus: {doc_desc}\nQueries: {json.dumps(queries[:5])}\n"
        f"Context window: {ctx_window} tokens\nLatency SLO: {latency_slo}ms\n"
        f"Framework: {framework}\n\nDesign the optimal RAG pipeline."
    )

    data = _parse_json(_llm(prompt, system, "rag_designer"), {
        "rag_config_yaml": "# rag config", "pipeline_code": "", "chunking": {}, "embedding": {},
    })

    config_path   = _save("rag", f"rag_config_{_ts()}.yaml",      data.get("rag_config_yaml", ""))
    pipeline_path = _save("rag", f"rag_pipeline_{_ts()}.py",      data.get("pipeline_code", ""))
    index_path    = _save("rag", f"index_setup_{_ts()}.py",       data.get("index_setup_code", ""))
    query_path    = _save("rag", f"query_pipeline_{_ts()}.py",    data.get("query_pipeline_code", ""))

    _record("rag_designer", doc_desc, config_path)
    return {
        "chunking":   data.get("chunking", {}),
        "embedding":  data.get("embedding", {}),
        "retrieval":  data.get("retrieval", {}),
        "performance_estimates": data.get("performance_estimates", {}),
        "tradeoffs":  data.get("tradeoffs", []),
        "config_path":    config_path,
        "pipeline_path":  pipeline_path,
        "index_path":     index_path,
        "query_path":     query_path,
        "summary": (
            f"RAG: {data.get('chunking',{}).get('strategy','?')} chunking, "
            f"{data.get('embedding',{}).get('model','?')} embeddings, "
            f"{data.get('retrieval',{}).get('method','?')} retrieval. → {config_path}."
        ),
    }
