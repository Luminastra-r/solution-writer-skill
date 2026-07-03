"""DOCX exporter.

Reuses the mature standalone renderer in scripts/generate_docx.py (cover page,
TOC placeholder, markdown-table support, markdown-symbol stripping, Chinese
typography) so the pipeline and the CLI stay consistent.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# scripts/ dir (parents[2] = solution_skill/../.. = scripts/)
_SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from solution_skill.text_utils import normalize_text


def _safe_filename(text: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "", normalize_text(text)).strip()


def export_docx(
    solution_path: Path,
    request: Dict[str, Any],
    blueprint: Dict[str, Any],
    artifacts_dir: Path,
) -> Path:
    """Render solution.md into a DOCX under artifacts_dir. Returns the path."""
    from generate_docx import create_solution_docx  # standalone renderer

    content = Path(solution_path).read_text(encoding="utf-8-sig")

    customer_name = (
        normalize_text(request.get("customer_name", ""))
        or normalize_text(request.get("organization_type", ""))
        or "客户单位"
    )
    project_name = (
        normalize_text(blueprint.get("title", ""))
        or normalize_text(request.get("project_name", ""))
        or normalize_text(request.get("solution_topic", ""))
        or "解决方案"
    )

    # Determine output path
    explicit = normalize_text(request.get("output_docx", ""))
    if explicit:
        output_path = Path(explicit)
        if not output_path.is_absolute():
            output_path = artifacts_dir / output_path
    else:
        date_str = datetime.now().strftime("%Y%m%d")
        cust_short = _safe_filename(customer_name)[:6] or "客户"
        proj_short = _safe_filename(project_name)[:12] or "方案"
        output_path = artifacts_dir / f"{date_str}_{cust_short}_{proj_short}_方案.docx"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    input_base_dir = str(Path(solution_path).resolve().parent)

    create_solution_docx(
        content=content,
        output_path=str(output_path),
        project_name=project_name,
        customer_name=customer_name,
        input_base_dir=input_base_dir,
    )
    return output_path
