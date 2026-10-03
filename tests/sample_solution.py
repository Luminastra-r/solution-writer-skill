"""Offline regression fixture; public numbers, proposed business structure."""
import json
from copy import deepcopy

SOURCE_URL = "https://www.miit.gov.cn/jgsj/yxj/xxfb/art/2025/art_82c3dba8d5f442beb4c49b04fbfd0e33.html"
DATASET = {
    "id": "software_2024", "labels": ["软件产品", "信息技术服务", "信息安全", "嵌入式系统软件"],
    "series": [{"name": "2024年收入", "values": [30417, 92190, 2290, 12379]}], "unit": "亿元",
    "source": {"kind": "verified", "reference": "工业和信息化部《2024年软件业运行良好》，2025-01-26；" + SOURCE_URL},
}


def graph(did, kind, chapter, section, title, labels, edges=None):
    return {"id": did, "type": kind, "title": title, "chapter_id": chapter, "section_id": section,
            "purpose": "展示正文中已说明的角色与关系，正文解释职责与实施条件。", "layout": "auto",
            "nodes": [{"id": f"v{i}", "label": label} for i, label in enumerate(labels)],
            "edges": edges if edges is not None else [{"from": f"v{i}", "to": f"v{i+1}"} for i in range(len(labels)-1)]}


def fixture():
    titles = ["行业背景与建设需求", "客户需求与建设边界", "服务体系与系统架构", "实施路径与服务流程", "组织协作与运营保障", "评估方法与后续展望"]
    sections = [("行业结构与服务重点", "建设必要性"), ("需求确认", "边界与假设"),
                ("三层服务体系", "系统接口与数据边界"), ("服务办理流程", "试点与验收"),
                ("协作关系", "运营机制"), ("评估方法", "后续展望")]
    bp = {"title": "园区数字服务运营解决方案", "target_length": 12000,
          "diagnosis": {"strategic_alignment": "以精细化运营支撑园区服务", "core_pain_points": [], "success_criteria": ["流程可追溯"]},
          "writing_guidance": "连贯商务正文，区分设计建议和事实。", "chapters": []}
    bodies = {}
    prose = [
        ["工信部发布的2024年软件业资料显示：软件产品收入30417亿元，信息技术服务收入92190亿元，信息安全收入2290亿元，嵌入式系统软件收入12379亿元。这些数据反映全国软件业结构，不代表园区经营数据，也不作为本方案实施成效。",
         "本方案围绕园区咨询、办理与协作服务设计可追溯的运营机制。建设必要性由真实业务调研进一步确认，行业规模只用于解释业务环境。"],
        ["需求确认由客户与服务团队共同完成，先核验服务对象、办理边界和现有接口。文档不假定客户已有经营成效，业务量、满意度与节约成本均等待客户核实。",
         "现阶段没有客户实际数值，因此本章不绘制经营统计图，也不设置未经确认的改善比例。边界确认形成双方认可的记录，作为试点与验收的依据。"],
        ["三层服务体系包括业务层、能力层和支撑层。业务层提供业务咨询、事项办理；能力层组织流程编排、质量管理；支撑层落实数据治理、制度规范。系统架构由服务入口连接业务平台，再由业务平台调用数据服务。图示解释服务分层与系统连接，正文说明各层职责。",
         "系统接口按最小必要原则开放，数据来源、权限和处理记录均由客户确认。系统对接过程不把行业公开资料混入客户业务数据库。"],
        ["服务办理流程依次为需求受理、业务核验、协同办理、结果反馈。需求受理登记事项和责任角色；业务核验确认办理条件；协同办理记录分工；结果反馈向服务对象说明处理结果。",
         "试点先选择可控事项，记录问题并确认修复结果后再扩展。验收使用完整的办理记录核对责任、过程和交付物，具体指标阈值由双方商定。"],
        ["客户单位负责需求决策，运营团队承接日常协调，技术团队落实技术保障。客户单位向运营团队确认需求，运营团队向技术团队传递配置与接口问题。三方共同维护事项记录，避免口头约定造成责任不清。",
         "运营机制通过定期复盘检查办理阻塞与数据质量，相关记录纳入可追溯台账。角色名称只表示建议分工，人员数量和预算另行协商。"],
        ["评估方法覆盖过程完整性与服务一致性。由于缺乏客户基线，本章不绘制收益趋势图，不宣称本方案已经取得实际成效。",
         "后续展望以试点证据为基础，逐步评估服务扩展与系统集成需求。每项新增能力都应对应明确的业务需求和维护责任。"],
    ]
    tasks = [
        {"id": "industry_bar", "type": "data_chart", "title": "2024年全国软件业分领域收入", "chart": "bar", "dataset_id": "software_2024", "chapter_id": "ch01", "section_id": "ch01_s1", "purpose": "比较公开行业结构，正文说明适用边界"},
        {"id": "service_model", "type": "business_model", "title": "三层服务体系", "chapter_id": "ch03", "section_id": "ch03_s1", "layers": [
            {"title": "业务层", "items": ["业务咨询", "事项办理"]},
            {"title": "能力层", "items": ["流程编排", "质量管理"]},
            {"title": "支撑层", "items": ["数据治理", "制度规范"]}]},
        graph("system_arch", "architecture", "ch03", "ch03_s1", "服务系统架构", ["服务入口", "业务平台", "数据服务"]),
        graph("service_flow", "flowchart", "ch04", "ch04_s1", "服务办理流程", ["需求受理", "业务核验", "协同办理", "结果反馈"]),
        graph("collaboration", "architecture", "ch05", "ch05_s1", "组织协作关系", ["客户单位", "运营团队", "技术团队"]),
    ]
    for i, title in enumerate(titles, 1):
        cid = f"ch{i:02d}"
        secs = [{"id": f"{cid}_s{j}", "title": st, "section_goal": "解释机制与边界", "content_brief": prose[i-1][j-1]} for j, st in enumerate(sections[i-1], 1)]
        bp["chapters"].append({"id": cid, "title": title, "chapter_goal": "说明方案机制", "suggested_words": 2000, "sections": secs,
                               "visualization_goals": [{"type": t["type"], "section_id": t["section_id"], "purpose": t.get("purpose", "解释结构")} for t in tasks if t["chapter_id"] == cid]})
        body = f"## {title}\n\n" + "\n\n".join(f"### {s['title']}\n\n{prose[i-1][j]}" for j, s in enumerate(secs))
        if i == 1:
            body += "\n\n| 领域 | 2024年收入（亿元） |\n| --- | --- |\n" + "\n".join(f"| {label} | {value} |" for label, value in zip(DATASET["labels"], DATASET["series"][0]["values"]))
        if i == 5:
            body += "\n\n| 角色 | 责任 |\n| --- | --- |\n| 客户单位 | 需求确认与验收 |\n| 运营团队 | 事项协调与复盘 |\n| 技术团队 | 接口与配置保障 |"
        body += "\n\n```visualizations\n" + json.dumps({"diagrams": [t for t in tasks if t["chapter_id"] == cid]}, ensure_ascii=False) + "\n```\n"
        bodies[cid] = body
    request = {"raw_input": "为园区设计数字服务运营方案，包含三层服务体系、服务流程、组织协作与公开行业数据。客户未提供实际业务量或成效数据。",
               "customer_name": "方案演示园区", "region": "示例区域", "solution_topic": "数字服务运营", "business_needs": "可追溯的协作与办理流程",
               "visualization_data": [deepcopy(DATASET)], "visualization": {"engine": "svg", "max_diagrams": 8}, "research_mode": "off", "output_docx": "sample_solution.docx"}
    return request, bp, bodies, tasks
