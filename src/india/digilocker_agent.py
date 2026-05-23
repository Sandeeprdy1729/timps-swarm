"""
DigiLocker Agent — India DigiLocker / eKYC / Aadhaar verification integration.
Generates OAuth flows, document pull APIs, Aadhaar OTP/biometric auth,
PAN verification, and eKYC handlers.

Input:  use_case (str), documents (list), redirect_uri (str), client_id (str)
Output: oauth_flow, document_pull_code, aadhaar_otp_code, ekyc_code, code_path
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from src._helpers import _ts, _llm, _save, _parse_json, _record


def digilocker_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    use_case     = args.get("use_case", "KYC verification")
    documents: List[str] = args.get("documents", ["AADHAAR", "PAN", "DRIVING_LICENSE"])
    redirect_uri = args.get("redirect_uri", "https://app.example.com/digilocker/callback")
    client_id    = args.get("client_id", "YOUR_CLIENT_ID")

    system = (
        "You are a DigiLocker/UIDAI integration expert. Return JSON: "
        "{oauth_flow:[{step,endpoint,method,params:object,response_fields:[str]}], "
        "document_pull_code:str, aadhaar_otp_verification_code:str, "
        "pan_verification_code:str, ekyc_response_parser:str, "
        "security_checklist:[str], sandbox_endpoints:object, "
        "xml_parser_code:str, error_handling_code:str}. "
        "Output ONLY valid JSON."
    )
    prompt = (
        f"Use case: {use_case}\nDocuments: {json.dumps(documents)}\n"
        f"Redirect URI: {redirect_uri}\nClient ID: {client_id}\n\n"
        "Generate complete DigiLocker integration."
    )

    data = _parse_json(_llm(prompt, system, "digilocker_agent"), {
        "oauth_flow": [], "document_pull_code": "", "aadhaar_otp_verification_code": "",
    })

    ts = _ts()
    code_path   = _save("code", f"digilocker_{ts}.py",        data.get("document_pull_code", ""))
    aadhaar_path = _save("code", f"aadhaar_otp_{ts}.py",      data.get("aadhaar_otp_verification_code", ""))
    ekyc_path   = _save("code", f"ekyc_parser_{ts}.py",       data.get("ekyc_response_parser", ""))

    _record("digilocker_agent", use_case, code_path)
    return {
        "oauth_flow":           data.get("oauth_flow", []),
        "security_checklist":   data.get("security_checklist", []),
        "sandbox_endpoints":    data.get("sandbox_endpoints", {}),
        "code_path":            code_path,
        "aadhaar_path":         aadhaar_path,
        "ekyc_path":            ekyc_path,
        "summary": (
            f"DigiLocker integration for '{use_case}'. "
            f"Docs: {', '.join(documents)}. Code → {code_path}."
        ),
    }
