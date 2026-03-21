# AGENTS.md

OpenCode should treat this repository as a deterministic AS400 SDD pipeline, not as a blank Python project.

## Working Rules

- Read `README.md`, `config/pipeline.yaml`, and `core/orchestrator.py` before changing workflow behavior.
- Keep `mock` mode working. It is the default validation path and must stay deterministic.
- Prefer thin wrappers around existing framework code. Do not duplicate orchestration logic outside `core/`.
- Preserve the artifact contract: `analysis.md`, `sdd.md`, `tests.md`, `review.md`, `execution_report.md`, and generated program source in the target output directory.
- Keep example assets under `examples/order_processing/` usable for smoke testing.

## Validation

- For code changes, run `python3 run.py --requirement examples/order_processing/requirement.txt --provider mock`.
- Run `python3 -m pytest tests/ -v`.
- If prompts, templates, or orchestrator stages change, verify the generated artifacts still match the current phase order in the README.

## Editing Guidance

- Use ASCII in code unless an existing file already uses Chinese content, which many project docs and templates do.
- Keep CLI output machine-readable. Prefer JSON for automation-friendly entry points.
- Avoid adding network-dependent tests. The baseline repo must stay runnable offline in `mock` mode.

## OpenCode Workflow

- Load this file as project instructions.
- Use `.opencode/config.json` via `OPENCODE_CONFIG=.opencode/config.json` when running OpenCode in this repository.
- When implementing workflow changes, update the README section named `OpenCode Workflow` so the usage docs stay aligned with the code.
