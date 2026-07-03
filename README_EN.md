# Solution Writer Skill

> An AI Agent skill for long-form solution writing — generates 10,000+ word business proposal drafts and DOCX exports in 7-15 LLM calls, with built-in customer insight, knowledge base retrieval, and web research enhancement.

**English** | [中文](./README.md)

---

## Overview

Solution Writer Skill is a standalone AI Agent skill module focused on generating high-quality, long-form business solution documents. It distills the writing expertise of senior pre-sales consultants into a standardized pipeline — from natural language requirements to a 10,000+ word draft and DOCX export, using only 7-15 LLM calls.

### Core Capabilities

- **Input completeness assessment**: Automatically detects missing requirements and guides one-round supplementation (non-blocking)
- **Customer background deep-dive**: 1 LLM call to extract strategic positioning, annual priorities, org structure, and implicit expectations
- **Solution blueprint generation**: Diagnosis + goal-oriented outline + per-section content contracts (1 LLM call)
- **Chapter-by-chapter writing**: 1 LLM call per chapter, fulfilling content briefs and explicitly aligning with customer strategy
- **Merge & export**: Markdown merge + one-click DOCX export
- **Lightweight quality review**: Summary-based solution quality audit (standard / high_quality modes)
- **Research enhancement**: hybrid mode runs web search for customer context + knowledge retrieval for company capabilities (parallel)

## Quick Start

### Prerequisites

- Python 3.8+
- An OpenAI-compatible LLM service (custom base_url supported)

### Installation

```bash
git clone https://github.com/your-username/solution-writer-skill.git
cd solution-writer-skill
pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
# Edit .env and fill in your OPENAI_API_KEY
```

### Usage

1. Prepare a request file:

```json
// artifacts/request.json
{
  "raw_input": "Write a solution: The client is a retail chain enterprise planning to upgrade their store operations system. Current issues include service quality fluctuations, high complaint rates, and uneven store traffic. The goal is to create an actionable annual operations optimization plan focused on customer satisfaction improvement, complaint reduction, staffing optimization, and service standardization.",
  "output_docx": "",
  "knowledge_root": "./knowledge",
  "research_mode": "hybrid",
  "run_mode": "standard"
}
```

> See [`references/request-example.json`](./references/request-example.json) for a complete example

2. Run the orchestrator:

```bash
python scripts/orchestrate_solution.py \
  --input-json ./artifacts/request.json \
  --output-dir ./artifacts \
  --model gpt-4.1
```

To use an OpenAI-compatible gateway:

```bash
python scripts/orchestrate_solution.py \
  --input-json ./artifacts/request.json \
  --output-dir ./artifacts \
  --model your-model \
  --base-url https://your-gateway.example.com/v1
```

### Output Artifacts

| Artifact | Description |
|----------|-------------|
| `artifacts/solution.md` | Merged complete solution in Markdown |
| Final `.docx` | Exported Word document |
| `artifacts/normalized_request.json` | Structured request |
| `artifacts/research_pack.json` | Research context (web + knowledge) |
| `artifacts/solution_blueprint.json` | Solution blueprint (outline + contracts) |
| `artifacts/chapters/chapter_XX.md` | Individual chapter drafts |
| `artifacts/quality_suggestions.txt` | Final quality review suggestions |
| `artifacts/run_state.json` | Run state and LLM call count |

## Run Modes

| Mode | LLM Calls | Use Case |
|------|-----------|----------|
| `fast` | 6-8 | Internal drafts, no review, no customer deep-dive |
| `standard` (default) | 8-10 | Formal proposal draft, with customer deep-dive + review |
| `high_quality` | 11-15 | Bidding/formal submission, with blueprint review + batch review |

> Customer background deep-dive only triggers when a customer is identifiable and context is available (standard / high_quality); otherwise skipped automatically.

## Research Modes

| Mode | Behavior |
|------|----------|
| `hybrid` (default) | Web for customer context/policy + knowledge for products/cases (parallel) |
| `knowledge` | Local knowledge base only |
| `web` | Web search only |
| `off` | No external research |
| `auto` | Legacy alias for `hybrid` |

## Project Structure

```
solution-writer-skill/
├── SKILL.md                          # Skill definition file
├── scripts/
│   ├── orchestrate_solution.py       # Main orchestrator entry point
│   ├── generate_docx.py              # Standalone DOCX export
│   ├── inject_diagrams.py            # Diagram injection (standalone module)
│   ├── render_diagrams.py            # Diagram rendering (standalone module)
│   └── solution_skill/               # Core Python package
│       ├── config.py                 # Constants, enums, dataclasses
│       ├── intake.py                 # Input parsing & completeness assessment
│       ├── llm_client.py             # OpenAI-compatible streaming client
│       ├── run_state.py              # Run state management
│       ├── text_utils.py             # Text processing utilities
│       ├── json_utils.py             # JSON repair utilities
│       ├── research/                 # Research enhancement module
│       │   ├── research_pack_builder.py
│       │   ├── customer_insight.py
│       │   ├── knowledge_index.py    # BM25 knowledge indexing
│       │   └── web_search.py         # DuckDuckGo search
│       ├── writing/                  # Writing module
│       │   ├── blueprint.py          # Solution blueprint generation
│       │   ├── chapter_writer.py     # Chapter-by-chapter writing
│       │   ├── markdown_builder.py   # Markdown merge
│       │   └── quality_review.py     # Quality review
│       └── export/
│           └── docx_exporter.py      # DOCX export
├── references/                       # Reference docs and templates
│   ├── workflow-blueprint.md
│   ├── writing-guidelines.md
│   ├── solution-template.md
│   ├── usage-examples.md
│   ├── request-example.json
│   └── diagram-spec-example.json
├── requirements.txt
├── .env.example
└── LICENSE
```

## Pipeline Overview

```
Input Parsing → Completeness Check → Research Pack → Customer Insight → Blueprint Generation
    → Chapter Writing → Markdown Merge → DOCX Export → Quality Review
```

- **Customer insight first**: Strategic positioning, annual priorities, org/reporting structure, and implicit expectations are structured as the basis for "aligning with strategy, targeting pain points"
- **Goal-oriented outline**: Each leaf section carries a `section_goal` (what to answer) + `content_brief` (mechanisms/roles/metrics to deliver)
- **Contract-based writing**: Body text fulfills content briefs item by item, explicitly explaining how it supports customer strategy, with tactful wording for internal management pain points
- **Graceful degradation**: Auto-extract/repair/fallback for invalid blueprint JSON; auto-retry and reuse completed chapters on LLM stream interruption

## Knowledge Base

Place your knowledge base files (Markdown / TXT) in the `knowledge/` directory. The system automatically indexes them and retrieves relevant snippets using a BM25-like algorithm with category weighting, integrating them into the solution writing.

> An empty knowledge base does not interrupt the pipeline. In `hybrid` / `web` mode, web search is used as a fallback.

## CLI Arguments

```bash
python scripts/orchestrate_solution.py --help
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--input-json` | (required) | Path to input request JSON |
| `--output-dir` | `./artifacts` | Artifacts output directory |
| `--model` | env `MODEL_NAME` | LLM model name |
| `--base-url` | env `OPENAI_BASE_URL` | LLM gateway URL |
| `--api-key` | env `OPENAI_API_KEY` | LLM API key |
| `--knowledge-root` | `./knowledge` | Local knowledge base directory |
| `--research-mode` | `hybrid` | Research mode |
| `--run-mode` | `standard` | Run mode |
| `--max-web-results` | `12` | Max web search results |
| `--review-rewrite-limit` | mode default | Max rewrite attempts after review |

## Tech Stack

- **Python 3.8+** — Pure Python implementation, no framework dependencies
- **openai** — OpenAI-compatible streaming LLM client
- **requests** — DuckDuckGo web search
- **python-docx** — DOCX document export

## Contributing

Issues and Pull Requests are welcome. Please ensure:

1. Code passes `python -m py_compile`
2. New features include a brief description
3. No hardcoded keys or sensitive information

## License

[MIT License](./LICENSE)
