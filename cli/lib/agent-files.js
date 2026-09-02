/**
 * agent-files.js — render native sub-agent Markdown files for all TIMPS
 * agents (currently 161), so Claude Code / Cursor / Codex pick them up as
 * parallel sub-agents (not just MCP tools).
 *
 * For each agent we write:
 *   ~/.claude/agents/timps-<name>.md      (Claude Code native sub-agent)
 *   ~/.claude/agents/timps-<name>.md      (Cursor also reads this path in Composer 1.5+)
 *   ~/.codex/agents/timps-<name>.md       (Codex-style — uses the same frontmatter)
 *
 * Each file is small: a YAML frontmatter block (name, description, tools, model)
 * and a short system-prompt body that wraps the MCP tool call.
 *
 * Re-running writeSubAgents() is idempotent — files are only written if the
 * on-disk content differs from the rendered output.
 */
import { existsSync, readFileSync, writeFileSync, mkdirSync, readdirSync, unlinkSync } from "fs";
import { join, dirname } from "path";
import { AGENTS, agentFileBase } from "./agents-manifest.js";

/**
 * Routing hints by agent name — adds a "Routing hint" section to the agent
 * .md file suggesting `timps_batch` for bulk ops and related agents.
 */
const ROUTING_HINTS = {
  // SDLC
  timps_run_task:             "For bulk operations across many files (e.g. adding tests to all handlers), use `timps_batch` instead. Related: `timps_pr_reviewer`, `timps_unit_test_writer`, `timps_docstring_generator`.",
  timps_pr_reviewer:          "For reviewing every file in a directory in one shot, use `timps_batch` with `agent_type: 'pr_reviewer'`. Related: `timps_run_task`.",
  timps_unit_test_writer:     "For adding tests to every module in a project, use `timps_batch` with `agent_type: 'unit_test_writer'`. Related: `timps_run_task`.",
  timps_docstring_generator:  "For documenting every function across a codebase, use `timps_batch` with `agent_type: 'docstring_generator'`. Related: `timps_run_task`, `timps_tech_writer_assistant`.",
  timps_refactoring_agent:    "For bulk refactoring across many files, use `timps_batch` with `agent_type: 'refactoring_agent'`. Related: `timps_pattern_detector`, `timps_technical_debt`.",
  timps_api_contract_auditor: "For auditing multiple API specs at once, use `timps_batch`. Related: `timps_api_design_agent`, `timps_api_security_tester`.",
  timps_content_multiplier:   "Related: `timps_demo_video_script_writer`, `timps_podcast_show_notes_writer`, `timps_cold_email_sequence_writer`.",
  // Health
  timps_system_optimizer:     "Run `timps_full_checkup` for a comprehensive 6-agent health scan. Related: `timps_environment_doctor`, `timps_update_manager`.",
  timps_file_organizer:       "Related: `timps_media_librarian`, `timps_disk_space_prophet`.",
  timps_environment_doctor:   "Related: `timps_dotfile_doctor`, `timps_system_optimizer`.",
  timps_network_medic:        "Related: `timps_security_guard` (port scan), `timps_full_checkup`.",
  timps_battery_analyst:      "Related: `timps_system_optimizer`, `timps_full_checkup`.",
  timps_update_manager:       "Related: `timps_system_optimizer`, `timps_dependency_rebel`.",
  timps_log_interpreter:      "Related: `timps_log_detective`, `timps_log_pattern_analyzer`, `timps_incident_responder`.",
  timps_security_guard:       "Related: `timps_api_security_tester`, `timps_container_image_scanner`, `timps_secrets_management`.",
  timps_privacy_cleaner:      "Related: `timps_security_guard`.",
  timps_media_librarian:      "Related: `timps_file_organizer`.",
  timps_backup_sentinel:      "Related: `timps_disk_space_prophet`.",
  timps_context_switcher:     "Related: `timps_calendar_optimizer`.",
  // Developer
  timps_issue_triager:        "Related: `timps_sprint_planning_agent`, `timps_sprint_reporter`.",
  timps_boilerplate_architect:"Related: `timps_cli_tool_agent`, `timps_db_agent`, `timps_api_design_agent`.",
  timps_dependency_sentinel:  "For scanning all manifests in a monorepo, use `timps_batch` with `agent_type: 'dependency_agent'`. Related: `timps_dependency_agent`, `timps_dependency_rebel`.",
  timps_log_detective:        "Related: `timps_log_interpreter`, `timps_log_pattern_analyzer`, `timps_incident_responder`.",
  timps_sql_optimizer:        "Related: `timps_db_agent`, `timps_db_migration_pilot`.",
  timps_sprint_reporter:      "Related: `timps_sprint_planning_agent`, `timps_issue_triager`.",
  timps_flaky_test_hunter:    "Related: `timps_flaky_test_detective`, `timps_test_intelligence`.",
  // Knowledge
  timps_research_scout:       "For multi-hop deep research, use `timps_deep_research_agent`. Related: `timps_trend_monitor`, `timps_competitor_tracker`.",
  timps_data_wrangler:        "For processing many data files at once, use `timps_batch` with `agent_type: 'data_wrangler'`.",
  timps_competitor_tracker:   "Related: `timps_research_scout`, `timps_trend_monitor`, `timps_web_search`.",
  // Priority agents
  timps_db_agent:             "Related: `timps_sql_optimizer`, `timps_db_migration_pilot`.",
  timps_dependency_agent:     "For scanning all manifests in a monorepo, use `timps_batch`. Related: `timps_dependency_sentinel`, `timps_dependency_rebel`.",
  timps_api_design_agent:     "Related: `timps_api_contract_auditor`, `timps_api_security_tester`, `timps_graphql_agent`.",
  timps_n8n_workflow_agent:   "Related: `timps_ai_workflow_orchestrator`.",
  timps_batch:                "For bulk operations across many files: set `agent_type` to the specialist agent name and `working_dir` to the project root. This is the TIMPS parallel-execution workhorse.",
  timps_dispatch:              "Auto-routes any plain-English request to the right specialist agent. Use when unsure which agent to pick.",
  timps_research_agent:       "Related: `timps_research_scout`, `timps_deep_research_agent`, `timps_web_search`.",
  timps_learning_agent:       "Related: `timps_memory_agent`, `timps_code_archaeology`.",
};

/**
 * Render the frontmatter + body for a single agent.
 * The 'description' field is what Claude Code uses to decide when to delegate
 * to this sub-agent, so we keep it concrete and trigger-rich.
 *
 * NOTE: The full description is double-quoted and any embedded `"` and `\n`
 * are escaped. This is required because ~30% of agent descriptions contain
 * `:` (e.g. "Re-design a noisy calendar: time-block...") which would otherwise
 * be parsed by YAML as a mapping key and break Claude Code / Cursor / Codex
 * frontmatter loading.
 */
export function renderAgentFile(agent, targetId = "claude-code") {
  const base = agentFileBase(agent.name);
  const toolName = agent.name;
  const description = agent.description;
  const hint = ROUTING_HINTS[agent.name];

  // The sub-agent runs on the HOST's own model (opencode's model, Claude
  // Code's model, etc.). The timps-swarm server is in "raw gather" mode
  // (TIMPS_LLM_MODE=raw): it collects the deterministic data and returns it
  // WITHOUT calling any server-side LLM. This sub-agent's job is to write the
  // analysis/report itself, on the host model, using that gathered data.
  const desc = `${description} You are a native specialist: gather the data via the timps-swarm MCP tool, then write the report yourself on your own model.`
    .replace(/\\/g, "\\\\")
    .replace(/"/g,  "\\\"")
    .replace(/\n/g, " ");

  const fm = [
    "---",
    `name: ${toolName}`,
    `description: "${desc}"`,
  ];
  if (targetId === "opencode") {
    // opencode sub-agents run on the session model; `mode: subagent` makes
    // them available via the `task` tool. No `tools:` restriction so the
    // sub-agent can use opencode-native tools (read/bash/grep/websearch).
    fm.push("mode: subagent");
  } else {
    // Claude Code / Cursor / Codex flavour.
    fm.push(`category: ${agent.category}`);
    fm.push(`model: ${agent.model}`);
  }
  fm.push("---");
  const frontmatter = fm.join("\n");

  const bodyLines = [
    "",
    `# ${base.replace(/_/g, " ")}`,
    "",
    `You are the **${base.replace(/_/g, " ")}** specialist sub-agent from the TIMPS Swarm (category: \`${agent.category}\`). You run on the user's own model.`,
    "",
    "## Your job",
    "",
    `${description}`,
    "",
    "## How to work (run on YOUR model — the user's LLM)",
    "",
    "1. **Gather the real data first.** Call the MCP tool `" + toolName + "` via the `mcp__timps-swarm__" + toolName + "` tool handle, passing the user's request/code/context. The server is in RAW-GATHER mode: it collects the deterministic data (file scans, command outputs, logs, diffs, code) and returns it — it does NOT generate any analysis.",
    "2. **Use that gathered raw data to do the actual specialist work yourself.** Apply your expertise to produce the deliverable described in \"Your job\": the report, the fix, the refactor, the test suite, the review, the plan, the generated code, etc. This is the step that must run on YOUR model — not a server-side LLM.",
    "3. If the raw data is incomplete for the task, use your own tools (read files, run shell commands, grep/glob the codebase, web search) to gather what else you need, then complete the work.",
    "4. Return a complete, well-structured result to the parent agent. This is a real deliverable, not just a pass-through.",
    "",
    "## Notes",
    "",
    "- You MAY use opencode-native tools (read, edit, bash, grep, glob, websearch, webfetch) as needed to complete the work.",
    "- Do NOT chain multiple TIMPS MCP tools in one invocation unless the task genuinely requires it.",
    "- If the server returns a JSON object with `raw_data`, `_mode`, `_note`, or similar fields, those are the gathered inputs — analyse them.",
    "",
  ];

  if (hint) {
    bodyLines.push(
      "",
      "## Routing hint",
      "",
      hint,
    );
  }

  return frontmatter + bodyLines.join("\n");
}

/**
 * Render the per-IDE list of (directory, filename) pairs.
 * Each entry is `{ dir, file }` where `dir` is the agent directory and `file`
 * is the rendered filename. The same filename pattern works for all three IDEs.
 */
export function subAgentTargets(home, cwd) {
  return [
    { id: "claude-code", label: "Claude Code",  dir: join(home, ".claude", "agents") },
    { id: "cursor",      label: "Cursor",       dir: join(cwd,  ".claude", "agents") },  // Cursor also reads this
    { id: "codex",       label: "Codex CLI",    dir: join(home, ".codex",  "agents") },
    { id: "opencode",    label: "opencode",     dir: join(home, ".config", "opencode", "agent") },
  ];
}

export function subAgentFilename(agent, targetId = "claude-code") {
  // opencode loads its sub-agents by the `name:` frontmatter, and the
  // conventional filename in ~/.config/opencode/agent/ matches the agent name
  // exactly (timps_<name>.md). Claude Code / Cursor / Codex use timps-<name>.md.
  if (targetId === "opencode") return `${agent.name}.md`;
  return `timps-${agentFileBase(agent.name)}.md`;
}

/**
 * Idempotently write all sub-agent files to the requested IDE targets.
 * The number written equals AGENTS.length (161 at v2.2.1).
 *
 * @param {{home?: string, cwd?: string, targetIds?: string[], dryRun?: boolean}} opts
 * @returns {{written: string[], skipped: string[], errors: string[]}}
 */
export function writeSubAgents(opts = {}) {
  const home = opts.home || process.env.HOME || process.env.USERPROFILE || "~";
  const cwd  = opts.cwd  || process.cwd();
  const requested = opts.targetIds || ["claude-code", "cursor", "codex", "opencode"];
  const targets = subAgentTargets(home, cwd).filter(t => requested.includes(t.id));

  const written = [];
  const skipped = [];
  const errors  = [];

  for (const target of targets) {
    try {
      mkdirSync(target.dir, { recursive: true });
    } catch (err) {
      errors.push(`${target.id}: mkdir ${target.dir} — ${err.message}`);
      continue;
    }

    for (const agent of AGENTS) {
      const file = join(target.dir, subAgentFilename(agent, target.id));
      const content = renderAgentFile(agent, target.id);

      if (existsSync(file) && readFileSync(file, "utf8") === content) {
        skipped.push(file);
        continue;
      }
      if (opts.dryRun) {
        written.push(file);
        continue;
      }
      try {
        writeFileSync(file, content);
        written.push(file);
      } catch (err) {
        errors.push(`${file}: ${err.message}`);
      }
    }
  }

  return { written, skipped, errors, targets };
}

/**
 * Remove TIMPS sub-agent files from a target directory. Only files that start
 * with `timps-` and end with `.md` are removed — never touch user files.
 */
export function removeSubAgents(opts = {}) {
  const home = opts.home || process.env.HOME || process.env.USERPROFILE || "~";
  const cwd  = opts.cwd  || process.cwd();
  const requested = opts.targetIds || ["claude-code", "cursor", "codex"];
  const targets = subAgentTargets(home, cwd).filter(t => requested.includes(t.id));

  const removed = [];
  const notPresent = [];
  const errors = [];

  for (const target of targets) {
    if (!existsSync(target.dir)) {
      notPresent.push(target.dir);
      continue;
    }
    let entries;
    try {
      entries = readdirSync(target.dir);
    } catch (err) {
      errors.push(`${target.id}: readdir ${target.dir} — ${err.message}`);
      continue;
    }
    for (const name of entries) {
      if (!name.startsWith("timps-") || !name.endsWith(".md")) continue;
      const file = join(target.dir, name);
      if (opts.dryRun) { removed.push(file); continue; }
      try {
        unlinkSync(file);
        removed.push(file);
      } catch (err) {
        errors.push(`${file}: ${err.message}`);
      }
    }
  }

  return { removed, notPresent, errors, targets };
}
