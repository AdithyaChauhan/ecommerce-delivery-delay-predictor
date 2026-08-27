# Project Working Instructions

## Required startup checks

Before making changes:

1. Read `README.md` and `docs/PROJECT_STATUS.md` completely.
2. Inspect the repository structure.
3. Run `git status` and review the five most recent commits when available.
4. Compare documentation with the actual code, data, and tests.
5. Report material contradictions before continuing.

Treat code, data, test results, and command output as stronger evidence than documentation or chat history.

## Change control

- Before editing, explain the proposed changes and list every affected file.
- Wait for the user's explicit approval before editing any file.
- Modify only the scope the user approved.
- Never stage or commit changes unless the user explicitly requests it.
- After editing, stop and show the diff.

## Working rules

- Work on one clearly defined milestone at a time.
- Explain the intended outcome in plain language before introducing unfamiliar concepts.
- Inspect files and data before making claims about them.
- Never invent command output, file counts, row counts, metrics, costs, or deployment status.
- Do not mark work complete unless the relevant verification command succeeds.
- Prefer the smallest change that satisfies the current milestone.
- Do not add dependencies, services, or scope without explaining why they are necessary.
- Clearly label optional work and defer it until the core system works.
- Never commit credentials, raw datasets, local environment files, or generated secrets.
- Review `git diff` and `git status` before every commit.
- Update `docs/PROJECT_STATUS.md` after every verified milestone and at the end of each work session.

## Project constraints

- Keep the project achievable within eight days.
- Make predictions using only information available when an order is approved.
- Do not introduce LLMs, chatbots, streaming systems, or extra microservices.
- Keep per-order SHAP explanations optional until the core system works.
- Develop and validate locally before using paid cloud services.

## Status update rules

When updating `docs/PROJECT_STATUS.md`:

- Record only verified facts.
- Include the exact commands or tests that produced important evidence.
- Distinguish planned work from completed work.
- State blockers explicitly.
- Leave one concrete next action.
