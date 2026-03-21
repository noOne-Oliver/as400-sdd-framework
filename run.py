"""Command-line entry point for the AS400 SDD pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from core.config_loader import SDDConfig
from core.orchestrator import Orchestrator


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""

    parser = argparse.ArgumentParser(description="Run the AS400 SDD framework pipeline.")
    parser.add_argument(
        "--requirement",
        required=True,
        help="Path to the requirement text file.",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory where generated artifacts will be written. Defaults to the requirement directory.",
    )
    parser.add_argument(
        "--provider",
        default=None,
        choices=["mock", "ollama", "openai", "openai-compatible"],
        help="LLM provider override. Defaults to sdd_config.yaml.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model override. Defaults to sdd_config.yaml.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Execute the pipeline and print the final result as JSON."""

    args = build_parser().parse_args(argv)
    requirement_path = Path(args.requirement)

    if not requirement_path.exists():
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": f"Requirement file not found: {requirement_path}",
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1

    output_dir = Path(args.output_dir) if args.output_dir else requirement_path.parent

    # Load unified config
    config = SDDConfig()

    # CLI overrides
    provider = args.provider or config.llm_provider()
    model = args.model or config.llm_model()

    orchestrator = Orchestrator(
        config=config,
        provider=provider,
        model=model,
        requirement_path=str(requirement_path),
    )
    result = orchestrator.run(requirement_path, output_dir=output_dir)

    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result.get("status") == "completed":
        return 0
    if result.get("status") == "waiting_human":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
