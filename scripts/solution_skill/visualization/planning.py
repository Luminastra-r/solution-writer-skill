"""Planning contracts shared by blueprint, chapter writing and local validation."""
from __future__ import annotations

import json
import math
import re
from copy import deepcopy

DEFAULTS = {"enabled": True, "max_diagrams": 8, "retries": 1,
            "engine": "auto", "png_width": 1800, "timeout": 60,
            "allow_assumed_data": False, "max_nodes": 18, "max_edges": 30,
            "gradient_mode": "solid", "theme": "auto"}


def options(request):
    result = dict(DEFAULTS)
    config = request.get("visualization") or {}
    if not isinstance(config, dict):
        raise ValueError("visualization must be an object")
    result.update(config)
    for key, low, high in (("max_diagrams", 0, 24), ("retries", 0, 2),
                           ("png_width", 1200, 3600), ("timeout", 5, 120),
                           ("max_nodes", 4, 24), ("max_edges", 4, 48)):
        result[key] = max(low, min(high, int(result[key])))
    if result["engine"] not in ("auto", "mmdc", "svg", "kroki"):
        raise ValueError("unsupported visualization engine")
    if result["gradient_mode"] not in ("controlled", "solid"):
        raise ValueError("gradient_mode must be controlled or solid")
    if result["theme"] not in ("auto", "sage", "tech"):
        raise ValueError("theme must be auto, sage or tech")
    return result


def blueprint_prompt(request):
    try:
        cfg = options(request)
    except (TypeError, ValueError):
        return "可视化配置无效，请只完成正文蓝图。"
    if not cfg["enabled"]:
        return "可视化关闭，不规划绘图。"
    return ("在各章可选字段 visualization_goals 中规划有信息价值的图及其分工："
            "type(flowchart/architecture/data_chart/business_model)、section_id、purpose。"
            f"全篇通常3-6张，上限{cfg['max_diagrams']}张；不凑数，同章可多图。"
            "结构过密时规划概览与独立子图，不得删掉关系。缺乏可靠数值用逻辑图或不绘图。"
            "这只是规划，具体节点/数据须由章节写作者根据实际正文确认。")


def chapter_prompt(request, blueprint, chapter):
    try:
        cfg = options(request)
    except (TypeError, ValueError):
        return ""
    if not cfg["enabled"]:
        return ""
    goals = next((c.get("visualization_goals", []) for c in blueprint.get("chapters", [])
                  if c.get("id") == chapter.id), [])
    return "\n".join([
        "【可视化附加契约】保留正文写作要求，图只表达关系/流程/数据，原因与举措由正文解释。",
        "正文后追加一个 ```visualizations 代码块，只含 JSON {\"diagrams\": [...]}，无需要则空数组。",
        "每图字段 id(ASCII唯一)、type(flowchart/architecture/data_chart/business_model)、title、purpose、",
        "section_id(本章小节ID)、anchor_text(正文中唯一的原句，可选，在该段后插入)。",
        "flowchart/architecture 用 nodes:[{id,label,kind}]、edges:[{from,to,label}]、layout:auto/TB/LR；",
        "business_model 用 layers:[{title,items:[字符串]}]（每层1-4项，2-6层）。",
        "data_chart 用 chart:bar/line/pie/scatter、dataset_id 引用下列已有数据；不允许改写数值。",
        "没有已有数据集时，可以从用户原文或研究片段提取 points:[{label,value,evidence:原文逐字引文}]，",
        "同时注明 source:{kind:user_provided/verified,reference:用户输入或研究条目的link/path}。",
        "每个点的引文必须同时包含标签和原始数值；无法逐点核验则跳过，不得虚构经营成效。",
        "每点选取最短的单指标原文片段，标签之后的第一个数值必须是该点数值，避免混用多个指标。",
        "假设数据默认禁用，逻辑图使用 source:{kind:proposal,reference:本方案设计}。",
        f"单图最多{options(request)['max_nodes']}节点/{options(request)['max_edges']}边；超出必须自行拆图，",
        "分图保留概览与跨图关系说明。避免重复图、装饰图、不强制每章配图。图中文字应出现在本章正文中。",
        f"本章规划：{json.dumps(goals, ensure_ascii=False)}",
        f"已有数据集：{json.dumps(request.get('visualization_data', []), ensure_ascii=False)}",
    ])


def extract_tasks(text):
    """Remove metadata even when malformed; never leak it into published prose."""
    tasks, errors = [], []
    pattern = re.compile(r"```visualizations\s*\n(.*?)(?:```|\Z)", re.S)
    for match in pattern.finditer(text):
        try:
            payload = json.loads(match.group(1).strip())
            values = payload.get("diagrams", [])
            if not isinstance(values, list):
                raise ValueError("diagrams must be a list")
            tasks.extend(values)
        except (ValueError, AttributeError) as exc:
            errors.append(str(exc))
    return pattern.sub("", text).strip(), tasks, errors


def _numbers(series, count):
    if not isinstance(series, list) or not 1 <= len(series) <= 4:
        raise ValueError("expected 1-4 data series")
    for s in series:
        values = s.get("values", [])
        if len(values) != count or any(isinstance(v, bool) or not isinstance(v, (int, float))
                                       or not math.isfinite(v) for v in values):
            raise ValueError("data series must contain finite numbers matching labels")


def validate_task(task, request, research_pack=None):
    d = deepcopy(task)
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", str(d.get("id", ""))):
        raise ValueError("diagram id must be a safe ASCII identifier")
    if not d.get("title") or len(d["title"]) > 120:
        raise ValueError("missing/overlong title")
    if d.get("type") not in ("flowchart", "architecture", "data_chart", "business_model"):
        raise ValueError("unsupported diagram type")
    cfg = options(request)
    if d["type"] == "data_chart":
        # These are derived exclusively from a trusted dataset, never from task flags.
        for key in ("numeric_x", "x_values", "x_label"):
            d.pop(key, None)
        if d.get("dataset_id"):
            datasets = request.get("visualization_data", [])
            dataset = next((s for s in datasets if s.get("id") == d["dataset_id"]), None)
            if dataset is None:
                raise ValueError("unknown dataset; no data will be invented")
            d["labels"] = deepcopy(dataset["labels"])
            d["series"] = deepcopy(dataset["series"])
            d["unit"] = dataset.get("unit", "")
            d["source"] = deepcopy(dataset.get("source", {}))
            if d.get("chart") == "scatter" and dataset.get("x_values") is not None:
                _numbers([{"values": dataset["x_values"]}], len(d["labels"]))
                d["x_values"] = deepcopy(dataset["x_values"])
                d["x_label"] = dataset.get("x_label", "")
                d["numeric_x"] = True
        else:
            source = d.get("source", {})
            kind = source.get("kind")
            trusted = request.get("raw_input", "") if kind == "user_provided" else ""
            if kind == "verified":
                items = (research_pack or {}).get("web_items", []) + (research_pack or {}).get("knowledge_items", [])
                for item in items:
                    reference = item.get("link") or item.get("path")
                    if reference and reference == source.get("reference"):
                        trusted += str(item.get("snippet", ""))
            points = d.get("points", [])
            if not points or not trusted:
                raise ValueError("no reliable numeric evidence")
            for p in points:
                evidence = p.get("evidence", "")
                tokens = re.findall(r"(?<![0-9.])-?\d+(?:,\d{3})*(?:\.\d+)?(?![0-9.])", evidence)
                if (not evidence or evidence not in trusted or not p.get("label")
                        or p["label"] not in evidence or str(p.get("value")) == "True"
                        or p.get("value") not in [float(t.replace(",", "")) for t in tokens]):
                    raise ValueError("point cannot be traced to its source quote")
                tail = evidence.split(p["label"], 1)[1]
                first = re.search(r"-?\d+(?:,\d{3})*(?:\.\d+)?", tail)
                if evidence.count(p["label"]) != 1 or not first or float(first.group().replace(",", "")) != p["value"]:
                    raise ValueError("quoted label/value pairing is ambiguous or inconsistent")
                if d.get("unit") and d["unit"] not in evidence:
                    raise ValueError("chart unit is absent from the original numeric evidence")
            d["labels"] = [p["label"] for p in points]
            d["series"] = [{"name": d.get("unit", "数值"), "values": [p["value"] for p in points]}]
        source = d.get("source", {})
        allowed = {"verified", "user_provided"}
        if cfg["allow_assumed_data"]:
            allowed.add("assumed")
        if source.get("kind") not in allowed or not source.get("reference"):
            raise ValueError("numeric source kind/reference required; assumed data disabled by default")
        labels = d.get("labels", [])
        if not 1 <= len(labels) <= 24 or any(not isinstance(x, str) or not x for x in labels):
            raise ValueError("expected 1-24 non-empty labels")
        _numbers(d.get("series"), len(labels))
        chart = d.get("chart", "bar")
        if chart not in ("bar", "line", "pie", "scatter"):
            raise ValueError("unsupported chart")
        if chart == "pie" and (len(d["series"]) != 1 or len(labels) > 8
                               or any(v < 0 for v in d["series"][0]["values"])
                               or sum(d["series"][0]["values"]) <= 0):
            raise ValueError("pie requires one nonnegative series, positive total, at most 8 slices")
        if chart == "scatter":
            if not d.get("numeric_x"):
                d["x_values"] = list(range(1, len(labels) + 1))
    elif d["type"] == "business_model":
        layers = d.get("layers", [])
        if not 2 <= len(layers) <= 6 or any(not l.get("title") or not 1 <= len(l.get("items", [])) <= 4 for l in layers):
            raise ValueError("model requires 2-6 layers of 1-4 items; split larger models")
        if any(not isinstance(item, str) or not item or len(item) > 120 for l in layers for item in l["items"]):
            raise ValueError("model items must be short non-empty strings")
    else:
        nodes, edges = d.get("nodes", []), d.get("edges", [])
        ids = [str(n.get("id", "")) for n in nodes]
        if not nodes or len(nodes) > cfg["max_nodes"] or len(edges) > cfg["max_edges"]:
            raise ValueError("graph exceeds readable limits; split into overview and subgraphs")
        if len(set(ids)) != len(ids) or any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", i) for i in ids):
            raise ValueError("node ids must be unique ASCII identifiers")
        if any(not n.get("label") or len(str(n["label"])) > 120 for n in nodes):
            raise ValueError("node label missing/too long; move explanation to prose")
        if any(e.get("from") not in ids or e.get("to") not in ids for e in edges):
            raise ValueError("edge references unknown node")
        if d.get("layout", "auto") not in ("auto", "TB", "LR", "BT", "RL"):
            raise ValueError("invalid layout")
        group_ids, members = set(), set()
        for group in d.get("groups", []):
            gid = group.get("id", "")
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", str(gid)) or gid in group_ids or gid in ids:
                raise ValueError("group ids must be unique and separate from node ids")
            if any(n not in ids or n in members for n in group.get("node_ids", [])):
                raise ValueError("group member unknown or repeated")
            group_ids.add(gid)
            members.update(group.get("node_ids", []))
    d.setdefault("source", {"kind": "proposal", "reference": "本方案设计"})
    return d


def split_graph(task, cfg):
    """Partition edges without losing relations. Boundary nodes repeat by identity.

    Returning all parts lets the caller reject the complete group when the figure
    budget cannot accommodate it, rather than inserting a misleading partial graph.
    """
    import shutil
    if not isinstance(task, dict) or task.get("type", "flowchart") not in ("flowchart", "architecture"):
        return [task]
    nodes, edges = task.get("nodes", []), task.get("edges", [])
    if not isinstance(nodes, list) or not isinstance(edges, list) or len(nodes) > 200 or len(edges) > 400:
        return [task]
    nlimit, elimit = cfg["max_nodes"], cfg["max_edges"]
    fallback = cfg["engine"] == "svg" or (cfg["engine"] == "auto" and not (cfg.get("mmdc_bin") or shutil.which("mmdc")))
    if fallback:
        nlimit, elimit = min(nlimit, 10), min(elimit, 12)
    if len(nodes) <= nlimit and len(edges) <= elimit:
        return [task]
    try:
        by_id = {n["id"]: n for n in nodes}
        if len(by_id) != len(nodes) or any(e["from"] not in by_id or e["to"] not in by_id for e in edges):
            return [task]  # Normal validator supplies the useful error.
        chunks, chunk_edges, chunk_ids, covered = [], [], set(), set()
        for edge in edges:
            endpoints = {edge["from"], edge["to"]}
            if chunk_edges and (len(chunk_edges) >= elimit or len(chunk_ids | endpoints) > nlimit):
                chunks.append((chunk_ids, chunk_edges))
                covered |= chunk_ids
                chunk_edges, chunk_ids = [], set()
            chunk_edges.append(edge)
            chunk_ids |= endpoints
        if chunk_ids:
            chunks.append((chunk_ids, chunk_edges))
            covered |= chunk_ids
        remaining = [n["id"] for n in nodes if n["id"] not in covered]
        for i in range(0, len(remaining), nlimit):
            chunks.append((set(remaining[i:i+nlimit]), []))
        result = []
        for i, (ids, part_edges) in enumerate(chunks, 1):
            part = deepcopy(task)
            part.update(id=str(task.get("id", ""))[:54] + f"_p{i:02d}",
                        title=f"{task.get('title', '')}（分图{i}/{len(chunks)}）",
                        nodes=[n for n in nodes if n["id"] in ids], edges=part_edges,
                        split_from=task.get("id"), split_index=i, split_total=len(chunks))
            part["groups"] = [dict(g, node_ids=[nid for nid in g.get("node_ids", []) if nid in ids])
                              for g in part.get("groups", []) if any(nid in ids for nid in g.get("node_ids", []))]
            part["split_note"] = "跨图同名节点表示同一对象；所有原始关系按分图保留。"
            result.append(part)
        return result or [task]
    except (KeyError, TypeError):
        return [task]


def validate_content(task, text):
    """Conservative correspondence check; avoids illustrating unmentioned content."""
    if task["type"] == "data_chart":
        labels = task["labels"]
        numeric_tokens = re.findall(r"(?<![0-9.])-?\d+(?:,\d{3})*(?:\.\d+)?(?![0-9.])", text)
        values = {float(t.replace(",", "")) for t in numeric_tokens}
        plotted = [v for s in task["series"] for v in s["values"]]
        if task.get("numeric_x"):
            plotted.extend(task["x_values"])
        if any(v not in values for v in plotted):
            raise ValueError("chart values are not present in the target chapter prose/table")
    elif task["type"] == "business_model":
        labels = [str(t) for l in task["layers"] for t in [l["title"], *l["items"]]]
    else:
        labels = [n["label"] for n in task["nodes"]]
    if any(label not in text for label in labels):
        raise ValueError("diagram labels are not present in the target chapter prose/table")
