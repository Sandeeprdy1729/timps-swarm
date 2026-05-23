"""
Data Pipeline Agent — designs and generates ETL/ELT pipelines using
dbt, Apache Airflow, Prefect, or Dagster.

Input:  source_description (str), destination (str), schedule (str),
        framework (str), transformations (list)
Output: dag_code, dbt_models, data_contracts, code_path
"""
from __future__ import annotations

from typing import Any, Dict, List

from src._helpers import _ts, _llm, _save, _parse_json, _record


def data_pipeline(args: Dict[str, Any]) -> Dict[str, Any]:
    source   = args.get("source_description", "Postgres database")
    dest     = args.get("destination", "Snowflake data warehouse")
    schedule = args.get("schedule", "0 2 * * *")
    framework = args.get("framework", "airflow")
    transforms: List[str] = args.get("transformations", ["deduplicate", "normalize", "aggregate"])

    system = (
        "You are a data engineering expert. Return JSON: "
        "{dag_code:str, dbt_models:[{model_name,sql,schema_yml}], "
        "data_contracts:[{table,columns:[{name,type,nullable,description}]}], "
        "monitoring_code:str, alerting_config:object, "
        "incremental_strategy:str, partitioning_recommendations:str}. "
        "Output ONLY valid JSON."
    )
    prompt = (
        f"Source: {source}\nDestination: {dest}\nSchedule: {schedule}\n"
        f"Framework: {framework}\nTransformations: {', '.join(transforms)}\n\n"
        "Generate production-grade data pipeline."
    )

    data = _parse_json(_llm(prompt, system, "data_pipeline"), {
        "dag_code": "# dag stub", "dbt_models": [], "data_contracts": [],
    })

    ts = _ts()
    dag_path      = _save("code", f"pipeline_dag_{framework}_{ts}.py",  data.get("dag_code", ""))
    monitor_path  = _save("monitoring", f"pipeline_monitoring_{ts}.py", data.get("monitoring_code", ""))
    for i, model in enumerate(data.get("dbt_models", [])[:5]):
        _save("code", f"dbt_{model.get('model_name','model'+str(i))}_{ts}.sql", model.get("sql", ""))

    _record("data_pipeline", f"{framework}:{source}->{dest}", dag_path)
    return {
        "dbt_models":               data.get("dbt_models", []),
        "data_contracts":           data.get("data_contracts", []),
        "incremental_strategy":     data.get("incremental_strategy", ""),
        "partitioning_recommendations": data.get("partitioning_recommendations", ""),
        "dag_path":     dag_path,
        "monitor_path": monitor_path,
        "summary": f"Pipeline ({framework}): {source} → {dest}. DAG → {dag_path}.",
    }
