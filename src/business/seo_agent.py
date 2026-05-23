"""
SEO Agent — technical SEO audit, schema.org markup, Lighthouse CI,
Core Web Vitals fixes, and programmatic SEO content strategy.

Input:  url (str), target_keywords (list), framework (str), page_type (str)
Output: audit_findings, schema_markup, meta_tags, fixes, report_path
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from src._helpers import _ts, _llm, _save, _parse_json, _record, _run


def seo_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    url       = args.get("url", "https://example.com")
    keywords: List[str] = args.get("target_keywords", [])
    framework = args.get("framework", "nextjs")
    page_type = args.get("page_type", "product")

    lighthouse_out = _run(
        f"npx lighthouse {url} --output=json --quiet 2>/dev/null | "
        f"python3 -c \"import json,sys; d=json.load(sys.stdin); "
        f"cats=d.get('categories',{{}}); "
        f"print(json.dumps({{k:v.get('score') for k,v in cats.items()}}))\" "
        "2>/dev/null || echo '{}'",
    )[:1000]

    system = (
        "You are an SEO expert. Return JSON: "
        "{audit_findings:[{issue,severity:'critical'|'warning'|'info',fix,impact}], "
        "schema_markup:str (JSON-LD), meta_tags_code:str, "
        "sitemap_code:str, robots_txt:str, "
        "core_web_vitals_fixes:[{metric,current,target,fix_code}], "
        "programmatic_seo_strategy:str, "
        "internal_linking_plan:[str], keyword_clusters:[{seed,variants:[str]}]}. "
        "Output ONLY valid JSON."
    )
    prompt = (
        f"URL: {url}\nFramework: {framework}\nPage type: {page_type}\n"
        f"Target keywords: {json.dumps(keywords[:20])}\n"
        f"Lighthouse scores: {lighthouse_out}\n\n"
        "Perform technical SEO audit."
    )

    data = _parse_json(_llm(prompt, system, "seo_agent"), {
        "audit_findings": [], "schema_markup": "", "meta_tags_code": "",
    })

    ts = _ts()
    report_path = _save("reports", f"seo_audit_{ts}.md",
                         "# SEO Audit\n\n"
                         + "\n".join(
                             f"**[{f.get('severity','?').upper()}]** {f.get('issue','?')} — {f.get('fix','')}"
                             for f in data.get("audit_findings", [])
                         ))
    schema_path = _save("code",    f"schema_markup_{ts}.json", data.get("schema_markup", ""))
    meta_path   = _save("code",    f"meta_tags_{framework}_{ts}.tsx", data.get("meta_tags_code", ""))
    sitemap_path = _save("code",   f"sitemap_{ts}.xml",              data.get("sitemap_code", ""))

    _record("seo_agent", url, report_path)
    return {
        "audit_findings":        data.get("audit_findings", []),
        "core_web_vitals_fixes": data.get("core_web_vitals_fixes", []),
        "keyword_clusters":      data.get("keyword_clusters", []),
        "report_path":           report_path,
        "schema_path":           schema_path,
        "meta_path":             meta_path,
        "sitemap_path":          sitemap_path,
        "summary": (
            f"SEO audit for {url}: "
            f"{len(data.get('audit_findings', []))} findings. → {report_path}."
        ),
    }
