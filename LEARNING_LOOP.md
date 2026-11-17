# TIMPS self-improvement loop

Status: **instrumented, scored, gated**. Promotion requires a measured improvement on
golden cases. Automated promotion is opt-in (`--auto-promote`) and still goes through
that gate.

## What was missing (verified 2026-11-17)

| Gap | Evidence |
|---|---|
| No quality signal | 34 rows in `runs.jsonl`, 0 with a `score`, 4 distinct agents |
| Learned prompts had no consumer | `generated/prompts/` did not exist; 0 code references |
| `min_score` was a dead parameter | learner filtered on `success` only |
| Scorer never persisted | `self_critic_agent` never called `record_run` |
| No schedule | 4 TIMPS launchd jobs, none for learning |

## What is wired now

```
every agent ──_llm()──> ~/.timps/memory/llm_calls.jsonl   (latency, success, chars)
                            │
swarm graph / kernel ──sampled critic (10%, max 3/run)
                            │
self_critic ──score──> ~/.timps/memory/runs.jsonl          (score, verdict, metadata)
                            │
nightly_learning.py ──> generated/reports/nightly_learning_*.md
                            │
                       prompt_store.propose()  →  candidates/<agent>/*.md
                            │
                    eval_harness.gate()  ── golden cases, baseline vs candidate
                            │  (delta >= 0.1 required)
                       prompt_store.promote()  →  overrides/<agent>.md
                            │
                       _llm() resolves override before every LLM call
```

One edit in `src/_helpers.py:_llm` covers 120 of 125 LLM call sites. Critic sampling is
wired into every node of the SDLC graph (`src/graph.py`) and the agent kernel
(`src/agent_kernel.py`), so completed outputs across the swarm produce scores.

## Commands

```bash
# Nightly report (read-only, no LLM spend)
python3 scripts/nightly_learning.py

# Propose candidates (spends tokens; still shadow-only)
python3 scripts/nightly_learning.py --apply-candidates --max-agents 5

# Full loop: propose, gate each candidate, promote only on a pass
python3 scripts/nightly_learning.py --apply-candidates --auto-promote

# Golden cases — required before any promotion
python3 -m src.eval_harness init <agent>
# edit ~/.timps/evals/cases/<agent>.json with expect_contains / expect_not_contains
python3 -m src.eval_harness gate <agent> <candidate.md> --promote --min-delta 0.1

# Inspect / undo
python3 -m src.prompt_store status
python3 -m src.prompt_store resolve <agent> --default "code default"
python3 -m src.prompt_store rollback <agent>
python3 -m src.prompt_store disable <agent>
```

Storage overrides: `TIMPS_PROMPT_DIR`, `TIMPS_MEMORY_DIR`, `TIMPS_EVAL_DIR`.
Sampling controls: `TIMPS_CRITIC_SAMPLE_RATE` (default `0.1`, `0` disables),
`TIMPS_CRITIC_MAX_PER_RUN` (default `3`). All writes are atomic and fail-open.

## Nightly schedule — installed and running

`~/Library/LaunchAgents/ai.timps.nightly-learning.plist` is installed and loaded
(`ai.timps.nightly-learning`, 02:00 daily). It runs with
`--apply-candidates --auto-promote`, so promotion happens only through the golden-case
gate. Verified via `launchctl kickstart` — clean stdout, empty stderr, exit 0.

```bash
launchctl list | grep ai.timps.nightly-learning
tail -f ~/.timps/logs/nightly-learning.log
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/ai.timps.nightly-learning.plist  # disable
```

The plist pins `WorkingDirectory` and `GENERATED_DIR` because launchd starts in `/`,
where relative `generated/` is read-only.

## Golden cases for all agents

`evals/cases/_default.json` provides three read-only smoke cases. Any agent without its
own `evals/cases/<agent>.json` uses those, so the gate covers all 161 agents from day
one. The default cases only reject erroring or empty outputs; add a per-agent file with
real assertions to make the gate meaningful.

Use `python3 -m src.eval_harness init <agent>` to create a per-agent file.

## Deliberate limits

- **No promotion without cases.** `gate()` returns `insufficient_cases` if fewer than 3
  cases resolve (including the default smoke set), and never promotes.
- **No LLM judge in the gate.** Checks are deterministic string assertions, so a
  passing delta means the output changed measurably, not that a model liked it.
- **No fine-tuning.** This is prompt-level learning; adapter training is separate.
- **Sampling is bounded** at 3 critiques per process so scoring cannot dominate cost.

## Verification

`python3 -m pytest -q` — 111 passed. New tests cover prompt versioning/rollback,
telemetry, score persistence, sampled critiquing, eval scoring, and the promotion gate.
