# Strict Sequential Swarm Prompt

Use this prompt in a fresh Codex/Cursor context when you want to generate Spanish grammar chapters strictly one by one.

```text
You are working in:
/Users/antonfilatov/www/my/k3s/english-ai-bot/courses/spanish-grammar

Your task is to generate the Spanish grammar course strictly in chapter order, with hard validation gating.

Mandatory rules:
1. Process chapters strictly by `config/generation-status.json` order.
2. Never start the next chapter until the current chapter is fully correct.
3. A chapter counts as complete only when:
   - `01-outline.json` exists
   - all `02-theory-blocks/*.json` exist
   - `03-questions.json` exists
   - `05-final.json` has been assembled from source files
   - `05-validation.json` exists
   - script validation passes
   - content review finds no unresolved grammar/methodology issues
4. Do not hand-edit `05-final.json`. Fix source files and reassemble.
5. Update `config/generation-status.json` only serially, after the chapter is actually complete.
6. Do not process multiple chapters in parallel.
7. If sub-agents are available, you may use them only inside the current chapter workflow, not across multiple chapters at once.
8. In learner-facing Russian text, do not use English loanwords in Latin script like `spelling`, `default`, or `feedback`; use Russian wording, and put the Spanish term in parentheses if needed.
9. For A0 `orientation_alphabet_sounds` chapters, do not create direct memorization questions of the form "what is the name of letter X"; test reading, recognition, order, and matching instead.
10. In those same chapters, `error_spotting` is allowed only for short fragments such as letters, syllables, and simple forms. Do not use full Spanish sentences that require semantic correction.
11. Do not ping or interrupt an active sub-agent before 20 minutes of runtime unless the user explicitly asks.

Before doing work, read these files:
- `README.md`
- `SWARM_RUNBOOK.md`
- `01-sections.md`
- `config/generation-status.json`
- `prompts/00-generate-full-chapter.md`
- `prompts/01-plan.md`
- `prompts/02-theory-block.md`
- `prompts/03-questions.md`
- `prompts/05-validation.md`
- `02-chapter-schema.json`

Strict workflow:

Step 1. Pick the next pending chapter
- Read `config/generation-status.json`.
- Find the first chapter with `status == "pending"` by the smallest `order`.
- Use its `chapter_id`, `input_file`, and `output_dir`.

Step 2. Generate the chapter
- Use `config/chapter-templates/<chapter_id>-input.json`.
- Generate:
  - `01-outline.json`
  - all `02-theory-blocks/*.json`
  - `03-questions.json`
- Follow the prompt files in `prompts/`.
- The theory must be explained in Russian and the target examples/questions must be in Spanish.
- Learner-facing chapter title should be Spanish; Russian translation belongs in `title_translations.ru`.

Step 3. Assemble and validate
- Run:
  - `bash scripts/assemble-chapter.sh <chapter_id>`
  - `bash scripts/validate-chapter.sh <chapter_id>`
- Inspect the generated `05-final.json` and `05-validation.json`.

Step 4. Deep content review
- Review the chapter for:
  - correct Spanish forms and accents
  - natural neutral Spanish usage
  - correct treatment of Russian-speaker mistakes
  - no English loanwords in learner-facing Russian text
  - no letter-name memorization questions in `orientation_alphabet_sounds`
  - no full-sentence semantic `error_spotting` in `orientation_alphabet_sounds`
  - consistency between theory, examples, and questions
  - no duplicate or weak questions
  - no mismatch between `correct_answer` and explanation
- If needed, fix source files and repeat Step 3 until the chapter is clean.

Step 5. Optional sub-agent use inside one chapter
- If sub-agents are available, use at most:
  - one author worker for chapter generation
  - one reviewer/validator worker after generation
- Do not let them edit shared status files.
- Do not let them work on the next chapter while the current one is unresolved.

Step 6. Mark chapter complete
- Only when the chapter is fully correct:
  - update this chapter in `config/generation-status.json` to `validated`
  - update `summary`
- If the chapter still has unresolved issues, do not advance to the next one.

Step 7. Continue
- Move to the next pending chapter and repeat the same process.
- Continue until:
  - all chapters are completed, or
  - the user interrupts you.

Output requirements after each chapter:
- chapter id
- status
- what was fixed
- validation result
- next chapter id

Non-negotiable rule:
Do not advance to the next chapter until the current chapter is genuinely finished and validated.
```
