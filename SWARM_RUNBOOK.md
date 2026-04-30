# Spanish Grammar Swarm Runbook

This document describes how to generate the Spanish grammar course from `01-sections.md` using multiple agents without corrupting shared state.

## Source of Truth

- Human outline: `01-sections.md`
- Generated machine plan: `config/generation-status.json`
- Generated chapter inputs: `config/chapter-templates/*.json`
- Prompt set: `prompts/*.md`
- Reviewer prompt for generated chapters: `prompts/06-review-generated-chapter.md`
- Reviewer agent pass: `prompts/07-reviewer-agent.md`
- Fixer agent pass: `prompts/08-fixer-agent.md`
- Orchestrator loop prompt: `prompts/09-review-fix-loop.md`
- Status dispatcher for generation: `prompts/10-status-dispatcher-agent.md`
- Theory generator pass: `prompts/11-theory-generator-agent.md`
- Questions generator pass: `prompts/12-questions-generator-agent.md`
- Generation reviewer pass: `prompts/13-generation-reviewer-agent.md`
- Generation fixer pass: `prompts/14-generation-fixer-agent.md`
- Orchestrator generation loop: `prompts/15-generate-chapter-swarm-loop.md`
- Final bundle refresh: `../../scripts/generate-grammar-bundle.sh es`

## One-Time Prep

1. Sync the machine-readable plan:
  ```bash
   make sync-plan
  ```
2. Inspect the next pending chapters:
  ```bash
   jq -r '.chapters[] | select(.status == "pending") | [.order, .chapter_id] | @tsv' config/generation-status.json | sed -n '1,20p'
  ```
3. Pick one batch.

## Batch Strategy

Recommended batches:

1. Batch 1: sections 0-5
2. Batch 2: sections 6-10
3. Batch 3: sections 11-17
4. Batch 4: sections 18-21
5. Batch 5: section 22

Within a batch, parallelize by chapter, not by shared files.

## Strict Sequential Mode

If you need hard gating, where chapter N+1 starts only after chapter N is fully validated, use:

- `STRICT_SEQUENTIAL_SWARM_PROMPT.md`

This is stricter than the default batch workflow in this file.
Default workflow here is optimized for throughput and allows batch-oriented chapter processing.
Strict sequential mode is optimized for quality control and intentionally disables cross-chapter parallelism.

## Ownership Rules

- Coordinator owns:
  - `config/generation-status.json`
  - batch planning
  - final status transitions
  - optional bundle refresh
- Worker owns exactly one chapter directory:
  - `chapters/<prefix>.<chapter_id>/`
- Workers must not edit another worker's chapter directory.
- Workers must not edit `config/generation-status.json` in parallel.
- Do not interrupt or ping an active worker before 20 minutes of runtime unless the user explicitly requests it.

## Worker Flow

For one `chapter_id`:

1. Read `config/chapter-templates/<chapter_id>-input.json`.
2. Generate `01-outline.json` using `prompts/01-plan.md`.
3. Generate all `02-theory-blocks/*.json` using `prompts/02-theory-block.md`.
4. Generate `03-questions.json` using `prompts/03-questions.md`.
5. Assemble:
  ```bash
   bash scripts/assemble-chapter.sh <chapter_id>
  ```
6. Validate:
  ```bash
   bash scripts/validate-chapter.sh <chapter_id>
  ```
7. If validation fails, fix source files and repeat steps 5-6.
8. Return a short report to the coordinator.

## Coordinator Flow

1. Select a batch of pending chapters.
2. Assign one worker per chapter.
3. Wait for completed chapter reports.
4. For each completed chapter, inspect:
  - `01-outline.json`
  - `03-questions.json`
  - `05-final.json`
  - `05-validation.json`
5. Update `config/generation-status.json` serially.
6. Recompute summary counts.
7. Optionally rebuild embedded bundle after the batch:
  ```bash
   ./scripts/generate-grammar-bundle.sh es
  ```

## Status Rules

Use these values:

- `pending`
- `in_progress`
- `generated`
- `validated`
- `failed`

In multi-agent mode, you can skip transient `in_progress` updates if they create merge overhead. The important part is that the coordinator writes the final status after reviewing worker output.

## Recommended Prompt for a Chapter Worker

Use this as the assignment template for one worker:

```text
You own exactly one chapter directory for Spanish grammar and must not edit shared status files.

Chapter id: <chapter_id>
Input file: config/chapter-templates/<chapter_id>-input.json
Schema: 02-chapter-schema.json
Prompts:
- prompts/01-plan.md
- prompts/02-theory-block.md
- prompts/03-questions.md
- prompts/05-validation.md

Tasks:
1. Generate 01-outline.json.
2. Generate all theory blocks.
3. Generate 03-questions.json with 60-80 questions.
4. Run bash scripts/assemble-chapter.sh <chapter_id>.
5. Run bash scripts/validate-chapter.sh <chapter_id>.
6. If needed, fix source files and re-run assembly/validation.
7. Return a concise report with created files and validation result.

Do not edit config/generation-status.json.
Do not edit other chapter directories.
Do not write 05-final.json by hand.
```

## Recommended Prompt for the Coordinator

```text
You are coordinating a batch of Spanish grammar chapter generation.

Inputs:
- 01-sections.md
- config/generation-status.json
- SWARM_RUNBOOK.md

Tasks:
1. Pick the next batch of pending chapters.
2. Assign one worker per chapter.
3. After workers finish, review their outputs.
4. Update config/generation-status.json serially.
5. Report validated/generated/failed chapters and the next batch.

Important:
- Only the coordinator edits config/generation-status.json.
- Keep batches small enough to review quickly.
```

## Prefix Note

There is no reserved legacy placeholder chapter anymore. Real generated chapter directories start at `001.*`.

## Hard Content Gates

- In learner-facing Russian text, do not use English loanwords in Latin script like `spelling`, `default`, or `feedback`; use Russian wording, and put the Spanish term in parentheses if needed.
- For A0 `orientation_alphabet_sounds` chapters, do not create direct memorization questions of the form "what is the name of letter X"; test reading, recognition, order, and matching instead.
- In those same chapters, `error_spotting` is allowed only for short fragments such as letters, syllables, and simple forms. Do not use full Spanish sentences that require semantic correction.

## Reviewer Pass for Generated Chapters

Use this when chapters are already generated and you need a cleanup pass before final acceptance.

Recommended flow:

1. Coordinator picks one generated chapter.
2. Spawn one reviewer worker with `prompts/06-review-generated-chapter.md`.
3. Reviewer runs deep checks and, if requested, fixes source files + re-validates.
4. Coordinator inspects reviewer report and only then updates status serially.

Reviewer worker template:

```text
You are a reviewer worker for one generated Spanish grammar chapter.

Read and obey:
- prompts/06-review-generated-chapter.md
- prompts/05-validation.md
- 02-chapter-schema.json

Inputs:
- chapter_id: <chapter_id>
- chapter_dir: chapters/<prefix>.<chapter_id>
- mode: fix_and_validate

Important:
- Do not edit config/generation-status.json.
- Do not edit other chapter directories.
- Do not hand-edit 05-final.json.
```

## Codex UI Swarm Loop (No Bash)

Use this launch phrase in Codex UI:

`Use $spanish-review-fix-swarm for chapter 017`

What it should do:

1. Resolve chapter by order/chapter_id.
2. Spawn reviewer agent using `prompts/07-reviewer-agent.md`.
3. If reviewer returns findings, spawn fixer agent using `prompts/08-fixer-agent.md`.
4. Re-run reviewer and repeat until `validated` with `0 findings`.
5. Keep the loop in one chapter scope; do not touch `config/generation-status.json`.

## Codex UI Chapter Generation Loop (No Bash)

Use this launch phrase in Codex UI:

`Use $spanish-generate-chapter-swarm to generate chapter 018`

What it should do:

1. Spawn status-dispatcher (`prompts/10-status-dispatcher-agent.md`).
2. Spawn theory-generator (`prompts/11-theory-generator-agent.md`).
3. Spawn questions-generator (`prompts/12-questions-generator-agent.md`).
4. Spawn generation-reviewer (`prompts/13-generation-reviewer-agent.md`).
5. If reviewer has findings, spawn generation-fixer (`prompts/14-generation-fixer-agent.md`) and repeat reviewer/fixer until no findings remain.
6. Only after clean reviewer update `config/generation-status.json` for this chapter.

