"""
ABDM Agent — Ayushman Bharat Digital Mission integration.
Generates ABHA enrollment, HIP/HIU flows, FHIR R4 bundles, consent workflows.

Input:  use_case (str), fhir_resources (list), consent_purpose (str), hip_id (str)
Output: abha_flow, fhir_bundle, consent_workflow, integration_code, code_path
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from src._helpers import _ts, _llm, _save, _parse_json, _record


def abdm_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    use_case   = args.get("use_case", "patient health record sharing")
    fhir_res: List[str] = args.get("fhir_resources", ["Patient", "Observation", "Condition"])
    consent_purpose = args.get("consent_purpose", "care-management")
    hip_id     = args.get("hip_id", "")

    system = (
        "You are an ABDM/FHIR R4 integration expert. Return JSON: "
        "{abha_enrollment_flow:[{step,api_endpoint,method,request_body:object,response:object}], "
        "hip_hiu_flow:[{step,description,api,auth_header}], "
        "fhir_bundle:object, "
        "consent_workflow:[{step,api,payload:object}], "
        "integration_code:str, "
        "m2_deeplink_example:str, "
        "required_certs:[str], "
        "sandbox_urls:object}. Output ONLY valid JSON."
    )
    prompt = (
        f"Use case: {use_case}\nHIP ID: {hip_id or 'demo'}\n"
        f"FHIR resources: {json.dumps(fhir_res)}\n"
        f"Consent purpose: {consent_purpose}\n\n"
        "Generate complete ABDM integration."
    )

    data = _parse_json(_llm(prompt, system, "abdm_agent"), {
        "abha_enrollment_flow": [], "fhir_bundle": {}, "integration_code": "",
    })

    ts = _ts()
    fhir_path = _save("code", f"abdm_fhir_bundle_{ts}.json",
                       json.dumps(data.get("fhir_bundle", {}), indent=2))
    code_path = _save("code", f"abdm_integration_{ts}.py", data.get("integration_code", ""))

    _record("abdm_agent", use_case, code_path)
    return {
        "abha_enrollment_flow": data.get("abha_enrollment_flow", []),
        "hip_hiu_flow":         data.get("hip_hiu_flow", []),
        "fhir_bundle":          data.get("fhir_bundle", {}),
        "consent_workflow":     data.get("consent_workflow", []),
        "m2_deeplink_example":  data.get("m2_deeplink_example", ""),
        "required_certs":       data.get("required_certs", []),
        "sandbox_urls":         data.get("sandbox_urls", {}),
        "fhir_path":            fhir_path,
        "code_path":            code_path,
        "summary": (
            f"ABDM integration for '{use_case}'. "
            f"FHIR bundle → {fhir_path}. Code → {code_path}."
        ),
    }
