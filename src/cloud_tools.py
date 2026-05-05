"""
Cloud & Infrastructure Tools — data-collection helpers for DevOps/cloud agents.

Used by:
  - CloudCostAuditor
  - CertificateRotator
  - TerraformPlanReviewer
  - IncidentResponder
  - SLOWatcher
"""
from __future__ import annotations

import json
import logging
import os
import re
import socket
import ssl
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _run(cmd: List[str], cwd: Optional[str] = None, timeout: int = 30) -> Tuple[str, str, int]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return r.stdout, r.stderr, r.returncode
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return "", str(exc), 1


# ─────────────────────────────────────────────────────────────────────────────
# TLS / Certificate checker
# ─────────────────────────────────────────────────────────────────────────────

class CertificateChecker:
    """Check TLS certificate expiry for a list of hosts."""

    def check_host(self, host: str, port: int = 443, timeout: int = 10) -> Dict[str, Any]:
        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((host, port), timeout=timeout) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()

            not_after_str = cert.get("notAfter", "")
            not_after = datetime.strptime(not_after_str, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            days_left = (not_after - now).days

            subject = dict(x[0] for x in cert.get("subject", []))
            issuer = dict(x[0] for x in cert.get("issuer", []))

            return {
                "host": host,
                "port": port,
                "days_until_expiry": days_left,
                "expiry_date": not_after_str,
                "common_name": subject.get("commonName", ""),
                "issuer": issuer.get("organizationName", ""),
                "status": "critical" if days_left < 7 else ("warning" if days_left < 30 else "ok"),
            }
        except ssl.SSLCertVerificationError as e:
            return {"host": host, "port": port, "error": f"SSL verification failed: {e}", "status": "error"}
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            return {"host": host, "port": port, "error": str(e), "status": "unreachable"}

    def check_hosts(self, hosts: List[str]) -> List[Dict[str, Any]]:
        return [self.check_host(h) for h in hosts]

    def find_hosts_from_repo(self, repo_path: str) -> List[str]:
        """Extract hostnames from common config files (nginx, k8s, terraform, .env)."""
        hosts = set()
        patterns = [
            re.compile(r"server_name\s+([\w.\-]+)", re.IGNORECASE),  # nginx
            re.compile(r"host:\s+([\w.\-]+)", re.IGNORECASE),         # k8s
            re.compile(r'"([\w\-]+\.[\w.\-]+)"'),                      # terraform string values
        ]
        skip = {".git", "node_modules", "__pycache__", ".venv"}
        root = Path(repo_path)
        for f in root.rglob("*"):
            if f.is_dir() or any(d in f.parts for d in skip):
                continue
            if f.suffix not in {".conf", ".yaml", ".yml", ".tf", ".env", ".ini", ".toml"}:
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for pattern in patterns:
                for match in pattern.findall(text):
                    if "." in match and not match.startswith("127.") and match != "localhost":
                        hosts.add(match)
        return list(hosts)[:20]


# ─────────────────────────────────────────────────────────────────────────────
# Terraform plan reviewer
# ─────────────────────────────────────────────────────────────────────────────

class TerraformReviewer:
    """Parse terraform plan output and flag destructive changes."""

    DESTRUCTIVE_KEYWORDS = [
        "will be destroyed", "must be replaced", "forces replacement",
        "destroy", "recreate", "-/+",
    ]
    HIGH_RISK_RESOURCES = [
        "aws_db_instance", "aws_rds_cluster", "aws_s3_bucket",
        "aws_iam_role", "aws_iam_policy", "google_sql_database_instance",
        "azurerm_sql_server", "kubernetes_persistent_volume",
    ]

    def parse_plan_text(self, plan_text: str) -> Dict[str, Any]:
        """Parse terraform plan output text."""
        lines = plan_text.splitlines()
        changes = {"add": 0, "change": 0, "destroy": 0}
        destructive_ops = []
        high_risk = []

        current_resource = None
        for line in lines:
            # Summary line
            m = re.search(r"(\d+) to add,\s*(\d+) to change,\s*(\d+) to destroy", line)
            if m:
                changes = {"add": int(m.group(1)), "change": int(m.group(2)), "destroy": int(m.group(3))}

            # Resource block
            rm = re.match(r"\s*#\s+([\w.]+)\s+", line)
            if rm:
                current_resource = rm.group(1)

            # Destructive operations
            for kw in self.DESTRUCTIVE_KEYWORDS:
                if kw in line and current_resource:
                    entry = {"resource": current_resource, "reason": line.strip()[:120]}
                    if entry not in destructive_ops:
                        destructive_ops.append(entry)

            # High-risk resources
            for hr in self.HIGH_RISK_RESOURCES:
                if hr in line and current_resource:
                    if current_resource not in [h["resource"] for h in high_risk]:
                        high_risk.append({"resource": current_resource, "type": hr})

        risk = "none"
        if changes["destroy"] > 0:
            risk = "critical" if high_risk else "high"
        elif changes["change"] > 5:
            risk = "medium"
        elif changes["add"] > 0:
            risk = "low"

        return {
            "changes": changes,
            "risk_level": risk,
            "destructive_operations": destructive_ops[:20],
            "high_risk_resources": high_risk,
            "approval_required": risk in ("high", "critical"),
        }

    def find_plan_file(self, repo_path: str) -> Optional[str]:
        """Look for a saved terraform plan file."""
        for name in ["tfplan", "plan.out", "terraform.plan", ".terraform/plan"]:
            p = Path(repo_path) / name
            if p.exists():
                return str(p)
        return None

    def run_plan_check(self, repo_path: str) -> Dict[str, Any]:
        """Run terraform plan in the given directory."""
        out, err, rc = _run(["terraform", "plan", "-no-color"], cwd=repo_path, timeout=120)
        if rc not in (0, 2):
            return {"error": f"terraform plan failed: {err[:500]}", "raw": out[:1000]}
        return self.parse_plan_text(out)


# ─────────────────────────────────────────────────────────────────────────────
# Cloud cost auditor (local / static analysis only — no cloud API calls)
# ─────────────────────────────────────────────────────────────────────────────

class CloudCostAuditor:
    """
    Audit Terraform configs and AWS CLI output for obvious waste.
    Operates without API keys — static analysis of IaC files.
    """

    EXPENSIVE_DEFAULTS = {
        "instance_type": {
            "wasteful": ["t2.xlarge", "t3.xlarge", "m5.xlarge", "m5.2xlarge", "m5.4xlarge",
                         "c5.2xlarge", "c5.4xlarge", "r5.xlarge", "r5.2xlarge"],
            "note": "Over-provisioned instance — check actual CPU/RAM utilization",
        },
        "allocated_storage": {
            "threshold": 500,
            "note": "Large RDS storage allocation — verify usage before paying for it",
        },
    }

    def scan_terraform_dir(self, tf_dir: str) -> Dict[str, Any]:
        root = Path(tf_dir)
        issues = []
        resource_count: Dict[str, int] = {}

        for tf_file in root.rglob("*.tf"):
            try:
                content = tf_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            # Count resource types
            for m in re.finditer(r'resource\s+"([\w_]+)"', content):
                rt = m.group(1)
                resource_count[rt] = resource_count.get(rt, 0) + 1

            # Flag expensive instance types
            for inst in self.EXPENSIVE_DEFAULTS["instance_type"]["wasteful"]:
                if f'"{inst}"' in content or f"'{inst}'" in content:
                    issues.append({
                        "file": str(tf_file.relative_to(root)),
                        "type": "expensive_instance",
                        "detail": f"Instance type {inst} detected — {self.EXPENSIVE_DEFAULTS['instance_type']['note']}",
                        "estimated_monthly": self._estimate_cost(inst),
                    })

            # Flag deletion protection disabled on databases
            if "aws_db_instance" in content or "aws_rds_cluster" in content:
                if "deletion_protection" not in content:
                    issues.append({
                        "file": str(tf_file.relative_to(root)),
                        "type": "missing_deletion_protection",
                        "detail": "RDS resource without deletion_protection = true",
                    })

            # Unencrypted storage
            if "aws_s3_bucket" in content and "server_side_encryption" not in content:
                issues.append({
                    "file": str(tf_file.relative_to(root)),
                    "type": "unencrypted_s3",
                    "detail": "S3 bucket without server-side encryption configured",
                })

            # Publicly accessible databases
            if "publicly_accessible" in content:
                m2 = re.search(r'publicly_accessible\s*=\s*(true)', content)
                if m2:
                    issues.append({
                        "file": str(tf_file.relative_to(root)),
                        "type": "public_database",
                        "detail": "Database is publicly_accessible = true — security risk",
                    })

        return {
            "tf_files_scanned": len(list(root.rglob("*.tf"))),
            "resource_types": resource_count,
            "issues": issues,
            "total_issues": len(issues),
        }

    def _estimate_cost(self, instance_type: str) -> str:
        # Rough estimates based on on-demand US East pricing
        estimates = {
            "t2.xlarge": "$134/mo", "t3.xlarge": "$120/mo",
            "m5.xlarge": "$144/mo", "m5.2xlarge": "$288/mo", "m5.4xlarge": "$576/mo",
            "c5.2xlarge": "$248/mo", "c5.4xlarge": "$496/mo",
            "r5.xlarge": "$181/mo", "r5.2xlarge": "$362/mo",
        }
        return estimates.get(instance_type, "unknown")

    def scan_aws_cli_output(self) -> Dict[str, Any]:
        """Check for idle/orphaned resources using AWS CLI (if configured)."""
        results: Dict[str, Any] = {"available": False, "issues": []}

        # Check if AWS CLI is configured
        out, _, rc = _run(["aws", "sts", "get-caller-identity"], timeout=10)
        if rc != 0:
            results["error"] = "AWS CLI not configured or no credentials"
            return results

        results["available"] = True

        # Check for unattached EBS volumes
        out, _, rc = _run(
            ["aws", "ec2", "describe-volumes",
             "--filters", "Name=status,Values=available",
             "--query", "Volumes[*].{ID:VolumeId,Size:Size,AZ:AvailabilityZone}",
             "--output", "json"],
            timeout=20,
        )
        if rc == 0:
            try:
                vols = json.loads(out)
                if vols:
                    results["issues"].append({
                        "type": "unattached_ebs",
                        "count": len(vols),
                        "volumes": vols[:10],
                        "note": f"{len(vols)} unattached EBS volumes — ~$0.10/GB/mo each",
                    })
            except Exception:
                pass

        # Check for unused elastic IPs
        out, _, rc = _run(
            ["aws", "ec2", "describe-addresses",
             "--query", "Addresses[?AssociationId==null]",
             "--output", "json"],
            timeout=20,
        )
        if rc == 0:
            try:
                ips = json.loads(out)
                if ips:
                    results["issues"].append({
                        "type": "unassociated_eip",
                        "count": len(ips),
                        "note": f"{len(ips)} unused Elastic IPs — $3.60/mo each",
                        "estimated_waste": f"${len(ips) * 3.60:.2f}/mo",
                    })
            except Exception:
                pass

        return results


# ─────────────────────────────────────────────────────────────────────────────
# Incident response helpers (log correlation across sources)
# ─────────────────────────────────────────────────────────────────────────────

class IncidentCorrelator:
    """Gather logs from multiple sources and correlate events around an incident."""

    def __init__(self, repo_path: Optional[str] = None):
        self.repo = repo_path or os.getcwd()

    def get_docker_logs(self, since: str = "1h") -> List[Dict[str, Any]]:
        """Get logs from all running Docker containers."""
        out, _, rc = _run(["docker", "ps", "--format", "{{.Names}}"], timeout=10)
        if rc != 0:
            return []
        containers = [c.strip() for c in out.splitlines() if c.strip()]
        logs = []
        for c in containers[:5]:
            out, _, _ = _run(["docker", "logs", "--since", since, "--tail", "200", c], timeout=15)
            logs.append({"container": c, "log": out[:3000]})
        return logs

    def get_app_logs(self, log_dir: Optional[str] = None) -> List[Dict[str, Any]]:
        """Scan common log directories for recent errors."""
        dirs = [
            log_dir,
            "logs", "log", "tmp/log",
            "/var/log/nginx",
            "/var/log/apache2",
        ]
        results = []
        for d in dirs:
            if not d:
                continue
            p = Path(d) if d.startswith("/") else Path(self.repo) / d
            if not p.exists():
                continue
            for lf in sorted(p.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)[:3]:
                try:
                    lines = lf.read_text(encoding="utf-8", errors="ignore").splitlines()[-200:]
                    errors = [l for l in lines if re.search(r"\b(error|exception|fatal|critical)\b", l, re.IGNORECASE)]
                    results.append({
                        "file": str(lf),
                        "recent_errors": errors[:20],
                        "error_count": len(errors),
                    })
                except OSError:
                    pass
        return results

    def correlate_timeline(self, window_minutes: int = 30) -> Dict[str, Any]:
        """Build a unified timeline of events across log sources."""
        docker = self.get_docker_logs(since=f"{window_minutes}m")
        app = self.get_app_logs()

        # Extract timestamped error lines
        ts_pattern = re.compile(
            r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})"
        )
        events = []
        for src in docker:
            for line in src["log"].splitlines():
                m = ts_pattern.search(line)
                if m and re.search(r"error|exception|fatal", line, re.IGNORECASE):
                    events.append({"time": m.group(1), "source": src["container"], "line": line[:200]})
        for src in app:
            for line in src["recent_errors"]:
                m = ts_pattern.search(line)
                if m:
                    events.append({"time": m.group(1), "source": src["file"], "line": line[:200]})

        events.sort(key=lambda x: x["time"])
        return {
            "docker_containers_checked": len(docker),
            "app_log_files_checked": len(app),
            "error_events": events[:50],
            "timeline_window_minutes": window_minutes,
        }
