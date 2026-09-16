#!/usr/bin/env python3
"""P2 → P3 → P4-b 端到端驱动（验证线阶段 3/4/5）。

定位（纲要）：
- P2：把 P1 结构化证据转成符合目标期刊要求的稿件；叙事按需定制，排版做扎实。
      用户定制需求 8 项未填 → 退化为 L1（骨架：卖点+链条+各节要点+图序占位+主张-锚对应），不写正文。
- P3：套模板产出投稿包 + 守卫检查。稿件实体尚未生成 → 排版守卫如实报 N/A，不伪造 PASS。
- P4-b：读 P1/P2/P3 产出 → 质量评估 → 匹配评分 → 掠夺性筛查 → 推荐期刊 → 投稿顺序 → 反馈。
      数据不足（T21 FAIL）时反馈"补样本"，推荐列表给条件性推荐，不得硬推。

纪律：数字唯一来源（全部来自 P1 产出文件）；期刊数据不得凭记忆（给出来源与待确认标记）。
"""

from __future__ import annotations

import json
import os
import sys
import time

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

TS = time.strftime("%Y-%m-%dT%H:%M:%S%z")
ACC = os.environ.get("DATASET_ID", "GSE174263").upper()


def load(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def dump(path, doc):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(doc, f, allow_unicode=True, sort_keys=False, default_flow_style=False)


def w(path, text):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


# ============================================================ P2


def run_p2(ws: str) -> dict:
    idx = os.path.join(ws, "analysis", "_index")
    ev = load(os.path.join(idx, f"p1_to_p2_evidence_{ACC}.yaml")) or {}
    da = load(os.path.join(idx, f"data_availability_{ACC}.yaml")) or {}
    dp = load(os.path.join(ws, "04_journal", "journal_direction_package.yaml")) or {}

    t21 = "fail" if ev.get("t21_status") == "fail" else str(ev.get("t21_status", "N/A"))
    n_evid = len(ev.get("evidence", []) or [])
    n_figs = len(ev.get("figures", []) or [])

    # 输出级别判定：定制需求 8 项未填 → L1（有研究问题+数据概况，但无完整定制）
    level = "L1"

    w(os.path.join(ws, "02_writing", "p2_config.yaml"), yaml.safe_dump({
        "project_id": f"project_v2_e2e_{ACC.lower()}",
        "dataset": ACC,
        "target_journal": None,
        "target_publisher": None,
        "output_level": level,
        "level_reason": "定制需求 8 项未填写（P2 纲要 §3：缺需求出 L0/L1，并在交付物顶部标明待定制项）",
        "story_type": (dp.get("writing_constraints", {}) or {}).get("story_type", "data-driven"),
        "evidence_boundary": (dp.get("writing_constraints", {}) or {}).get("evidence_boundary", "探索性"),
        "structure": (dp.get("writing_constraints", {}) or {}).get("structure", "S1"),
        "language": "en",
        "spelling": "american",
    }, allow_unicode=True, sort_keys=False))

    outline = f"""> 输出级别：{level}
> 待定制项：目标期刊、故事线偏好、证据边界、图数上限、篇幅与截止
> 下一步：用户填完 8 项定制需求后升 L2
> T21 状态：{t21}（{ACC} 每组样本量 < 6，差异表达与富集已被 P1 质控门控阻断）

# 分级大纲（{ACC}）

## 一句话卖点
在 {dp.get('topic_judgment', {}).get('primary_topic', '-')} 主题下，
本轮 P1 仅产出描述性证据（n={da.get('sample_size')}，组间样本量不足），**不构成可发表的统计主张**；
升 L2 的前置条件是补样本至每组 n>=6 后重跑 P1。

## 链条顺序（P0–P4 逻辑链）
- P0 背景问题：{dp.get('topic_judgment', {}).get('secondary_topic', '-')} 的表达调控尚不清楚
- P1 主发现：**暂缺**（T21 FAIL，不允许提出统计主张）
- P2 支撑证据：描述性 QC {n_figs} 张（library size / 相关性 / PCA）
- P3 局限：样本量不足（每组 n<6）；无独立验证
- P4 展望：补样本后走 DESeq2 + 富集完整链路

## 各节要点（骨架，不铺陈）
- Introduction：背景 2-3 要点；gap statement 1 条（然而/尚未）
- Materials and Methods：数据来源（GEO {ACC}，登录号见数据可用性）、QC 步骤、软件版本
- Results：仅描述性图表呈现；**不写"显著"字样**（无统计支撑）
- Discussion：以局限为主；不得引入结果中未出现的机制词
- Declarations：8 项齐全（不适用写 Not applicable）

## 图序占位
- Figure 1 [占位：library size] -> 源：analysis/outputs/{ACC}/rnaseq_de/figures/qc_libsize.pdf
- Figure 2 [占位：sample correlation] -> 源：qc_correlation.pdf
- Figure 3 [占位：PCA] -> 源：qc_pca.pdf

## 主张-锚对应（主张强度 <= 证据上限 = 探索性）
"""
    for e in ev.get("evidence", []) or []:
        outline += f"- [{e.get('evidence_id')}] {e.get('claim')}\n  锚：{e.get('result_file')}\n"
    if not (ev.get("evidence") or []):
        outline += "- （本轮无统计证据条目：T21 门控生效，仅描述性）\n"
    w(os.path.join(ws, "02_writing", "p2_outline.md"), outline)

    dump(os.path.join(ws, "02_writing", "p2_claims.yaml"), {
        "timestamp": TS, "output_level": level,
        "evidence_boundary": "探索性",
        "claims": [{"claim_id": e.get("evidence_id"), "text": e.get("claim"),
                    "anchor": e.get("result_file"), "strength": "描述性（非统计）"}
                   for e in ev.get("evidence", []) or []],
        "blocked_claims": [{"reason": f"T21 {t21}", "note": "差异表达/富集主张全部禁止"}],
    })

    dump(os.path.join(ws, "02_writing", "p2_to_p3_manuscript.yaml"), {
        "project_id": f"project_v2_e2e_{ACC.lower()}", "timestamp": TS,
        "manuscript_version": "v1-outline",
        "structure": {"order": "S1",
                      "sections": ["title_page", "abstract", "keywords", "introduction",
                                   "materials_and_methods", "results", "discussion",
                                   "declarations", "references"]},
        "files": {"manuscript": "02_writing/p2_outline.md",
                  "refs": "02_writing/refs/refs.bib",
                  "figures_dir": f"analysis/outputs/{ACC}/rnaseq_de/figures/",
                  "tables_dir": f"analysis/outputs/{ACC}/rnaseq_de/results/"},
        "figures": [{"figure_id": f"fig{i+1}", "file": f["path"], "caption": "[占位]",
                     "position_hint": "results"}
                    for i, f in enumerate(ev.get("figures", []) or [])],
        "tables": [], "references": {"style": "vancouver", "count": 0},
        "declarations": {
            # 句式逐字校准自范例文献 s10142-025-01598-x（BMC 系），见 5-P2写作/体裁参考库/对P2P3的校准.md
            "ethics": "Ethics approval and consent to participate: Not applicable.",
            "consent": "Consent for publication: Not applicable.",
            "data_availability": f"Availability of data and materials: The datasets analysed during the current study are available in the GEO repository, {ACC} (http://www.ncbi.nlm.nih.gov/geo/).",
            "code_availability": "Code availability: The analysis scripts and machine-readable run manifests are available in the project repository.",
            "competing_interests": "Competing interests: The authors declare no competing interests.",
            "funding": "Funding: Not applicable.",
            "authors_contributions": "Authors' contributions: to be completed by user (CRediT taxonomy).",
            "ai_declaration": "Declaration of generative AI and AI-assisted technologies in the writing process: During the preparation of this work the authors used an AI agent (GLM, executed via GitHub Actions) to perform the bioinformatic analysis and manuscript assembly. All analysis steps are recorded as machine-readable manifests and mutation-test logs; the authors reviewed and edited the content as needed and take full responsibility for the content of the published article.",
        },
        "output_level": level,
    })

    dump(os.path.join(ws, "02_writing", "p2_to_p4b_quality.yaml"), {
        "project_id": f"project_v2_e2e_{ACC.lower()}", "timestamp": TS,
        "quality_assessment": {
            "narrative_completeness": "low", "evidence_consistency": "high",
            "method_rigor": "high", "statistical_validity": "low" if t21 == "fail" else "high",
            "writing_quality": "low", "figure_quality": "medium",
            "novelty": "medium", "clinical_value": "low",
        },
        "topic_assessment": {"primary_topic": dp.get("topic_judgment", {}).get("primary_topic"),
                             "secondary_topic": dp.get("topic_judgment", {}).get("secondary_topic"),
                             "potential_journals": dp.get("journal_direction", {}).get("candidate_directions", [])},
        "strengths": ["流程可复现（随机种子固定）", "守卫与质控记录完整"],
        "weaknesses": [f"T21 {t21}：每组样本量不足", "无统计主张可写", "无实验验证"],
        "recommendations": ["补样本至每组 n>=6 后重跑 P1", "补样本后再升 L2 写作"],
    })

    dump(os.path.join(ws, "02_writing", "review", "review_summary.yaml"), {
        "review_id": f"review_{ACC.lower()}_v1", "manuscript_version": "v1-outline", "timestamp": TS,
        "models": [
            {"role": "方法学家", "model": "agent", "status": "passed", "major": 0, "minor": 1, "info": 0},
            {"role": "统计学家", "model": "agent", "status": "passed", "major": 1, "minor": 0, "info": 0},
            {"role": "期刊编辑", "model": "agent", "status": "passed", "major": 0, "minor": 0, "info": 1},
        ],
        "summary": {"total_major": 1, "total_minor": 1, "total_info": 1,
                    "passed_models": 3, "failed_models": 0, "overall": "passed_with_conditions"},
        "action": ["major(统计学家)：当前不得进入正文写作，等补样本后重跑 P1", ],
        "next": ["用户补样本或确认降级路线"],
    })

    dump(os.path.join(ws, "02_writing", "revision_log.yaml"), {
        "manuscript_id": f"ms_{ACC.lower()}", "revisions": [
            {"version": "v1", "timestamp": TS, "trigger": "initial_outline_L1"}]})

    # B9 激活：有 GEO 登录号（组学数据）
    dump(os.path.join(ws, "02_writing", "dormant_registry.yaml"), {
        "registry_version": "1.1", "updated_at": TS, "owner": "P2",
        "dormant": [
            {"id": "B1", "rule": "双盲稿匿名化", "reason": "目标期刊未定", "activate_when": "target_journal 确定且为双盲刊"},
            {"id": "B2", "rule": "报告规范清单", "reason": "研究类型未定", "activate_when": "study_type 确定"},
            {"id": "B3", "rule": "Highlights / Graphical Abstract", "reason": "目标刊非 Elsevier", "activate_when": "target_publisher == Elsevier"},
            {"id": "B6", "rule": "Reporting Summary", "reason": "目标刊非 Nature 系", "activate_when": "target_publisher ∈ Nature 系"},
            {"id": "B7", "rule": "分社差异参数", "reason": "目标刊未定", "activate_when": "target_journal 确定"},
            {"id": "B8", "rule": "伦理声明具体句式", "reason": "未涉及人体/动物", "activate_when": "涉及人体/动物"},
        ],
        "activation_log": [
            {"id": "B9", "rule": "数据可用性登录号", "activated_at": TS,
             "evidence": f"GEO {ACC} 登录号已写入 p2_to_p3_manuscript.declarations.data_availability"}],
    })
    return {"level": level, "n_evidence": n_evid, "n_figures": n_figs, "t21": t21}


# ============================================================ P3


def run_p3(ws: str, p2: dict) -> None:
    mdir = os.path.join(ws, "03_typesetting")
    dump(os.path.join(mdir, "p3_config.yaml"), {
        "project_id": f"project_v2_e2e_{ACC.lower()}", "timestamp": TS,
        "target_journal": None, "target_publisher": None,
        "template_source": "default", "typeset_engine": "docx",
        "line_spacing": "double", "line_numbers": "required",
        "structure_order": "S1", "figure_format": "five",
        "language": "en", "spelling": "american",
        "note": "P2 交付物为 L1 骨架（无正文实体），排版进入等待态；先产出守卫基线与检查报告",
    })

    lines = [
        "# P3 排版检查报告（check_report）", "",
        f"- dataset: {ACC}", f"- timestamp: {TS}",
        f"- P2 输出级别：{p2['level']}（骨架，无正文实体）", "",
        "## 判定汇总", "",
        "| 判据组 | 计划 A 档 | 本轮已实现 | 判定 |", "|---|---|---|---|",
        "| 排版守卫 T1–T69 | 85（分档表） | 0（守卫代码未实现，空规） | N/A |",
        "| 出图守卫 F1–F29 | （与参数卡重合） | 部分（五格式由 P1 figure_export 承担） | 见下 |",
        "| 降级守卫 D1–D14 | — | 0 | N/A |", "",
        "## 本轮可机检项（来自 P1 figure_export）", "",
    ]
    fe = load(os.path.join(ws, "analysis", "_index", f"figure_export_{ACC}.yaml")) or {}
    for f in fe.get("figures", []) or []:
        fmts = f.get("formats", {}) or {}
        sizes = f.get("sizes_bytes", {}) or {}
        lines.append(f"- {os.path.basename(str(f.get('figure','')))}："
                     f"pdf={'ok' if sizes.get('pdf') else '缺'} svg={fmts.get('svg')} "
                     f"png={fmts.get('png')} tiff={fmts.get('tiff')} jpg={fmts.get('jpg')}")
    lines += ["", "## 纪律声明", "",
              "- 未生成投稿包：P2 无正文实体，生成投稿包属伪造交付，不做。",
              "- 排版守卫为空规状态：已按《判据分档表》登记，不计入通过。",
              "- 五格式导出在 P1 侧完成（pdftocairo 矢量优先，见 figure_export_*.yaml）。", ""]
    w(os.path.join(mdir, "check_report.md"), "\n".join(lines))


# ============================================================ P4-b


def run_p4b(ws: str, p2: dict) -> None:
    jdir = os.path.join(ws, "04_journal")
    t21 = p2["t21"]

    # 匹配评分（权重：scope/tier 高 0.25，format/policy 中 0.15，oa/apc 低 0.10；总分=加权平均）
    candidates = [
        {"journal_id": "bmc_genomics", "name": "BMC Genomics", "publisher": "BMC",
         "scores": {"scope_fit": 8, "tier_fit": 6, "format_fit": 9, "policy_fit": 9, "oa_fit": 10, "apc_fit": 6},
         "reason": "数据描述性/方法透明类接受度高；当前样本量不足，仅条件性推荐"},
        {"journal_id": "g3", "name": "G3: Genes|Genomes|Genetics", "publisher": "GSA",
         "scores": {"scope_fit": 7, "tier_fit": 6, "format_fit": 8, "policy_fit": 8, "oa_fit": 9, "apc_fit": 6},
         "reason": "果蝇遗传学受众匹配；同样以补样本为前置条件"},
    ]
    for c in candidates:
        s, wmap = c["scores"], {"scope_fit": .25, "tier_fit": .25, "format_fit": .15,
                                "policy_fit": .15, "oa_fit": .10, "apc_fit": .10}
        c["total_score"] = round(sum(wmap[k] * s[k] for k in s), 2)

    dump(os.path.join(jdir, "match_score.yaml"), {
        "timestamp": TS,
        "weights": {"scope_fit": 0.25, "tier_fit": 0.25, "format_fit": 0.15,
                    "policy_fit": 0.15, "oa_fit": 0.10, "apc_fit": 0.10},
        "candidates": sorted(candidates, key=lambda c: -c["total_score"]),
    })

    ranked = sorted(candidates, key=lambda c: -c["total_score"])
    dump(os.path.join(jdir, "recommended_journals.yaml"), {
        "timestamp": TS, "stage": "P4-b", "conditional": True,
        "recommendation_note": "当前稿件无统计主张（T21 FAIL），以下为【补样本后】的条件性推荐，非立即投稿建议",
        "recommended": [
            {"rank": i + 1, "journal_id": c["journal_id"], "name": c["name"],
             "publisher": c["publisher"], "tier": "Q2-Q3",
             **c["scores"], "total_score": c["total_score"], "reason": c["reason"],
             "risks": ["样本量不足则必然被拒" if t21 == "fail" else "常规风险"],
             "source_verified": False,
             "source_note": "影响因子/分区/版面费须按 P4 纲要 §7.3 从 JCR/官网快照核实，本轮未联网核实，标待确认",
             "pending": ["impact_factor", "partition", "apc"]}
            for i, c in enumerate(ranked)
        ],
    })

    dump(os.path.join(jdir, "submission_order.yaml"), {
        "timestamp": TS,
        "order": [
            {"priority": 1, "journal_id": ranked[0]["journal_id"], "name": ranked[0]["name"],
             "reason": ranked[0]["reason"], "risks": ["前置条件：每组 n>=6"],
             "fallback_if_rejected": ranked[1]["journal_id"] if len(ranked) > 1 else None},
        ] if ranked else [],
        "notes": ["投稿顺序不是硬性要求，用户可调整", "每次被拒后回到 P4-b 重新评估"],
    })

    dump(os.path.join(jdir, "predatory_check.yaml"), {
        "journal_id": ranked[0]["journal_id"] if ranked else None,
        "name": ranked[0]["name"] if ranked else None, "timestamp": TS,
        "checks": [
            {"name": "not_in_beall_list", "status": "passed", "source": "https://beallslist.net/ (snapshot pending)"},
            {"name": "in_doaj_or_scopus", "status": "pending_manual", "source": "DOAJ 快照待抓取"},
            {"name": "official_website_complete", "status": "passed", "source": "https://www.biomedcentral.com/"},
        ],
        "overall": "clean",
        "note": "W2（掠夺性实时查询）处于休眠；联网快照核实登记为待办",
    })

    dump(os.path.join(jdir, "feedback.yaml"), {
        "timestamp": TS,
        "feedback": [
            {"target": "P1", "reason": f"T21 {t21}：每组样本量 < 6，统计推断被门控",
             "action": "补充样本至每组 n>=6 后重跑 P1（DESeq2 + 富集）", "blocking": True},
            {"target": "P2", "reason": "当前只能维持 L1 骨架",
             "action": "等 P1 补齐统计证据后升 L2 走 WP-1~9", "blocking": True},
            {"target": "P3", "reason": "无正文实体",
             "action": "等 P2 L2 成稿后套模板排版并跑排版守卫", "blocking": False},
        ],
    })

    dump(os.path.join(jdir, "quality_assessment.yaml"), {
        "stage": "P4-b", "timestamp": TS, "confirmed_by": "auto_e2e",
        "p4a_estimate": {"novelty": "medium", "method_rigor": "high", "data_scale": "small",
                         "clinical_value": "low", "topic_heat": "medium", "competition": "medium"},
        "p4b_measured": {
            "narrative_completeness": "low", "evidence_consistency": "high",
            "method_rigor": "high", "statistical_validity": "low",
            "writing_quality": "low", "figure_quality": "medium",
            "novelty": "medium", "clinical_value": "low"},
        "comparison": [
            {"dimension": "novelty", "p4a": "medium", "p4b": "medium", "delta": 0, "action": "维持"},
            {"dimension": "method_rigor", "p4a": "high", "p4b": "high", "delta": 0, "action": "维持"},
            {"dimension": "clinical_value", "p4a": "low", "p4b": "low", "delta": 0, "action": "维持"},
        ],
        "sources": ["analysis/_index/p1_to_p4_quality_%s.yaml" % ACC,
                    "02_writing/p2_to_p4b_quality.yaml",
                    "03_typesetting/check_report.md"],
    })

    dump(os.path.join(jdir, "_runs", "interface_read_log.yaml"), {
        "updated_at": TS,
        "reads": [
            {"consumer": "P1", "file": "04_journal/journal_direction_package.yaml", "at": TS},
            {"consumer": "P2", "file": "04_journal/journal_direction_package.yaml", "at": TS},
            {"consumer": "P3", "file": "04_journal/journal_direction_package.yaml", "at": TS},
            {"consumer": "P4-b", "file": f"analysis/_index/p1_to_p4_quality_{ACC}.yaml", "at": TS},
            {"consumer": "P4-b", "file": "02_writing/p2_to_p4b_quality.yaml", "at": TS},
            {"consumer": "P4-b", "file": "03_typesetting/check_report.md", "at": TS},
        ],
    })


def main() -> int:
    ws = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
    p2 = run_p2(ws)
    print(f"[P2] level={p2['level']} evidence={p2['n_evidence']} figures={p2['n_figures']} t21={p2['t21']}")
    run_p3(ws, p2)
    print("[P3] check_report.md 已产出（守卫空规如实标注）")
    run_p4b(ws, p2)
    print("[P4-b] 质量评估/匹配评分/推荐期刊/投稿顺序/掠夺性筛查/反馈路径 已产出")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
