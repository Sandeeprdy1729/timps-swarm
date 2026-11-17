# TIMPS Swarm — Agent Catalogue

Generated from `cli/lib/agents-manifest.js` (source of truth: `mcp_server/server.py` TOOLS). **161 agents.**

## Column legend

| Column | Meaning |
|---|---|
| **Model hint** | `sonnet`/`haiku` = routing hint written into the sub-agent `.md` files; not enforced by Python. |
| **Model map** | ✅ = has an explicit entry in `src/llm_router.py:AGENT_MODEL_MAP`; ❌ = falls back to `qwen2.5-coder:7b` @0.3 for Ollama. |
| **Dispatch** | ✅ = reachable from `timps_dispatch` keyword routing; ❌ = must be called directly. |
| **Listed** | ✅ = appears in `timps_list_agents` output; ❌ = hidden from the discovery tool. |
| **I/O** | ✅ = module performs real local/system I/O (shell, files, scanners); ⚪ = LLM-only / prompt-only. |

## Meta / orchestration — 7 agents

| Agent (MCP tool) | What it does | Model hint | Model map | Dispatch | Listed | I/O |
|---|---|---|:--:|:--:|:--:|:--:|
| `timps_list_agents` | List all TIMPS Swarm agents with their purpose, so you can choose the right one for the user's request. | haiku | ❌ | ❌ | ❌ | ⚪ |
| `timps_dispatch` | Auto-detect the best TIMPS agent for any plain-English request and run it immediately. Use this when unsure which agent to pick. Examples: 'my wifi keeps dropping', 'why is my laptop slow', 'broken python environment', 'organize my downloads'. | haiku | ❌ | ❌ | ❌ | ✅ |
| `timps_full_checkup` | Run a comprehensive computer health scan across 6 agents: system optimizer, battery analyst, security guard, network medic, backup sentinel, and update manager. Returns a combined health score and prioritised action list. | haiku | ❌ | ❌ | ❌ | ⚪ |
| `timps_batch` | Intelligently decompose a bulk task into parallel sub-tasks, execute them concurrently, and return a single aggregated result. Use this to do the same operation across many files at once. Examples: 'add tests for all handlers', 'review all API endpoints', 'add docstrings to every Python file', 'find flaky tests across all modules'. | haiku | ❌ | ❌ | ❌ | ⚪ |
| `timps_list_providers` | Show all configured LLM providers and which one is currently active. Useful for debugging which model is handling agent calls. | haiku | ❌ | ❌ | ❌ | ⚪ |
| `timps_connect_tools` | Auto-configure TIMPS Swarm as an MCP server in every AI coding tool installed on this machine (Cursor, Windsurf, GitHub Copilot, Cline, Continue, Aider, Goose, OpenCode, Gemini CLI, and more). Use --dry-run to preview what would change. | haiku | ❌ | ❌ | ❌ | ⚪ |
| `timps_tool_status` | Show which AI coding tools are installed and which ones are already connected to the TIMPS Swarm MCP server. | haiku | ❌ | ❌ | ❌ | ⚪ |

## SDLC pipeline — 1 agents

| Agent (MCP tool) | What it does | Model hint | Model map | Dispatch | Listed | I/O |
|---|---|---|:--:|:--:|:--:|:--:|
| `timps_run_task` | Run the full 10-agent SDLC pipeline (product manager → architect → code generator → reviewer → QA → security → performance → devops → docs). Use for software development tasks: writing code, fixing bugs, building APIs, etc. | sonnet | ❌ | ❌ | ✅ | ⚪ |

## Computer health — 12 agents

| Agent (MCP tool) | What it does | Model hint | Model map | Dispatch | Listed | I/O |
|---|---|---|:--:|:--:|:--:|:--:|
| `timps_system_optimizer` | Diagnose why a computer is slow. Scans: top CPU/RAM processes, startup items, thermal throttling, memory pressure. Returns a report with specific processes to kill and startup items to disable. Generates a dry-run cleanup shell script. | haiku | ✅ | ✅ | ✅ | ✅ |
| `timps_file_organizer` | Scan Downloads and Desktop for clutter: duplicates, large files, unnamed junk. Generates a folder organisation plan and a move script (dry-run — no files moved until user approves). | haiku | ✅ | ✅ | ✅ | ✅ |
| `timps_environment_doctor` | Diagnose broken development environments. Checks Python, Node.js, Docker, Git, PATH integrity, shell config conflicts. Returns exact terminal commands to fix each issue. | haiku | ✅ | ✅ | ✅ | ✅ |
| `timps_security_guard` | Security scan: open network ports, running process anomalies, app camera/microphone/location permissions (macOS TCC). Returns CVSS-rated findings and mitigation commands. | haiku | ✅ | ✅ | ✅ | ✅ |
| `timps_network_medic` | Diagnose network problems: ping internet/Cloudflare, DNS resolution, WiFi signal, traceroute, open ports. Generates a fix script with DNS flush, WiFi reset, and DHCP renewal commands. | haiku | ✅ | ✅ | ✅ | ✅ |
| `timps_battery_analyst` | Identify battery drainers. Reads battery %, health cycle count, and ranks processes by CPU usage (proxy for energy drain). Generates kill commands for the top energy vampires. | haiku | ✅ | ✅ | ✅ | ✅ |
| `timps_update_manager` | Check for pending updates: macOS/Linux OS, Homebrew packages, global npm packages, pip packages. Returns a prioritised update plan (security first) with a safe ordered shell script. | haiku | ✅ | ✅ | ✅ | ✅ |
| `timps_log_interpreter` | Read crash logs and system logs, extract stack traces, and explain each crash in plain English. Classifies as app bug / OS bug / hardware / user error. Pass a log file path to analyse a specific log. | haiku | ✅ | ✅ | ✅ | ✅ |
| `timps_privacy_cleaner` | Privacy audit: count cookies per browser (Chrome, Firefox, Edge, Brave), list macOS app permissions (camera, mic, location, contacts). Returns a cleanup manifest — no data is deleted until user reviews. | haiku | ✅ | ✅ | ✅ | ✅ |
| `timps_media_librarian` | Scan Photos, Downloads, Desktop for media chaos: unnamed photos, screenshot backlog, oversized videos. Suggests a date-based rename plan and generates ffmpeg compression commands (dry-run). | haiku | ✅ | ✅ | ✅ | ✅ |
| `timps_backup_sentinel` | Audit backup health: Time Machine last backup time, all local git repos with uncommitted/unpushed changes, large files on Desktop/Documents not tracked by git or cloud. Returns a risk score and backup script. | haiku | ✅ | ✅ | ✅ | ✅ |
| `timps_context_switcher` | Analyse current work context: active apps, estimated browser tabs, current git branch and recent commits. Identifies distraction apps and generates a focus-mode script to quit them. | haiku | ✅ | ✅ | ✅ | ✅ |

## Context — 1 agents

| Agent (MCP tool) | What it does | Model hint | Model map | Dispatch | Listed | I/O |
|---|---|---|:--:|:--:|:--:|:--:|
| `timps_context_briefing` | Get a 3-sentence resumption briefing from the Context Keeper: what you were working on, current state (uncommitted changes, broken tests), and recommended next step. Use when the user says 'what was I doing' or 'catch me up'. | haiku | ❌ | ✅ | ❌ | ⚪ |

## Agent kernel — 2 agents

| Agent (MCP tool) | What it does | Model hint | Model map | Dispatch | Listed | I/O |
|---|---|---|:--:|:--:|:--:|:--:|
| `timps_delegate` | Delegate a multi-step goal to the TIMPS Agent Kernel. The kernel plans, routes to specialist agents, and returns a structured result. Use for complex goals like 'fix the auth bug and ensure 80% test coverage'. | sonnet | ❌ | ❌ | ❌ | ✅ |
| `timps_kernel_status` | Check the status of a previously delegated kernel run by its run_id. | sonnet | ❌ | ❌ | ❌ | ⚪ |

## Developer workflow — 12 agents

| Agent (MCP tool) | What it does | Model hint | Model map | Dispatch | Listed | I/O |
|---|---|---|:--:|:--:|:--:|:--:|
| `timps_issue_triager` | Triage a bug report or GitHub issue: detect duplicates, assign severity (critical/high/medium/low), suggest labels and owner. Pass the raw issue title and body text. | haiku | ✅ | ❌ | ❌ | ✅ |
| `timps_boilerplate_architect` | Scaffold a new project: folder structure, stub files, setup commands. Supports any language or framework — describe what you're building. | haiku | ✅ | ❌ | ❌ | ✅ |
| `timps_pr_reviewer` | Review a pull request diff for blockers, suggestions, and nitpicks. Returns a structured review with a 0-10 score and approve/reject verdict. | haiku | ✅ | ❌ | ❌ | ✅ |
| `timps_dependency_sentinel` | Scan a dependency manifest (requirements.txt, package.json, go.mod, Cargo.toml) for CVEs and severely outdated packages. Returns a severity-ranked report with upgrade commands. | haiku | ✅ | ❌ | ❌ | ✅ |
| `timps_unit_test_writer` | Analyse source code and generate a comprehensive test suite: happy paths, edge cases, error conditions. Returns a complete test file ready to run. | haiku | ✅ | ❌ | ❌ | ✅ |
| `timps_docstring_generator` | Read raw source code and insert production-quality docstrings in your preferred format (Google, Sphinx, NumPy, JSDoc, Doxygen). Logic is never changed — only documentation is added. | haiku | ✅ | ❌ | ❌ | ✅ |
| `timps_log_detective` | Cluster production log errors, identify root cause, and suggest a fix. Handles stack traces, JSON logs, syslog, and journald output. | haiku | ✅ | ❌ | ❌ | ✅ |
| `timps_sql_optimizer` | Analyse a slow SQL query and return: the optimised rewrite, index recommendations with CREATE INDEX SQL, and an estimated speedup. Supports PostgreSQL, MySQL, SQLite, MSSQL. | haiku | ✅ | ❌ | ❌ | ✅ |
| `timps_sprint_reporter` | Generate a formatted daily standup report from task lists. Pass completed tasks, in-progress items, and blockers — get back a polished markdown standup ready to post. | haiku | ✅ | ❌ | ❌ | ✅ |
| `timps_flaky_test_hunter` | Find non-deterministic tests from CI run history. Returns ranked list of flaky tests, suspected causes, and fix suggestions. | haiku | ✅ | ❌ | ❌ | ✅ |
| `timps_api_contract_auditor` | Diff two API specs (OpenAPI/AsyncAPI) and flag breaking changes, deprecations, and safe additions. Returns a semver recommendation and a migration guide for clients. | haiku | ✅ | ❌ | ❌ | ✅ |
| `timps_content_multiplier` | Transform a long-form technical post into multiple short-form formats: tweet thread, LinkedIn post, changelog entry, docs blurb, and HN title. | haiku | ✅ | ❌ | ❌ | ✅ |

## Knowledge work — 7 agents

| Agent (MCP tool) | What it does | Model hint | Model map | Dispatch | Listed | I/O |
|---|---|---|:--:|:--:|:--:|:--:|
| `timps_inbox_gatekeeper` | Triage a batch of emails: flag urgent ones, draft routine replies, identify newsletters to unsubscribe from. Pass a list of email objects with 'from', 'subject', 'body'. | haiku | ✅ | ❌ | ❌ | ✅ |
| `timps_meeting_condenser` | Extract action items, decisions, and open questions from a meeting transcript. Returns a structured summary with owners and deadlines. | haiku | ✅ | ❌ | ❌ | ✅ |
| `timps_research_scout` | Deep-dive research on any topic. Returns a structured brief: key findings, consensus view, controversies, recommended actions, and sources. Depth options: quick, medium (default), deep. | haiku | ✅ | ❌ | ❌ | ✅ |
| `timps_trend_monitor` | Monitor keywords across Hacker News, Reddit, GitHub, and Dev.to for spikes in interest. Returns trend direction, sentiment, and a digest summary. | haiku | ✅ | ❌ | ❌ | ✅ |
| `timps_data_wrangler` | Clean and normalise messy data: CSV, JSON, PDF extracts, copy-pasted tables. Returns cleaned records, a quality score, and SQL insert hint. | haiku | ✅ | ❌ | ❌ | ✅ |
| `timps_competitor_tracker` | Monitor competitors for pricing changes, new features, job postings, and public sentiment. Returns a competitive intelligence brief. | haiku | ✅ | ❌ | ❌ | ✅ |
| `timps_agri_commodity_forecaster` | Forecast Indian agri-commodity prices (mandi arrivals, MSP, weather, festival demand). Returns direction, confidence, and a hedge recommendation for farmers / FPOs / traders. | haiku | ❌ | ❌ | ✅ | ✅ |

## Expert diagnostics — 51 agents

| Agent (MCP tool) | What it does | Model hint | Model map | Dispatch | Listed | I/O |
|---|---|---|:--:|:--:|:--:|:--:|
| `timps_dependency_rebel` | Detect dependency conflicts, vulnerabilities, and outdated packages across Python and Node. Returns a fix plan and remediation script. | sonnet | ✅ | ✅ | ❌ | ✅ |
| `timps_merge_conflict_predictor` | Predict merge conflicts between two branches before merging, with file-level and line-level overlap analysis. | sonnet | ✅ | ✅ | ❌ | ✅ |
| `timps_tech_debt_quantifier` | Scan codebase for TODO/FIXME density, cyclomatic complexity hotspots, and deprecated patterns. Returns a prioritised debt repayment plan. | sonnet | ✅ | ✅ | ❌ | ✅ |
| `timps_migration_pilot` | Analyse a codebase for breaking-change APIs given a target library/framework upgrade. Returns a step-by-step migration checklist. | sonnet | ✅ | ✅ | ❌ | ✅ |
| `timps_flaky_test_detective` | Identify flaky tests by scanning for timing dependencies, random data, and external HTTP calls. Reads pytest failure cache for history. | sonnet | ✅ | ✅ | ❌ | ✅ |
| `timps_onboarding_mentor` | Generate a customised onboarding guide: most-touched files, architecture overview, key modules, recent PR walkthroughs. | sonnet | ✅ | ✅ | ❌ | ✅ |
| `timps_incident_responder` | Multi-source log correlation for production incidents. Gathers Docker + app logs, builds a timeline, and generates a triage report. | sonnet | ✅ | ✅ | ❌ | ✅ |
| `timps_cloud_cost_auditor` | Scan Terraform configs for waste (over-provisioned instances, missing deletion protection) and check AWS CLI for idle resources. | sonnet | ✅ | ✅ | ❌ | ✅ |
| `timps_certificate_rotator` | Check TLS certificate expiry for all hosts found in config files. Warns 30 days before expiry and generates certbot renewal commands. | sonnet | ✅ | ✅ | ❌ | ✅ |
| `timps_terraform_plan_reviewer` | Review terraform plan output for destructive changes. Requires explicit approval before allowing apply on high-risk plans. | sonnet | ✅ | ✅ | ❌ | ✅ |
| `timps_dotfile_doctor` | Detect errors and performance issues in shell config files (.zshrc, .bashrc, .gitconfig). Finds slow evals, duplicate PATH entries, syntax errors. | sonnet | ✅ | ✅ | ❌ | ✅ |
| `timps_disk_space_prophet` | Predict disk usage trends, identify cache directories safe to prune, and warn before 'no space left on device' events. | sonnet | ✅ | ✅ | ❌ | ✅ |
| `timps_code_archaeology` | Analyse git history to build an AST import graph, risk map, and tribal knowledge document. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_pattern_detector` | Detect duplicate code blocks, god classes, magic numbers, and anti-patterns in a codebase. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_dataset_agent` | Validate and clean ML training datasets; generate data cards and quality reports. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_ai_safety_agent` | Audit LLM applications against OWASP LLM Top 10 (LLM01-LLM10) with mitigations. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_web_scraping` | Generate Playwright/Scrapy/httpx scrapers with anti-bot config and data extraction logic. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_data_pipeline` | Design dbt/Airflow/Prefect/Dagster ETL/ELT pipelines with monitoring and lineage. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_graphql_agent` | Write GraphQL SDL schemas, resolvers, DataLoader, subscriptions, and federation config. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_embedded_agent` | Create Arduino/ESP32/RPi firmware, HAL headers, CMakeLists, and OTA update scripts. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_postmortem_agent` | Write blameless postmortems: 5 Whys, root causes, P0-P2 action items, runbooks. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_load_testing` | Generate k6/Artillery/Locust load test scripts with ramp-up plans and Grafana dashboards. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_disaster_recovery` | Design RTO/RPO-aware DR plans, failover runbooks, and DR test scripts for cloud systems. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_edge_agent` | Generate Cloudflare Workers/Vercel Edge/Fastly code with KV storage and geo-routing. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_compliance_auditor` | Map a codebase + infra config against SOC 2 / ISO 27001 / HIPAA / PCI-DSS / GDPR controls; produce an evidence pack and gap report. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_incident_response_coordinator` | Turn an active incident (SIEM alert, customer report, CVE disclosure) into a play-by-play response with comms, containment, and a postmortem stub. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_kubernetes_navigator` | Diagnose Kubernetes workloads: pods, services, ingress, RBAC, resources, network policies. Outputs fix YAML and Helm/Kustomize patches. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_pipeline_healer` | Read a failing CI/CD run and produce a minimal diff to make it green: cache tweaks, image bumps, secret injection, retry policies. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_docker_compose_architect` | Compose a production-grade multi-service docker-compose (or compose.yaml) for a project: env, healthchecks, volumes, networks, profiles. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_test_intelligence` | Analyse test suite + git bug history to find untested code paths, suggest property-based tests, and propose a mutation-testing config. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_changelog_generator` | Generate a Conventional Commits changelog from commit history, PRs, and issues; supports semver bump recommendation. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_db_migration_pilot` | Plan a zero-downtime database migration: expand-contract phases, backfill scripts, dual-write strategy, kill-switches, rollback plan. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_log_pattern_analyzer` | Cluster production log errors, identify root cause, suggest a fix. Handles stack traces, JSON logs, syslog, and journald output. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_api_perf_profiler` | Profile an API from access logs / traces — p50/p95/p99 by endpoint, slow query, N+1 detection, and concrete optimisations. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_accessibility_tester` | Audit a frontend (HTML / React / Vue) for WCAG 2.2 AA & AAA issues — colour contrast, ARIA, keyboard nav, focus order, screen reader hints. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_visual_regression_detective` | Diff design tokens / Storybook / screenshot baselines and surface unintended visual changes with root-cause hints. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_mcp_server_generator` | Scaffold a complete Model Context Protocol (MCP) server: tools, resources, prompts, server.py, pyproject, smoke-test client, README. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_ai_workflow_orchestrator` | Turn a plain-English multi-step workflow into executable code for LangGraph, Temporal, or Claude-Flow — plus a Mermaid diagram and tests. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_local_rag_builder` | Build a fully-local RAG pipeline (Ollama embeddings + Chroma/FAISS + reranker + chat) from a corpus description. Emits ingest, retrieve, generate, evaluate, Dockerfile, Makefile. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_git_workflow_automator` | Generate an opinionated git workflow: pre-commit hooks, commitlint, lefthook, semantic-release / release-please config, PR template, branch-protection policy, CODEOWNERS. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_web_search` | Multi-engine web search (DuckDuckGo / Brave / SerpAPI / Bing / Hacker News) with deduplication, content extraction, and LLM-synthesised answer with [N] citations. Hacker News covers tech/startup discussion via the official Firebase API (top/new/best/Ask/Show/jobs) and Algolia HN Search. Use for live lookups, news, vendor docs, and competitive intel. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_phishing_simulator` | Generate a realistic, organisation-tailored phishing simulation: emails, landing pages, payload tracking, and a click-through metrics plan. Strictly for authorised training use. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_api_security_tester` | Run an OWASP API Security Top-10 (2023) audit against an OpenAPI spec or live endpoint — broken auth, BOLA, mass assignment, rate-limit, SSRF, injection — with a runnable test harness. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_container_image_scanner` | Scan a container image / Dockerfile for CVEs, misconfigurations, and supply-chain risk. Wraps trivy/grype/syft when present; falls back to static analysis of the Dockerfile. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_contract_reviewer` | Review a contract (MSA, NDA, SaaS, vendor agreement) for red-flags: indemnification, liability caps, IP, data, termination, SLAs. Returns a clause-by-clause scorecard and a redline. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_iac_drift_detector` | Detect drift between Terraform / Pulumi / CloudFormation state and live cloud — produces a ranked diff, blast-radius estimate, and a safe `terraform plan` review. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_license_compliance_scanner` | Scan source + manifests for OSS license usage (GPL/AGPL/LGPL/SSPL/Commercial), produce a per-dependency report, and a copyleft-compatibility matrix for your distribution model. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_adr_writer` | Turn a technical decision into a Michael Nygard-style Architecture Decision Record: context, options matrix, decision, consequences, and a rendered Markdown file. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_game_day_facilitator` | Plan and run a chaos-engineering game-day: hypothesis, blast radius, rollback, comms tree, inject schedule, success criteria, and a blameless retrospective template. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_court_case_summarizer` | Summarise a court judgment / order: bench, facts, issues, holdings, reasoning, ratio, and citations in a structured brief. For legal research, not legal advice. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_computer_use_agent` | Plan a GUI / computer-use task and emit OS-specific step scripts (cliclick / xdotool / PowerShell) with safety approval gates. Pairs with the runtime computer_use tools. | sonnet | ❌ | ❌ | ✅ | ⚪ |

## Specialist (priority) — 68 agents

| Agent (MCP tool) | What it does | Model hint | Model map | Dispatch | Listed | I/O |
|---|---|---|:--:|:--:|:--:|:--:|
| `timps_research_agent` | Research Agent — runs BEFORE any coding task. Searches documentation, GitHub issues, Stack Overflow, and the web to gather context so all downstream agents have grounded information. Returns a structured brief: findings, gotchas, recommended approach, sources. | sonnet | ✅ | ❌ | ❌ | ✅ |
| `timps_api_design_agent` | API Design Agent — generates a complete OpenAPI 3.1 spec (YAML) from a natural-language description. Enforces REST/GraphQL best practices, versioning strategy, and consistent naming BEFORE code generation starts. Returns the spec + a design rationale document. | sonnet | ✅ | ❌ | ❌ | ✅ |
| `timps_db_agent` | DB Agent — schema design, query optimisation, and migration scripts. Given a description of your data model it produces: CREATE TABLE SQL, an ER diagram in Mermaid, index recommendations, a migration script (Alembic / Flyway / raw SQL), and query templates. Pairs with the sql_injection LoRA for secure query generation. | sonnet | ✅ | ❌ | ❌ | ✅ |
| `timps_dependency_agent` | Dependency Agent — runs pip-audit / npm audit / cargo audit after code generation. Produces: a CVE severity report, a license compliance check, a version pinning strategy, and a safe upgrade script. Security-conscious devs' favourite agent. | sonnet | ✅ | ❌ | ❌ | ✅ |
| `timps_n8n_workflow_agent` | n8n Workflow Agent — converts a plain-English task description into a complete, importable n8n workflow JSON. Knows all n8n core nodes, integrations (Slack, Gmail, GitHub, Notion, Airtable, HTTP Request, Webhook, Cron, etc.), and expression syntax. Returns the workflow JSON + a visual description of every node. | sonnet | ✅ | ❌ | ❌ | ✅ |
| `timps_refactoring_agent` | Detect code smells and produce a fully refactored version with a diff summary, complexity scores, and improvement list. | sonnet | ❌ | ❌ | ❌ | ✅ |
| `timps_test_data_agent` | Generate realistic, edge-case-covering seed / fixture data for any JSON schema, SQL DDL, or plain-text description. | sonnet | ❌ | ❌ | ❌ | ✅ |
| `timps_monitoring_agent` | Generate Prometheus metric definitions, Grafana dashboard JSON, alerting rules, and instrumentation code snippets. | sonnet | ❌ | ❌ | ❌ | ✅ |
| `timps_ui_ux_agent` | Generate a UI component spec, implementation code, Storybook story, design tokens, and WCAG accessibility audit. | sonnet | ❌ | ❌ | ❌ | ✅ |
| `timps_i18n_agent` | Extract translatable strings from source code, generate translation JSON files for multiple locales, and flag RTL/cultural issues. | sonnet | ❌ | ❌ | ❌ | ✅ |
| `timps_cost_optimizer` | Estimate monthly/annual cloud cost for an architecture and generate a prioritised list of savings optimisations. | sonnet | ❌ | ❌ | ❌ | ✅ |
| `timps_self_critic_agent` | Score any agent's output on a 1–10 quality scale, identify weaknesses, and automatically re-run the originating agent with an improved prompt until the score meets the threshold. This closes the quality feedback loop across the entire swarm. | sonnet | ❌ | ❌ | ❌ | ✅ |
| `timps_technical_debt` | Quantify technical debt via radon complexity + git churn + TODO density; output a debt roadmap. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_memory_agent` | Store, recall, and manage TIMPS run history and contextual memory. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_learning_agent` | Analyse past successful runs and distil prompt improvements for all agents. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_agent_composer` | Generate a new fully-functional Python agent file from a natural-language description. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_prompt_engineer` | Rewrite prompts with Chain-of-Thought, XML tags, and few-shot examples for better LLM output. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_model_evaluator` | Create evaluation harnesses, adversarial test inputs, and RAGAS config for LLM models. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_rag_designer` | Design chunking/embedding/retrieval/reranking RAG pipelines for LlamaIndex or LangChain. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_finetuning_agent` | Generate complete LoRA/MLX/Axolotl/Unsloth fine-tuning pipelines with push-to-hub scripts. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_vector_db_agent` | Design Qdrant/Pinecone/Weaviate/pgvector schemas and integration code. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_gst_compliance` | Generate GSTR-1/3B filings, e-invoice XML, ITC reconciliation reports (India GST). | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_abdm_agent` | Implement ABHA enrollment, HIP/HIU flows, FHIR R4 bundles, and consent workflows (India ABDM). | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_upi_agent` | Generate UPI deep links, QR codes, Razorpay/Cashfree webhook handlers (India UPI). | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_digilocker_agent` | Implement DigiLocker OAuth, document pull, Aadhaar OTP, PAN verify, and eKYC flows (India). | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_indiehacker_agent` | India GTM plan: INR pricing tiers, Razorpay integration, GST invoice generation. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_realtime_agent` | Build WebSocket/SSE/Redis Pub-Sub/Kafka server+client real-time systems. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_mobile_agent` | Scaffold React Native/Flutter/Expo apps with push notifications and deep links. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_browser_automation` | Generate Playwright E2E tests with page objects, fixtures, and CI config. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_cli_tool_agent` | Generate Click/Cobra/Commander CLI tools with shell completions and release workflows. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_analytics_agent` | Set up PostHog/Mixpanel/Amplitude event tracking, funnels, and dashboards. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_ab_testing_agent` | Design A/B tests with Welch's t-test power analysis and GrowthBook configuration. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_monetization_agent` | Configure Stripe/LemonSqueezy products, checkout flows, webhooks, and dunning emails. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_seo_agent` | Run Lighthouse CI, generate schema.org JSON-LD, fix Core Web Vitals, build sitemaps. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_sprint_planning_agent` | Decompose epics into sprint tickets with estimates, dependencies, and GitHub Issues payload. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_feature_flag` | Design feature flags with LaunchDarkly/Flagsmith/GrowthBook targeting rules and rollout plans. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_finops_agent` | Analyse cloud costs with Infracost, generate rightsizing recommendations and budget alerts. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_secrets_management` | Scan for hardcoded secrets, generate Vault/AWS Secrets Manager migration code and pre-commit hooks. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_robotics_agent` | Generate ROS2 nodes, URDF descriptions, motion planning config, and ISO 10218-1 safety analysis. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_web3_agent` | Audit smart contracts with Slither/Mythril patterns; generate Solidity code with gas optimisation. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_federated_learning` | Design Flower/FedAvg/PySyft FL pipelines with differential privacy and aggregation strategies. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_quantum_ready` | Identify quantum-vulnerable algorithms, generate Qiskit circuits, and produce NIST PQC migration plans. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_threat_intel_analyst` | Ingest threat feeds (CVE, MITRE ATT&CK, CISA KEV) and produce a threat brief with detection rules and prioritised mitigations. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_security_remediation` | Convert a security finding (CVE, SAST, secret, misconfig) into a step-by-step patch plan with a working code diff and rollback. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_release_manager` | Produce a release plan: SemVer bump, release notes, rollout/canary strategy, rollback gate, customer-comms draft, and stakeholder checklist. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_tech_writer_assistant` | Refresh a project README, write ADRs, generate a 'Getting Started' guide, an FAQ, and a reference page from the codebase. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_model_perf_monitor` | Monitor an ML model in production: drift, accuracy decay, latency, and cost — with alerting thresholds and a re-training trigger plan. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_red_team_agent` | Plan and execute an OWASP-style red-team engagement: threat model, adversarial test cases, payloads, runnable exploit harness, and a remediation checklist. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_prompt_injection_scanner` | Scan prompts, system messages, and tool schemas for prompt-injection / jailbreak / data-exfiltration risk. Produces a severity-rated report and hardened prompt rewrites. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_dpdp_act_auditor` | Audit a system or data flow against India's Digital Personal Data Protection Act 2023: consent, notice, data-principal rights, breach, penalties, and a remediation roadmap. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_fssai_compliance_agent` | Assess an F&B product / packaging against India's FSSAI regulations: license type, label checklist, additive and claim restrictions, and a submission-ready checklist. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_observability_cost_optimizer` | Analyse your observability bill (Datadog / New Relic / Grafana Cloud / Splunk) and recommend cardinality pruning, sampling, log-volume cuts, and tier migrations with projected savings. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_service_mesh_configurator` | Generate production-grade service-mesh config (Istio / Linkerd / Consul) — mTLS, traffic policies, retries, circuit-breakers, observability, multi-cluster, and a migration plan. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_sbom_generator` | Generate a CycloneDX / SPDX Software Bill of Materials from a project tree + manifests, integrate syft/trivy if available, and flag license and supply-chain risks. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_deep_research_agent` | Multi-hop, multi-source research planner: decomposes a query, runs parallel web searches, cross-references, and returns a sourced report with [N] citations and a bottom-line answer. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_agent_marketplace_curator` | Curate the best AI agent / MCP / LLM-tool marketplaces and recommend picks by use-case. Tracks pulse.mcp.run, glama.ai, mcp.so, OpenAI GPT Store, Claude tool directory. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_churn_predictor` | Score accounts/users for churn risk from behavioural signals, build a survival-curve forecast, segment at-risk cohorts, and recommend save plays per segment. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_demand_forecaster` | Produce a SKU/location-level demand forecast with seasonality, promotions, and trend. Returns intervals, backtest MAPE/MASE, and an ordering recommendation. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_calendar_optimizer` | Re-design a noisy calendar: time-block deep work, batch meetings, protect maker time, add commute/exercise buffers, and emit an ICS patch and a focus-mode script. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_wearable_health_coach` | Interpret wearable / fitness data (HRV, sleep, RHR, steps, SpO2) into an actionable, evidence-based weekly coaching plan with safety guardrails. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_cold_email_sequence_writer` | Write a 5-7 step cold-outreach email sequence for a persona + offer, with subject A/B variants, social proof, objection handling, and a reply-promise CTA. Spam-safe. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_demo_video_script_writer` | Write a punchy 60-90s product demo video script: hook, problem, demo beats, payoff, CTA — with storyboard, B-roll suggestions, and on-screen copy. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_podcast_show_notes_writer` | Turn a podcast transcript / outline into SEO-friendly show notes: title, summary, chapter timestamps, key quotes, links, guest bio, and 3 tweet drafts. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_storybook_story_generator` | Generate an original illustrated children's story for a target age, theme, and moral: outline, full prose, page breaks, illustration prompts, and a printable PDF layout spec. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_win_loss_analyst` | Analyse a set of won/lost deals to surface the real reasons — pricing, champion, timing, competitor, fit — and recommend sales-coaching and product fixes. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_voice_agent_designer` | Design a production voice / phone agent: persona, system prompt, SSML, tool calls, barge-in handling, escalation rules, latency budget, and test utterances. | sonnet | ❌ | ❌ | ✅ | ⚪ |
| `timps_rag_evaluator` | Run a RAGAS-style evaluation of a RAG pipeline: context precision/recall, faithfulness, answer relevance, MRR/NDCG, with a runnable eval harness and an improvement plan. | sonnet | ❌ | ❌ | ✅ | ✅ |
| `timps_tracing_emitter` | Generate an OpenTelemetry tracing bootstrap: service name, resource attributes, auto-instrumentation, sampling, span/metric/log pipeline, and exporter config. | sonnet | ❌ | ❌ | ✅ | ⚪ |
