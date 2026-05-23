"""
GST Compliance Agent — India GST/e-invoice automation.
Generates GSTR-1, GSTR-3B, e-invoice XML, ITC reconciliation, HSN/SAC mapping.

Input:  business_description (str), invoices (list), period (str), gstin (str)
Output: gstr1, gstr3b, einvoice_xml, itc_reconciliation, report_path
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from src._helpers import _ts, _llm, _save, _parse_json, _record


def gst_compliance(args: Dict[str, Any]) -> Dict[str, Any]:
    biz_desc   = args.get("business_description", "Indian business")
    invoices: List[Dict] = args.get("invoices", [])
    period     = args.get("period", "2024-03")
    gstin      = args.get("gstin", "")

    invoice_sample = json.dumps(invoices[:20], indent=2)[:3000]

    system = (
        "You are an Indian GST expert. Generate compliant filings and code. Return JSON: "
        "{gstr1:{summary,b2b:[{gstin,invoice_no,invoice_date,taxable_value,cgst,sgst,igst}],"
        "hsn_summary:[{hsn,uqc,quantity,taxable_value,cgst_rate,sgst_rate,igst_rate}]}, "
        "gstr3b:{section31_supplies,section32_itc,net_tax_liability}, "
        "einvoice_xml:str, "
        "itc_reconciliation:{eligible_itc,ineligible_itc,blocked_credit:[str]}, "
        "gst_code_snippet:str, "
        "compliance_checklist:[str], "
        "penalties_risk:[str]}. Output ONLY valid JSON."
    )
    prompt = (
        f"Business: {biz_desc}\nGSTIN: {gstin or 'not provided'}\nPeriod: {period}\n\n"
        f"Invoices (sample):\n{invoice_sample}\n\n"
        "Generate GSTR-1, GSTR-3B, e-invoice, ITC reconciliation."
    )

    data = _parse_json(_llm(prompt, system, "gst_compliance"), {
        "gstr1": {}, "gstr3b": {}, "compliance_checklist": [],
    })

    ts = _ts()
    gstr1_path = _save("reports", f"GSTR1_{period}_{ts}.json",
                        json.dumps(data.get("gstr1", {}), indent=2))
    gstr3b_path = _save("reports", f"GSTR3B_{period}_{ts}.json",
                         json.dumps(data.get("gstr3b", {}), indent=2))
    einvoice_path = _save("reports", f"einvoice_{ts}.xml", data.get("einvoice_xml", ""))
    code_path = _save("code", f"gst_integration_{ts}.py", data.get("gst_code_snippet", ""))

    _record("gst_compliance", f"{gstin}/{period}", gstr1_path)
    return {
        "gstr1":               data.get("gstr1", {}),
        "gstr3b":              data.get("gstr3b", {}),
        "itc_reconciliation":  data.get("itc_reconciliation", {}),
        "compliance_checklist": data.get("compliance_checklist", []),
        "penalties_risk":      data.get("penalties_risk", []),
        "gstr1_path":          gstr1_path,
        "gstr3b_path":         gstr3b_path,
        "einvoice_path":       einvoice_path,
        "code_path":           code_path,
        "summary": (
            f"GST filings for {period}. "
            f"GSTR-1 → {gstr1_path}, GSTR-3B → {gstr3b_path}."
        ),
    }
