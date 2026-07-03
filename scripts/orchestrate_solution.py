#!/usr/bin/env python3
"""Solution Writer Skill — slim orchestrator.

Pipeline (standard mode, ~7-9 LLM calls):
  1. Input parsing & completeness check  (local)
  2. Research Pack                       (web + knowledge, no LLM)
  3. Solution Blueprint                  (1 LLM call)
  4. Chapter writing                     (5-7 LLM calls, one per chapter)
  5. Merge Markdown                      (local)
  6. Export DOCX                         (local)
  7. Light final review                  (1 LLM call, standard/high_quality only)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Add scripts/ to path so solution_skill package is importable
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from solution_skill.config import (
    CHAPTERS_DIRNAME,
    DEFAULT_ARTIFACT_DIR,
    REPO_ROOT,
    ResearchMode,
    RunMode,
)
from solution_skill.text_utils import normalize_text, strip_trigger_prefix
from solution_skill.run_state import RunState, RunStateStore
from solution_skill.llm_client import OpenAILLM
from solution_skill.intake import (
    assess_completeness,
    generate_clarification,
    maybe_enrich_input,
    parse_input,
)
from solution_skill.research.research_pack_builder import build_research_pack
from solution_skill.research.customer_insight import build_customer_insight
from solution_skill.writing.blueprint import (
    flatten_chapters,
    generate_blueprint,
    review_blueprint,
)
from solution_skill.writing.chapter_writer import write_chapter
from solution_skill.writing.markdown_builder import (
    build_solution_markdown,
    save_solution_markdown,
)
from solution_skill.writing.quality_review import run_quality_review
from solution_skill.export.docx_exporter import export_docx


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Main orchestrator ─────────────────────────────────────────────────


def orchestrate(args: argparse.Namespace) -> int:
    """Main pipeline orchestration."""
    artifacts_dir = Path(args.output_dir).resolve()
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    chapters_dir = artifacts_dir / CHAPTERS_DIRNAME
    chapters_dir.mkdir(exist_ok=True)

    # ── Step 0: Input parsing ──
    input_path = Path(args.input_json).resolve()
    raw_payload = _read_json(input_path)
    request = parse_input(raw_payload, args)
    raw_input = strip_trigger_prefix(request.get("raw_input", ""))
    if not raw_input:
        raise RuntimeError("raw_input is required.")

    # State store
    state_store = RunStateStore(artifacts_dir / "run_state.json")
    state_store.state = RunState(
        status="running",
        current_step="parse_input",
        run_mode=request.get("run_mode", "standard"),
    )
    state_store.save()

    # Save normalized request
    request_path = artifacts_dir / "normalized_request.json"
    _write_json(request_path, request)
    state_store.set_output("normalized_request", request_path)
    log(f"Loaded input ({len(raw_input)} chars). Run mode: {request['run_mode']}, Research: {request['research_mode']}")

    # ── Step 1: Completeness check ──
    assessment = assess_completeness(request)
    if assessment.get("sparse"):
        log("Input is sparse — generating one-round supplement request")
        clarification = generate_clarification(assessment, artifacts_dir)
        state_store.set_output("clarification_questions", artifacts_dir / "clarification_questions.json")
        print(f"补充信息请求（可只答部分，不阻塞）: {artifacts_dir / 'clarification_questions.md'}", flush=True)
        for q in clarification.get("questions", []):
            print(f"  {q}", flush=True)
        # Continue with generation using available input (missing items never block)
        log("Continuing with available input (missing items do not block)...")

    # Optional: enrich input (high_quality only)
    request = maybe_enrich_input(request, assessment, llm=None, state_store=None)

    # ── Step 2: LLM initialization ──
    model_name = args.model or os.getenv("MODEL_NAME", "")
    if not model_name:
        raise RuntimeError("model is required.")
    llm = OpenAILLM(model=model_name, base_url=args.base_url, api_key=args.api_key)

    # ── Step 3: Research Pack (no LLM) ──
    state_store.mark_step("research_pack", "running")
    log("Building research pack...")
    research_pack = build_research_pack(raw_input, request, artifacts_dir, state_store)
    log(f"Research pack: mode={research_pack['mode']}, web={len(research_pack.get('web_items', []))}, knowledge={len(research_pack.get('knowledge_items', []))}")

    # ── Step 3b: Customer background deep-dive (P1, 0-1 LLM call) ──
    log("Deep-diving customer background...")
    insight = build_customer_insight(
        raw_input, request, research_pack, llm, state_store, artifacts_dir,
    )
    if any(insight.values()):
        log(f"Customer insight: positioning={bool(insight.get('strategic_positioning'))}, "
            f"priorities={len(insight.get('annual_priorities', []))}, "
            f"hooks={len(insight.get('alignment_hooks', []))}")
    else:
        log("Customer insight: skipped or empty (continuing).")

    # ── Step 4: Solution Blueprint (1 LLM call) ──
    log("Generating solution blueprint...")
    blueprint = generate_blueprint(raw_input, research_pack, request, llm, state_store, artifacts_dir)
    chapters = flatten_chapters(blueprint)
    log(f"Blueprint: {blueprint.get('title')}, {len(chapters)} chapters, target {blueprint.get('target_length', 12000)} words")

    # Optional: review blueprint (high_quality only)
    if request.get("run_mode") == RunMode.HIGH_QUALITY:
        log("Reviewing blueprint (high_quality mode)...")
        review_blueprint(blueprint, raw_input, llm, state_store, request)

    # ── Step 5: Chapter writing (5-7 LLM calls) ──
    state_store.mark_step("write_chapters", "running")
    chapter_texts = {}
    completed_chapters = []

    for chapter in chapters:
        log(f"Writing chapter {chapter.index}: {chapter.title}")
        body, meta = write_chapter(
            raw_input=raw_input,
            blueprint=blueprint,
            research_pack=research_pack,
            chapter=chapter,
            completed_chapters=completed_chapters,
            llm=llm,
            request=request,
            state_store=state_store,
            chapters_dir=chapters_dir,
        )
        chapter_texts[chapter.id] = body
        completed_chapters.append({
            "id": chapter.id,
            "title": chapter.title,
            "body": body,
        })
        state_store.mark_chapter_complete(chapter.id)
        log(f"  → {meta['word_count']} chars, status={meta['status']}")

    # ── Step 6: Merge Markdown (local) ──
    state_store.mark_step("merge_solution", "running")
    log("Merging solution markdown...")
    solution_md = build_solution_markdown(blueprint, chapters, chapter_texts)
    solution_path = save_solution_markdown(solution_md, artifacts_dir)
    state_store.set_output("solution_md", solution_path)
    log(f"Solution: {solution_path} ({len(solution_md)} chars)")

    # ── Step 7: Export DOCX (local) ──
    state_store.mark_step("export_docx", "running")
    log("Exporting DOCX...")
    try:
        docx_path = export_docx(solution_path, request, blueprint, artifacts_dir)
        state_store.state.docx_status = "completed"
        state_store.set_output("docx", docx_path)
        state_store.save()
        log(f"DOCX: {docx_path}")
    except Exception as exc:
        state_store.warn(f"DOCX export failed: {exc}")
        state_store.state.docx_status = "failed"
        state_store.save()
        docx_path = None
        log(f"DOCX export failed (solution.md still available): {exc}")

    # ── Step 8: Quality review (0-1 LLM call) ──
    run_mode = request.get("run_mode", RunMode.STANDARD)
    if run_mode in (RunMode.STANDARD, RunMode.HIGH_QUALITY):
        state_store.mark_step("quality_review", "running")
        log("Running quality review...")
        try:
            run_quality_review(
                raw_input, blueprint, chapter_texts, chapters,
                llm, request, state_store, artifacts_dir,
            )
            log("Quality review completed.")
        except Exception as exc:
            state_store.warn(f"quality review failed: {exc}")
            state_store.state.quality_status = "failed"
            state_store.save()

    # ── Step 9: Complete ──
    state_store.mark_step("completed", "completed")
    log(f"Pipeline complete. LLM calls: {state_store.state.llm_call_count}")

    # Print output summary
    print(f"\n=== Output Files ===", flush=True)
    print(f"Normalized request: {request_path}", flush=True)
    print(f"Research pack:      {artifacts_dir / 'research_pack.json'}", flush=True)
    print(f"Solution blueprint: {artifacts_dir / 'solution_blueprint.json'}", flush=True)
    print(f"Chapters:           {chapters_dir}", flush=True)
    print(f"Solution markdown:  {solution_path}", flush=True)
    if docx_path:
        print(f"DOCX:               {docx_path}", flush=True)
    if (artifacts_dir / "quality_suggestions.txt").exists():
        print(f"Quality suggestions: {artifacts_dir / 'quality_suggestions.txt'}", flush=True)
    print(f"Run state:          {artifacts_dir / 'run_state.json'}", flush=True)

    return 0


# ── CLI ────────────────────────────────────────────────────────────────


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Solution Writer Skill — streamlined pipeline for high-quality long-form solutions."
    )
    parser.add_argument("--input-json", required=True, help="Path to the input request JSON.")
    parser.add_argument("--output-dir", default=str(DEFAULT_ARTIFACT_DIR), help="Artifacts output directory.")
    parser.add_argument("--model", help="LLM model name.")
    parser.add_argument("--base-url", default=os.getenv("OPENAI_BASE_URL", ""), help="Optional LLM base URL.")
    parser.add_argument("--api-key", default=os.getenv("OPENAI_API_KEY", ""), help="Optional LLM API key.")
    parser.add_argument("--knowledge-root", help="Optional local knowledge directory.")
    parser.add_argument(
        "--research-mode",
        default="hybrid",
        choices=["hybrid", "auto", "knowledge", "web", "off"],
        help="Research source policy. 'auto' maps to 'hybrid'.",
    )
    parser.add_argument("--max-web-results", type=int, default=12, help="Max web search results.")
    parser.add_argument("--review-rewrite-limit", type=int, default=None, help="How many times to rewrite after review.")
    parser.add_argument(
        "--run-mode",
        default="standard",
        choices=["fast", "standard", "high_quality"],
        help="Run mode controlling LLM call budget.",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    try:
        return orchestrate(args)
    except Exception as exc:
        run_state_path = Path(args.output_dir).resolve() / "run_state.json"
        if run_state_path.exists():
            payload = json.loads(run_state_path.read_text(encoding="utf-8-sig"))
            payload["status"] = "failed"
            payload["error"] = str(exc)
            run_state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Workflow failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
