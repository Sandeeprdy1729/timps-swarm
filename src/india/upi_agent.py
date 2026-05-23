"""
UPI Agent — India UPI payment integration.
Generates deep links, QR codes, gateway integration (Razorpay/Cashfree/PhonePe),
webhook handlers, reconciliation scripts.

Input:  use_case (str), gateway (str), amount (float), merchant_vpa (str),
        webhook_url (str)
Output: upi_deeplink, qr_payload, integration_code, webhook_code, code_path
"""
from __future__ import annotations

from typing import Any, Dict

from src._helpers import _ts, _llm, _save, _parse_json, _record


def upi_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    use_case     = args.get("use_case", "payment collection")
    gateway      = args.get("gateway", "razorpay")
    amount       = float(args.get("amount", 0))
    merchant_vpa = args.get("merchant_vpa", "merchant@ybl")
    webhook_url  = args.get("webhook_url", "https://api.example.com/webhooks/upi")

    system = (
        "You are a UPI/Indian payments expert. Return JSON: "
        "{upi_deeplink:str, qr_payload:str, integration_code:str (Python), "
        "webhook_handler_code:str (FastAPI), reconciliation_code:str, "
        "gateway_config:object, error_codes:{upi_code:description}, "
        "pci_dss_checklist:[str], testing_upi_ids:[str]}. "
        "Output ONLY valid JSON."
    )
    prompt = (
        f"Use case: {use_case}\nGateway: {gateway}\n"
        f"Merchant VPA: {merchant_vpa}\nWebhook URL: {webhook_url}\n"
        f"Amount: {amount if amount else 'dynamic'}\n\n"
        "Generate complete UPI integration."
    )

    data = _parse_json(_llm(prompt, system, "upi_agent"), {
        "upi_deeplink": "", "integration_code": "", "webhook_handler_code": "",
    })

    ts = _ts()
    code_path    = _save("code", f"upi_{gateway}_{ts}.py",     data.get("integration_code", ""))
    webhook_path = _save("code", f"upi_webhook_{ts}.py",       data.get("webhook_handler_code", ""))
    recon_path   = _save("scripts", f"upi_reconciliation_{ts}.py", data.get("reconciliation_code", ""))

    _record("upi_agent", f"{gateway}/{use_case}", code_path)
    return {
        "upi_deeplink":        data.get("upi_deeplink", ""),
        "qr_payload":          data.get("qr_payload", ""),
        "gateway_config":      data.get("gateway_config", {}),
        "error_codes":         data.get("error_codes", {}),
        "pci_dss_checklist":   data.get("pci_dss_checklist", []),
        "testing_upi_ids":     data.get("testing_upi_ids", []),
        "code_path":           code_path,
        "webhook_path":        webhook_path,
        "reconciliation_path": recon_path,
        "summary": (
            f"UPI integration ({gateway}) for '{use_case}'. "
            f"Code → {code_path}."
        ),
    }
