"""
Vector DB Agent — designs optimal schema and generates integration code
for Qdrant, Pinecone, Weaviate, or pgvector.

Input:  data_description (str), query_patterns (list), provider (str),
        embedding_dim (int), expected_scale (str)
Output: collection_schema, hnsw_config, upsert_path, query_path
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from src._helpers import _ts, _llm, _save, _parse_json, _record


def vector_db_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    data_desc = args.get("data_description", "text documents")
    queries: List[str] = args.get("query_patterns", ["semantic search"])
    provider  = args.get("provider", "qdrant")
    emb_dim   = int(args.get("embedding_dim", 1536))
    scale     = args.get("expected_scale", "medium (<10M)")

    system = (
        "You are a vector database architect. Return JSON: "
        "{collection_schema:object, hnsw_config:{m:int,ef_construct:int,ef:int}, "
        "metadata_fields:[{name,type,indexed:bool,rationale}], "
        "upsert_code:str, query_code:str, batch_import_code:str, "
        "performance_tips:[str], estimated_storage_gb_per_1m_docs:float}. "
        "Output ONLY valid JSON."
    )
    prompt = (
        f"Provider: {provider}\nData: {data_desc}\n"
        f"Queries: {json.dumps(queries[:5])}\n"
        f"Embedding dims: {emb_dim}\nScale: {scale}\n\n"
        "Design the optimal vector DB schema and integration code."
    )

    data = _parse_json(_llm(prompt, system, "vector_db_agent"), {
        "upsert_code": "# stub", "query_code": "", "collection_schema": {},
    })

    ts = _ts()
    schema_path = _save("vector_db", f"{provider}_schema_{ts}.json",
                         json.dumps(data.get("collection_schema", {}), indent=2))
    upsert_path = _save("vector_db", f"{provider}_upsert_{ts}.py",  data.get("upsert_code", ""))
    query_path  = _save("vector_db", f"{provider}_query_{ts}.py",   data.get("query_code", ""))
    batch_path  = _save("vector_db", f"{provider}_batch_{ts}.py",   data.get("batch_import_code", ""))

    _record("vector_db_agent", f"{provider}:{data_desc}", schema_path)
    return {
        "collection_schema":   data.get("collection_schema", {}),
        "hnsw_config":         data.get("hnsw_config", {}),
        "metadata_fields":     data.get("metadata_fields", []),
        "performance_tips":    data.get("performance_tips", []),
        "estimated_storage_gb": data.get("estimated_storage_gb_per_1m_docs", 0),
        "schema_path":  schema_path,
        "upsert_path":  upsert_path,
        "query_path":   query_path,
        "batch_path":   batch_path,
        "summary": (
            f"{provider} schema designed. "
            f"{len(data.get('metadata_fields', []))} metadata fields. "
            f"Code → {upsert_path}."
        ),
    }
