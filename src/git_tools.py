"""
Git Tools — data-collection helpers for git-aware expert agents.

Used by:
  - MergeConflictPredictor
  - TechDebtQuantifier
  - FlakeyTestDetective
  - OnboardingMentor
  - MigrationPilot
  - DependencyRebel
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _run(cmd: List[str], cwd: Optional[str] = None, timeout: int = 30) -> Tuple[str, str, int]:
    """Run a subprocess, return (stdout, stderr, returncode)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return r.stdout, r.stderr, r.returncode
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return "", str(exc), 1


def find_repo_root(cwd: Optional[str] = None) -> Optional[str]:
    """Walk up to find the nearest .git directory."""
    start = Path(cwd or os.getcwd())
    for p in [start, *start.parents]:
        if (p / ".git").exists():
            return str(p)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Branch & merge analysis
# ─────────────────────────────────────────────────────────────────────────────

class MergeAnalyzer:
    """Predict merge conflicts between two branches without actually merging."""

    def __init__(self, repo_path: Optional[str] = None):
        self.repo = repo_path or find_repo_root() or os.getcwd()

    def list_branches(self) -> List[str]:
        out, _, rc = _run(["git", "branch", "--all", "--format=%(refname:short)"], cwd=self.repo)
        if rc != 0:
            return []
        return [b.strip() for b in out.splitlines() if b.strip()]

    def current_branch(self) -> str:
        out, _, _ = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=self.repo)
        return out.strip() or "unknown"

    def changed_files_in_branch(self, branch: str, base: str = "main") -> List[Dict[str, str]]:
        """Files changed in `branch` relative to `base`."""
        out, _, rc = _run(
            ["git", "diff", "--name-status", f"{base}...{branch}"],
            cwd=self.repo,
        )
        if rc != 0:
            return []
        files = []
        for line in out.splitlines():
            parts = line.split("\t", 1)
            if len(parts) == 2:
                files.append({"status": parts[0], "file": parts[1]})
        return files

    def predict_conflicts(self, branch_a: str, branch_b: str, base: str = "main") -> Dict[str, Any]:
        """
        Predict conflicts by finding files changed in both branches.
        Returns dict with conflict_risk (low/medium/high), conflicting_files, stats.
        """
        files_a = {f["file"] for f in self.changed_files_in_branch(branch_a, base)}
        files_b = {f["file"] for f in self.changed_files_in_branch(branch_b, base)}
        overlap = files_a & files_b

        # Check line-level overlap for overlapping files (heuristic)
        detailed = []
        for f in list(overlap)[:20]:
            lines_a = self._changed_lines(branch_a, base, f)
            lines_b = self._changed_lines(branch_b, base, f)
            line_overlap = lines_a & lines_b
            detailed.append({
                "file": f,
                "line_conflicts": len(line_overlap),
                "sample_lines": sorted(line_overlap)[:10],
            })

        total_overlap = len(overlap)
        risk = "low" if total_overlap == 0 else ("medium" if total_overlap <= 3 else "high")
        return {
            "branch_a": branch_a,
            "branch_b": branch_b,
            "base": base,
            "files_changed_a": len(files_a),
            "files_changed_b": len(files_b),
            "overlapping_files": total_overlap,
            "conflict_risk": risk,
            "conflicting_files": detailed,
        }

    def _changed_lines(self, branch: str, base: str, filepath: str) -> set:
        """Return set of line numbers changed in branch for a specific file."""
        out, _, rc = _run(
            ["git", "diff", f"{base}...{branch}", "--", filepath],
            cwd=self.repo,
        )
        if rc != 0:
            return set()
        lines = set()
        line_num = 0
        for line in out.splitlines():
            m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
            if m:
                line_num = int(m.group(1))
                continue
            if line.startswith("+") and not line.startswith("+++"):
                lines.add(line_num)
                line_num += 1
        return lines

    def get_recent_commits(self, branch: str = "HEAD", n: int = 10) -> List[Dict[str, str]]:
        fmt = "--pretty=format:%H|%an|%ae|%ad|%s"
        out, _, rc = _run(
            ["git", "log", branch, f"-{n}", fmt, "--date=short"],
            cwd=self.repo,
        )
        if rc != 0:
            return []
        commits = []
        for line in out.splitlines():
            parts = line.split("|", 4)
            if len(parts) == 5:
                commits.append({
                    "hash": parts[0][:10],
                    "author": parts[1],
                    "email": parts[2],
                    "date": parts[3],
                    "message": parts[4],
                })
        return commits

    def get_hottest_files(self, n: int = 20) -> List[Dict[str, Any]]:
        """Files touched most often (heuristic for key modules)."""
        out, _, rc = _run(
            ["git", "log", "--name-only", "--pretty=format:", "--", "."],
            cwd=self.repo,
        )
        if rc != 0:
            return []
        counts: Dict[str, int] = {}
        for f in out.splitlines():
            f = f.strip()
            if f:
                counts[f] = counts.get(f, 0) + 1
        return [
            {"file": k, "commit_count": v}
            for k, v in sorted(counts.items(), key=lambda x: -x[1])[:n]
        ]


# ─────────────────────────────────────────────────────────────────────────────
# Tech debt scanning
# ─────────────────────────────────────────────────────────────────────────────

class TechDebtScanner:
    """Static analysis for tech debt indicators."""

    # Patterns that indicate debt
    DEBT_PATTERNS = {
        "todo_fixme": re.compile(r"\b(TODO|FIXME|HACK|XXX|TEMP|KLUDGE)\b", re.IGNORECASE),
        "deprecated_js_var": re.compile(r"^\s*var\s+", re.MULTILINE),
        "class_component": re.compile(r"class\s+\w+\s+extends\s+(?:React\.)?Component"),
        "print_debug": re.compile(r"\bprint\s*\(|console\.log\s*\(|debugger\b"),
        "magic_number": re.compile(r"(?<!\w)(?<!\.)\b(?!0\b|1\b|2\b)([3-9]\d{1,4})\b(?!\w)"),
        "long_line": None,  # handled separately
        "empty_except": re.compile(r"except\s*(?:\(\s*\))?\s*:\s*\n\s*pass"),
        "bare_except": re.compile(r"except\s*:\s*\n"),
        "mutable_default": re.compile(r"def\s+\w+\s*\(.*=\s*[\[\{]"),
    }

    def __init__(self, repo_path: Optional[str] = None):
        self.repo = repo_path or find_repo_root() or os.getcwd()

    def scan_directory(self, path: Optional[str] = None, exts: Optional[List[str]] = None) -> Dict[str, Any]:
        root = Path(path or self.repo)
        exts = exts or [".py", ".js", ".ts", ".jsx", ".tsx"]
        results: Dict[str, Any] = {
            "files_scanned": 0,
            "todo_fixme_count": 0,
            "debt_by_file": [],
            "total_lines": 0,
            "long_files": [],  # files > 500 lines
        }
        skip_dirs = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build", ".next"}

        for filepath in root.rglob("*"):
            if filepath.suffix not in exts:
                continue
            if any(d in filepath.parts for d in skip_dirs):
                continue
            try:
                content = filepath.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            lines = content.splitlines()
            results["files_scanned"] += 1
            results["total_lines"] += len(lines)

            file_debt: Dict[str, Any] = {"file": str(filepath.relative_to(root)), "issues": []}

            if len(lines) > 500:
                results["long_files"].append({"file": str(filepath.relative_to(root)), "lines": len(lines)})

            for name, pattern in self.DEBT_PATTERNS.items():
                if pattern is None:
                    continue
                matches = pattern.findall(content)
                if matches:
                    file_debt["issues"].append({"type": name, "count": len(matches)})
                    if name == "todo_fixme":
                        results["todo_fixme_count"] += len(matches)

            if file_debt["issues"]:
                results["debt_by_file"].append(file_debt)

        # Sort by issue count
        results["debt_by_file"].sort(
            key=lambda x: sum(i["count"] for i in x["issues"]), reverse=True
        )
        results["debt_by_file"] = results["debt_by_file"][:30]
        return results

    def cyclomatic_complexity(self, filepath: str) -> Dict[str, Any]:
        """Estimate cyclomatic complexity by counting decision points."""
        try:
            content = Path(filepath).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return {"error": "Could not read file"}

        # Count branch keywords
        keywords = re.findall(
            r"\b(if|elif|else|for|while|except|case|and|or|&&|\|\|)\b", content
        )
        complexity = len(keywords) + 1
        return {
            "file": filepath,
            "estimated_complexity": complexity,
            "risk": "low" if complexity < 10 else ("medium" if complexity < 30 else "high"),
            "branch_points": len(keywords),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Dependency analysis
# ─────────────────────────────────────────────────────────────────────────────

class DependencyAnalyzer:
    """Cross-language dependency conflict and vulnerability detection."""

    def __init__(self, repo_path: Optional[str] = None):
        self.repo = repo_path or find_repo_root() or os.getcwd()

    def detect_language(self) -> List[str]:
        root = Path(self.repo)
        langs = []
        if (root / "requirements.txt").exists() or (root / "pyproject.toml").exists() or (root / "Pipfile").exists():
            langs.append("python")
        if (root / "package.json").exists():
            langs.append("node")
        if (root / "Cargo.toml").exists():
            langs.append("rust")
        if (root / "pom.xml").exists() or (root / "build.gradle").exists():
            langs.append("java")
        if (root / "go.mod").exists():
            langs.append("go")
        return langs

    def scan_python(self) -> Dict[str, Any]:
        root = Path(self.repo)
        result: Dict[str, Any] = {"language": "python", "files": [], "conflicts": [], "issues": []}

        # Read requirements
        for req_file in ["requirements.txt", "requirements-dev.txt", "requirements-test.txt"]:
            path = root / req_file
            if path.exists():
                result["files"].append(req_file)

        # Check pip list for outdated
        out, _, rc = _run(["pip", "list", "--outdated", "--format=json"], cwd=self.repo, timeout=20)
        if rc == 0:
            try:
                outdated = json.loads(out)
                result["outdated_packages"] = outdated[:20]
            except json.JSONDecodeError:
                result["outdated_packages"] = []

        # Check for conflicting requirements (pip check)
        out, _, rc = _run(["pip", "check"], cwd=self.repo, timeout=20)
        if rc != 0:
            result["conflicts"] = [line.strip() for line in out.splitlines() if line.strip()]

        # Check lockfile vs installed
        lock = root / "Pipfile.lock"
        if lock.exists():
            try:
                data = json.loads(lock.read_text())
                result["lockfile_packages"] = len(data.get("default", {}))
            except Exception:
                pass

        return result

    def scan_node(self) -> Dict[str, Any]:
        root = Path(self.repo)
        result: Dict[str, Any] = {"language": "node", "issues": [], "outdated": [], "audit": []}

        pkg = root / "package.json"
        if not pkg.exists():
            return result

        try:
            data = json.loads(pkg.read_text())
            result["name"] = data.get("name", "unknown")
            result["deps_count"] = len(data.get("dependencies", {})) + len(data.get("devDependencies", {}))
        except Exception:
            pass

        # npm audit (fast, read-only)
        out, _, rc = _run(["npm", "audit", "--json"], cwd=self.repo, timeout=30)
        if rc in (0, 1):
            try:
                audit = json.loads(out)
                vuln = audit.get("metadata", {}).get("vulnerabilities", {})
                result["audit"] = vuln
                result["total_vulns"] = sum(vuln.values()) if isinstance(vuln, dict) else 0
            except json.JSONDecodeError:
                pass

        # Check for peer dependency issues
        out, _, _ = _run(["npm", "ls", "--json", "--depth=0"], cwd=self.repo, timeout=20)
        try:
            ls = json.loads(out)
            problems = ls.get("problems", [])
            result["peer_issues"] = problems[:20]
        except Exception:
            pass

        return result

    def generate_fix_plan(self, scan: Dict[str, Any]) -> str:
        """Generate human-readable fix plan from a dependency scan."""
        lines = []
        lang = scan.get("language", "unknown")

        if lang == "python":
            if scan.get("conflicts"):
                lines.append("## Python Dependency Conflicts")
                for c in scan["conflicts"]:
                    lines.append(f"  - {c}")
                lines.append("\nFix: `pip install --upgrade <conflicting-package>`")
            if scan.get("outdated_packages"):
                lines.append(f"\n## Outdated Packages ({len(scan['outdated_packages'])} found)")
                for p in scan["outdated_packages"][:10]:
                    lines.append(f"  - {p['name']} {p['version']} → {p['latest_version']}")

        elif lang == "node":
            if scan.get("total_vulns", 0) > 0:
                lines.append("## npm Security Vulnerabilities")
                vuln = scan.get("audit", {})
                for sev, count in vuln.items():
                    if count:
                        lines.append(f"  - {sev}: {count}")
                lines.append("\nFix: `npm audit fix`")
            if scan.get("peer_issues"):
                lines.append(f"\n## Peer Dependency Issues ({len(scan['peer_issues'])})")
                for p in scan["peer_issues"][:5]:
                    lines.append(f"  - {p}")

        return "\n".join(lines) or "No critical dependency issues found."


# ─────────────────────────────────────────────────────────────────────────────
# Test flakiness analysis
# ─────────────────────────────────────────────────────────────────────────────

class FlakeyTestAnalyzer:
    """Identify flaky tests from pytest cache or CI log patterns."""

    def __init__(self, repo_path: Optional[str] = None):
        self.repo = repo_path or find_repo_root() or os.getcwd()

    def read_pytest_cache(self) -> Dict[str, Any]:
        """Read .pytest_cache/v/cache/lastfailed and nodeids."""
        cache_dir = Path(self.repo) / ".pytest_cache" / "v" / "cache"
        result: Dict[str, Any] = {"last_failed": [], "nodeids": []}
        lf = cache_dir / "lastfailed"
        if lf.exists():
            try:
                data = json.loads(lf.read_text())
                result["last_failed"] = list(data.keys())
            except Exception:
                pass
        ni = cache_dir / "nodeids"
        if ni.exists():
            try:
                result["nodeids"] = json.loads(ni.read_text())
            except Exception:
                pass
        return result

    def find_test_files(self) -> List[str]:
        root = Path(self.repo)
        tests = []
        skip = {"node_modules", ".git", "__pycache__", ".venv", "venv"}
        for f in root.rglob("test_*.py"):
            if not any(d in f.parts for d in skip):
                tests.append(str(f.relative_to(root)))
        for f in root.rglob("*_test.py"):
            if not any(d in f.parts for d in skip):
                tests.append(str(f.relative_to(root)))
        return tests[:50]

    def detect_flakiness_patterns(self, test_file: str) -> List[Dict[str, str]]:
        """Look for common flakiness patterns in test source."""
        try:
            content = Path(self.repo, test_file).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []

        patterns = [
            (re.compile(r"\btime\.sleep\b|\basyncio\.sleep\b"), "timing_dependency",
             "Test uses sleep — may be timing-sensitive"),
            (re.compile(r"\brandom\b|\bfaker\b|\buuid\b", re.IGNORECASE), "random_data",
             "Test uses random data — results non-deterministic"),
            (re.compile(r"requests\.|httpx\.|urllib\.", re.IGNORECASE), "external_http",
             "Test makes real HTTP calls — depends on network"),
            (re.compile(r"open\(|Path\(|os\.path"), "filesystem",
             "Test reads/writes real filesystem — path-sensitive"),
            (re.compile(r"os\.environ|getenv"), "env_dependency",
             "Test depends on environment variables"),
            (re.compile(r"threading\.|concurrent\.|asyncio\.", re.IGNORECASE), "concurrency",
             "Test uses concurrency — potential race condition"),
        ]

        findings = []
        for pattern, kind, desc in patterns:
            if pattern.search(content):
                findings.append({"file": test_file, "type": kind, "description": desc})
        return findings

    def run_quick_scan(self) -> Dict[str, Any]:
        """Scan all test files for flakiness patterns + cache info."""
        test_files = self.find_test_files()
        cache = self.read_pytest_cache()
        all_findings = []
        for tf in test_files:
            findings = self.detect_flakiness_patterns(tf)
            all_findings.extend(findings)

        by_file: Dict[str, List] = {}
        for f in all_findings:
            by_file.setdefault(f["file"], []).append(f)

        return {
            "test_files_found": len(test_files),
            "files_with_patterns": len(by_file),
            "last_failed_tests": cache["last_failed"],
            "flakiness_findings": [
                {"file": k, "patterns": v} for k, v in sorted(
                    by_file.items(), key=lambda x: -len(x[1])
                )
            ][:20],
        }


# ─────────────────────────────────────────────────────────────────────────────
# Dotfile / shell config doctor
# ─────────────────────────────────────────────────────────────────────────────

class DotfileDoctor:
    """Detect errors and performance issues in shell config files."""

    SHELL_CONFIGS = [
        "~/.zshrc", "~/.bashrc", "~/.bash_profile",
        "~/.profile", "~/.zprofile", "~/.zshenv",
    ]
    TOOL_CONFIGS = [
        "~/.gitconfig", "~/.gitignore_global",
        "~/.npmrc", "~/.pip/pip.conf",
        "~/.ssh/config",
    ]
    EDITOR_CONFIGS = [
        "~/.vimrc", "~/.config/nvim/init.vim",
        "~/.config/nvim/init.lua",
    ]

    def scan_shell_config(self, filepath: str) -> Dict[str, Any]:
        path = Path(filepath).expanduser()
        if not path.exists():
            return {"file": filepath, "exists": False}

        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return {"file": filepath, "exists": True, "error": "Permission denied"}

        issues = []
        lines = content.splitlines()

        # Slow eval patterns (can add 50-200ms to shell startup)
        slow_patterns = [
            (re.compile(r'eval\s+"?\$\('), "slow_eval", "eval $() blocks startup — consider caching"),
            (re.compile(r'\bnvm\s+use\b|\bnvm\s+load\b'), "nvm_use", "nvm use in startup is slow — use .nvmrc auto-detection"),
            (re.compile(r'pyenv\s+init'), "pyenv_init", "pyenv init in startup — ensure it's cached"),
            (re.compile(r'conda\s+activate|conda\s+init'), "conda_init", "conda activate in startup adds ~200ms"),
        ]
        for pattern, kind, desc in slow_patterns:
            for i, line in enumerate(lines, 1):
                if pattern.search(line):
                    issues.append({"line": i, "type": kind, "description": desc, "content": line.strip()[:80]})

        # Duplicate PATH entries
        path_exports = [l for l in lines if "export PATH" in l or "PATH=" in l]
        if len(path_exports) > 3:
            issues.append({
                "line": None, "type": "duplicate_path",
                "description": f"PATH set {len(path_exports)} times — may cause slowness or shadowing",
                "content": "",
            })

        # Syntax check (bash/zsh -n)
        shell = "zsh" if "zsh" in filepath else "bash"
        _, err, rc = _run([shell, "-n", str(path)], timeout=5)
        if rc != 0:
            issues.append({"line": None, "type": "syntax_error", "description": err.strip()[:200], "content": ""})

        return {
            "file": filepath,
            "exists": True,
            "line_count": len(lines),
            "issues": issues,
        }

    def full_scan(self) -> Dict[str, Any]:
        results = []
        for cfg in self.SHELL_CONFIGS + self.TOOL_CONFIGS:
            r = self.scan_shell_config(cfg)
            if r.get("exists") and r.get("issues"):
                results.append(r)
        return {
            "configs_with_issues": results,
            "total_issues": sum(len(r.get("issues", [])) for r in results),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Disk space analysis
# ─────────────────────────────────────────────────────────────────────────────

class DiskSpaceAnalyzer:
    """Predict disk usage growth and identify safe prune targets."""

    PRUNE_TARGETS = [
        "~/.cache",
        "~/.npm",
        "~/.gradle/caches",
        "~/Library/Caches",
        "~/Library/Developer/Xcode/DerivedData",
        "~/Library/Developer/CoreSimulator/Caches",
    ]

    def get_disk_usage(self) -> Dict[str, Any]:
        out, _, rc = _run(["df", "-h", "/"])
        if rc != 0:
            return {}
        lines = out.strip().splitlines()
        if len(lines) < 2:
            return {}
        parts = lines[1].split()
        return {
            "filesystem": parts[0] if parts else "",
            "total": parts[1] if len(parts) > 1 else "",
            "used": parts[2] if len(parts) > 2 else "",
            "available": parts[3] if len(parts) > 3 else "",
            "use_percent": parts[4] if len(parts) > 4 else "",
        }

    def scan_large_dirs(self, path: str = "~", depth: int = 2) -> List[Dict[str, Any]]:
        """Top-N directories by size."""
        expanded = str(Path(path).expanduser())
        out, _, rc = _run(
            ["du", "-sh", "--apparent-size"] +
            [str(p) for p in Path(expanded).iterdir() if p.is_dir()],
            timeout=20,
        )
        if rc != 0:
            # fallback without --apparent-size (macOS du)
            out, _, rc = _run(
                ["du", "-sh"] + [str(p) for p in Path(expanded).iterdir() if p.is_dir()],
                timeout=20,
            )
        items = []
        for line in out.splitlines():
            parts = line.split("\t", 1)
            if len(parts) == 2:
                items.append({"size": parts[0], "path": parts[1]})
        return items[:20]

    def estimate_prune_savings(self) -> List[Dict[str, Any]]:
        """Check known cache dirs and estimate how much space can be freed."""
        savings = []
        for target in self.PRUNE_TARGETS:
            p = Path(target).expanduser()
            if not p.exists():
                continue
            out, _, rc = _run(["du", "-sh", str(p)], timeout=10)
            if rc == 0 and out:
                size = out.split("\t")[0]
                savings.append({"path": target, "size": size})
        return savings

    def get_inode_usage(self) -> Dict[str, Any]:
        out, _, rc = _run(["df", "-i", "/"])
        if rc != 0:
            return {}
        lines = out.strip().splitlines()
        if len(lines) < 2:
            return {}
        parts = lines[1].split()
        return {
            "inodes_used": parts[2] if len(parts) > 2 else "",
            "inodes_free": parts[3] if len(parts) > 3 else "",
            "inode_use_pct": parts[4] if len(parts) > 4 else "",
        }
