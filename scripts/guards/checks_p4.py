"""P4 判据实现（A 档 55 条）+ 变异用例。

依据：04.P4/P4纲要.txt §3.5 / §4.5 / §5.5 / §6.4 / §7.5 / §8.4 / §9.3 / §10.3 / §11.4 / §12.8
分档：见 2-骨架与接口/判据分档表.md §5（P4 全部 55 条均为 A 档）
"""

from __future__ import annotations

from typing import Any, Dict, List

from .base import FAIL, NA, PASS, Context, Finding, get_in, missing_fields, register
from .mutation import case

PART = "P4"

DP = "04_journal/journal_direction_package.yaml"
QA = "04_journal/quality_assessment.yaml"
MS = "04_journal/match_score.yaml"
RJ = "04_journal/recommended_journals.yaml"
SO = "04_journal/submission_order.yaml"
PC = "04_journal/predatory_check.yaml"
FB = "04_journal/feedback.yaml"
JD = "04_journal/journal_database.yaml"
IRL = "04_journal/_runs/interface_read_log.yaml"

LEVELS = ("low", "medium", "high")
MATCH_DIMS = ("scope_fit", "tier_fit", "format_fit", "policy_fit", "oa_fit", "apc_fit")
P4B_DIMS = (
    "narrative_completeness",
    "evidence_consistency",
    "method_rigor",
    "statistical_validity",
    "writing_quality",
    "figure_quality",
    "novelty",
    "clinical_value",
)
P4A_DIMS = ("novelty", "method_rigor", "data_scale", "clinical_value", "topic_heat", "competition")


def _present(doc: Any) -> bool:
    return isinstance(doc, dict) and len(doc) > 0


def _fields_check(ctx: Context, check_id: str, rel: str, paths: List[str]) -> Finding:
    doc = ctx.doc(rel)
    if not _present(doc):
        return Finding(check_id, NA, rel, f"{rel} 不存在或无内容")
    miss = missing_fields(doc, paths)
    if miss:
        return Finding(check_id, FAIL, f"{rel}:{miss[0]}", f"缺失 {len(miss)} 项：{', '.join(miss)}")
    return Finding(check_id, PASS, f"{rel}:{paths[0]}", "字段齐全")


def _register_fields(check_id: str, rel: str, paths: List[str], desc: str):
    @register(check_id, PART, "A", f"{rel}:{paths[0]}", desc)
    def _fn(ctx: Context) -> Finding:
        return _fields_check(ctx, check_id, rel, paths)

    return _fn


# ============================================================ A 系列（P4-a 阶段判据）
# 锚点前缀：journal_direction_package.yaml: —— 流程视角

_register_fields(
    "P4.A1.topic_judgment",
    DP,
    [
        "topic_judgment.primary_topic",
        "topic_judgment.secondary_topic",
        "topic_judgment.study_type",
        "topic_judgment.novelty_level",
        "topic_judgment.data_type",
        "topic_judgment.sample_size",
    ],
    "A1 题材初判六字段完整",
)


@register("P4.A2.directions_count", PART, "A", f"{DP}:journal_direction.candidate_directions", "A2 期刊方向 ≥2 个")
def _a2(ctx: Context) -> Finding:
    doc = ctx.doc(DP)
    if not _present(doc):
        return Finding("P4.A2.directions_count", NA, DP, "方向包不存在")
    items = get_in(doc, "journal_direction.candidate_directions", None)
    n = len(items) if isinstance(items, list) else 0
    if n < 2:
        return Finding("P4.A2.directions_count", FAIL, f"{DP}:journal_direction.candidate_directions", f"方向数={n} (<2)")
    return Finding("P4.A2.directions_count", PASS, f"{DP}:journal_direction.candidate_directions", f"方向数={n}")


@register("P4.A3.excluded_reason", PART, "A", f"{DP}:journal_direction.excluded[].reason", "A3 排除项必须带理由")
def _a3(ctx: Context) -> Finding:
    doc = ctx.doc(DP)
    if not _present(doc):
        return Finding("P4.A3.excluded_reason", NA, DP, "方向包不存在")
    items = get_in(doc, "journal_direction.excluded", []) or []
    bad = [i for i, e in enumerate(items) if not (isinstance(e, dict) and str(e.get("reason", "")).strip())]
    if bad:
        return Finding("P4.A3.excluded_reason", FAIL, f"{DP}:journal_direction.excluded[{bad[0]}].reason", f"第 {bad} 项缺理由")
    return Finding("P4.A3.excluded_reason", PASS, f"{DP}:journal_direction.excluded[].reason", f"{len(items)} 项均有理由")


@register("P4.A4.analysis_requirements", PART, "A", f"{DP}:analysis_requirements.required_modules", "A4 分析要求 ≥1 条")
def _a4(ctx: Context) -> Finding:
    doc = ctx.doc(DP)
    if not _present(doc):
        return Finding("P4.A4.analysis_requirements", NA, DP, "方向包不存在")
    req = get_in(doc, "analysis_requirements.required_modules", None)
    n = len(req) if isinstance(req, list) else 0
    if n < 1:
        return Finding("P4.A4.analysis_requirements", FAIL, f"{DP}:analysis_requirements.required_modules", "必做模块 = 0")
    return Finding("P4.A4.analysis_requirements", PASS, f"{DP}:analysis_requirements.required_modules", f"必做模块 {n} 个")


_register_fields(
    "P4.A5.writing_constraints",
    DP,
    [
        "writing_constraints.structure",
        "writing_constraints.abstract_type",
        "writing_constraints.abstract_limit",
        "writing_constraints.keywords_count",
        "writing_constraints.reference_style",
        "writing_constraints.reference_limit",
        "writing_constraints.figure_limit",
        "writing_constraints.table_limit",
        "writing_constraints.language",
        "writing_constraints.audience",
        "writing_constraints.story_type",
        "writing_constraints.evidence_boundary",
    ],
    "A5 写作约束十二字段完整",
)

_register_fields(
    "P4.A6.typesetting_constraints",
    DP,
    [
        "typesetting_constraints.publisher_system",
        "typesetting_constraints.template",
        "typesetting_constraints.line_spacing",
        "typesetting_constraints.line_numbers",
        "typesetting_constraints.figure_width_single",
        "typesetting_constraints.figure_width_double",
        "typesetting_constraints.figure_format",
    ],
    "A6 排版约束七字段完整",
)


@register("P4.A7.user_confirmed", PART, "A", f"{DP}:status", "A7 用户已确认")
def _a7(ctx: Context) -> Finding:
    doc = ctx.doc(DP)
    if not _present(doc):
        return Finding("P4.A7.user_confirmed", NA, DP, "方向包不存在")
    status = get_in(doc, "status", None)
    by = get_in(doc, "confirmed_by", None)
    if status != "confirmed" or not by:
        return Finding("P4.A7.user_confirmed", FAIL, f"{DP}:status", f"status={status}, confirmed_by={by}")
    return Finding("P4.A7.user_confirmed", PASS, f"{DP}:status", f"已由 {by} 确认")


# ============================================================ C 系列（方向包 schema 判据）
# 锚点前缀：journal_direction_package.yaml#schema: —— 文件视角（与 A 系列锚点区分，保证唯一）

_register_fields(
    "P4.C1.package_fields",
    DP,
    [
        "package_id",
        "timestamp",
        "stage",
        "topic_judgment",
        "journal_direction",
        "analysis_requirements",
        "writing_constraints",
        "typesetting_constraints",
        "risks",
        "uncertainties",
        "pending_items",
    ],
    "C1 方向包字段完整",
)


@register("P4.C2.topic_evidence", PART, "A", f"{DP}#schema:topic_judgment", "C2 题材初判有依据（非空）")
def _c2(ctx: Context) -> Finding:
    doc = ctx.doc(DP)
    if not _present(doc):
        return Finding("P4.C2.topic_evidence", NA, DP, "方向包不存在")
    tj = get_in(doc, "topic_judgment", {}) or {}
    empty = [k for k, v in tj.items() if v is None or (isinstance(v, str) and not v.strip())]
    if empty:
        return Finding("P4.C2.topic_evidence", FAIL, f"{DP}#schema:topic_judgment.{empty[0]}", f"空值字段：{empty}")
    return Finding("P4.C2.topic_evidence", PASS, f"{DP}#schema:topic_judgment", "题材初判均有依据")


@register("P4.C3.directions_count", PART, "A", f"{DP}#schema:journal_direction.candidate_directions", "C3 方向 ≥2")
def _c3(ctx: Context) -> Finding:
    f = _a2(ctx)
    f.check_id = "P4.C3.directions_count"
    f.anchor = f.anchor.replace(f"{DP}:", f"{DP}#schema:")
    return f


@register("P4.C4.excluded_reason", PART, "A", f"{DP}#schema:journal_direction.excluded[].reason", "C4 排除项有理由")
def _c4(ctx: Context) -> Finding:
    f = _a3(ctx)
    f.check_id = "P4.C4.excluded_reason"
    f.anchor = f.anchor.replace(f"{DP}:", f"{DP}#schema:")
    return f


@register("P4.C5.analysis_requirements", PART, "A", f"{DP}#schema:analysis_requirements.required_modules", "C5 分析要求 ≥1")
def _c5(ctx: Context) -> Finding:
    f = _a4(ctx)
    f.check_id = "P4.C5.analysis_requirements"
    f.anchor = f.anchor.replace(f"{DP}:", f"{DP}#schema:")
    return f


_register_fields(
    "P4.C6.writing_constraints",
    DP,
    [
        "writing_constraints.structure",
        "writing_constraints.abstract_type",
        "writing_constraints.reference_style",
        "writing_constraints.evidence_boundary",
    ],
    "C6 写作约束关键字段完整",
)

_register_fields(
    "P4.C7.typesetting_constraints",
    DP,
    [
        "typesetting_constraints.publisher_system",
        "typesetting_constraints.line_spacing",
        "typesetting_constraints.figure_format",
    ],
    "C7 排版约束关键字段完整",
)


@register("P4.C8.user_confirmed", PART, "A", f"{DP}#schema:confirmed_by", "C8 用户已确认")
def _c8(ctx: Context) -> Finding:
    f = _a7(ctx)
    f.check_id = "P4.C8.user_confirmed"
    f.anchor = f"{DP}#schema:confirmed_by"
    return f


@register("P4.C9.pending_items", PART, "A", f"{DP}#schema:pending_items", "C9 待定制项已列")
def _c9(ctx: Context) -> Finding:
    doc = ctx.doc(DP)
    if not _present(doc):
        return Finding("P4.C9.pending_items", NA, DP, "方向包不存在")
    if "pending_items" not in doc:
        return Finding("P4.C9.pending_items", FAIL, f"{DP}#schema:pending_items", "缺 pending_items 键")
    return Finding("P4.C9.pending_items", PASS, f"{DP}#schema:pending_items", "待定制项已列")


# ============================================================ B 系列（P4-b 阶段判据）

_register_fields("P4.B1.quality_fields", QA, [f"p4b_measured.{d}" for d in P4B_DIMS], "B1 质量评估八维完整")

_register_fields("P4.B2.match_fields", MS, ["weights"] + [f"candidates"], "B2 匹配评分完整")


@register("P4.B3.recommended_count", PART, "A", f"{RJ}:recommended", "B3 推荐期刊 1–3 个")
def _b3(ctx: Context) -> Finding:
    doc = ctx.doc(RJ)
    if not _present(doc):
        return Finding("P4.B3.recommended_count", NA, RJ, "推荐列表不存在")
    items = get_in(doc, "recommended", None)
    n = len(items) if isinstance(items, list) else 0
    if n < 1 or n > 3:
        return Finding("P4.B3.recommended_count", FAIL, f"{RJ}:recommended", f"推荐数={n}（应为 1–3）")
    return Finding("P4.B3.recommended_count", PASS, f"{RJ}:recommended", f"推荐数={n}")


@register("P4.B4.order_fields", PART, "A", f"{SO}:order[]", "B4 投稿顺序完整")
def _b4(ctx: Context) -> Finding:
    doc = ctx.doc(SO)
    if not _present(doc):
        return Finding("P4.B4.order_fields", NA, SO, "投稿顺序不存在")
    items = get_in(doc, "order", None)
    if not isinstance(items, list) or not items:
        return Finding("P4.B4.order_fields", FAIL, f"{SO}:order", "order 为空")
    need = ("priority", "journal_id", "name", "reason", "risks", "fallback_if_rejected")
    for i, it in enumerate(items):
        miss = [k for k in need if k not in it]
        if miss:
            return Finding("P4.B4.order_fields", FAIL, f"{SO}:order[{i}]", f"缺字段：{miss}")
    return Finding("P4.B4.order_fields", PASS, f"{SO}:order[]", f"{len(items)} 项字段齐全")


@register("P4.B5.predatory_executed", PART, "A", f"{PC}:overall", "B5 掠夺性筛查已执行")
def _b5(ctx: Context) -> Finding:
    doc = ctx.doc(PC)
    if not _present(doc):
        return Finding("P4.B5.predatory_executed", NA, PC, "筛查记录不存在")
    overall = get_in(doc, "overall", None)
    if overall not in ("clean", "suspicious", "predatory"):
        return Finding("P4.B5.predatory_executed", FAIL, f"{PC}:overall", f"overall={overall} 非法或未执行")
    return Finding("P4.B5.predatory_executed", PASS, f"{PC}:overall", f"overall={overall}")


@register("P4.B6.feedback_present", PART, "A", f"{FB}:feedback", "B6 反馈路径已给出")
def _b6(ctx: Context) -> Finding:
    doc = ctx.doc(FB)
    if not _present(doc):
        return Finding("P4.B6.feedback_present", NA, FB, "反馈文件不存在")
    items = get_in(doc, "feedback", None)
    if not isinstance(items, list) or not items:
        return Finding("P4.B6.feedback_present", FAIL, f"{FB}:feedback", "feedback 为空")
    for i, it in enumerate(items):
        if not isinstance(it, dict) or not it.get("target") or not it.get("action"):
            return Finding("P4.B6.feedback_present", FAIL, f"{FB}:feedback[{i}]", "缺 target 或 action")
    return Finding("P4.B6.feedback_present", PASS, f"{FB}:feedback", f"{len(items)} 条反馈")


@register("P4.B7.user_confirmed", PART, "A", f"{QA}:confirmed_by", "B7 用户已确认")
def _b7(ctx: Context) -> Finding:
    doc = ctx.doc(QA)
    if not _present(doc):
        return Finding("P4.B7.user_confirmed", NA, QA, "质量评估不存在")
    by = get_in(doc, "confirmed_by", None)
    if not by:
        return Finding("P4.B7.user_confirmed", FAIL, f"{QA}:confirmed_by", "未确认")
    return Finding("P4.B7.user_confirmed", PASS, f"{QA}:confirmed_by", f"已由 {by} 确认")


# ============================================================ E 系列（评价维度）

_register_fields("P4.E1.dimensions", QA, [f"p4a_estimate.{d}" for d in P4A_DIMS], "E1 评价维度完整（P4-a 六维）")


@register("P4.E2.enum_valid", PART, "A", f"{QA}:p4b_measured.*", "E2 取值合法（low/medium/high）")
def _e2(ctx: Context) -> Finding:
    doc = ctx.doc(QA)
    if not _present(doc):
        return Finding("P4.E2.enum_valid", NA, QA, "质量评估不存在")
    # 只查 P4-b 实测八维：其取值域为 low/medium/high。
    # P4-a 六维含 topic_heat(cold/warm/hot)、data_scale(small/medium/large)，取值域不同，由 E1 管字段完整。
    b = get_in(doc, "p4b_measured", {}) or {}
    bad = [k for k, v in b.items() if v not in LEVELS]
    if bad:
        return Finding("P4.E2.enum_valid", FAIL, f"{QA}:p4b_measured.{bad[0]}", f"非法取值：{bad}")
    return Finding("P4.E2.enum_valid", PASS, f"{QA}:p4b_measured", "取值合法")


@register("P4.E3.compare_a_b", PART, "A", f"{QA}:comparison", "E3 P4-b 必须与 P4-a 对比")
def _e3(ctx: Context) -> Finding:
    doc = ctx.doc(QA)
    if not _present(doc):
        return Finding("P4.E3.compare_a_b", NA, QA, "质量评估不存在")
    comp = get_in(doc, "comparison", None)
    if not isinstance(comp, list) or not comp:
        return Finding("P4.E3.compare_a_b", FAIL, f"{QA}:comparison", "未做 P4-a / P4-b 对比")
    shared = ("novelty", "method_rigor", "clinical_value")
    got = {c.get("dimension") for c in comp if isinstance(c, dict)}
    miss = [d for d in shared if d not in got]
    if miss:
        return Finding("P4.E3.compare_a_b", FAIL, f"{QA}:comparison", f"缺对比维度：{miss}")
    for i, c in enumerate(comp):
        if "action" not in c:
            return Finding("P4.E3.compare_a_b", FAIL, f"{QA}:comparison[{i}].action", "对比未给处置动作")
    return Finding("P4.E3.compare_a_b", PASS, f"{QA}:comparison", f"{len(comp)} 个维度已对比")


# ============================================================ S 系列（期刊数据源防幻觉）

_KEY_FIELDS = ("impact_factor", "partition", "apc")


@register("P4.S1.has_source", PART, "A", f"{JD}:journals[].impact_factor.source", "S1 每条期刊数据带来源")
def _s1(ctx: Context) -> Finding:
    doc = ctx.doc(JD)
    if not _present(doc):
        return Finding("P4.S1.has_source", NA, JD, "期刊数据库不存在")
    for i, j in enumerate(get_in(doc, "journals", []) or []):
        for k in _KEY_FIELDS:
            blk = get_in(j, k, {}) or {}
            if not str(blk.get("source", "")).strip():
                return Finding("P4.S1.has_source", FAIL, f"{JD}:journals[{i}].{k}.source", "缺来源")
    return Finding("P4.S1.has_source", PASS, f"{JD}:journals[].source", "关键数据均有来源")


@register("P4.S2.has_verified_at", PART, "A", f"{JD}:journals[].impact_factor.verified_at", "S2 每条期刊数据带时间")
def _s2(ctx: Context) -> Finding:
    doc = ctx.doc(JD)
    if not _present(doc):
        return Finding("P4.S2.has_verified_at", NA, JD, "期刊数据库不存在")
    for i, j in enumerate(get_in(doc, "journals", []) or []):
        for k in _KEY_FIELDS:
            blk = get_in(j, k, {}) or {}
            if not blk.get("verified_at"):
                return Finding("P4.S2.has_verified_at", FAIL, f"{JD}:journals[{i}].{k}.verified_at", "缺时间戳")
    return Finding("P4.S2.has_verified_at", PASS, f"{JD}:journals[].verified_at", "关键数据均有时间")


@register("P4.S3.manual_confirmed", PART, "A", f"{JD}:journals[].human_confirmed", "S3 关键数据已人工确认")
def _s3(ctx: Context) -> Finding:
    doc = ctx.doc(JD)
    if not _present(doc):
        return Finding("P4.S3.manual_confirmed", NA, JD, "期刊数据库不存在")
    for i, j in enumerate(get_in(doc, "journals", []) or []):
        for k in ("impact_factor", "partition", "apc"):
            blk = get_in(j, k, {}) or {}
            if blk.get("human_confirmed") is not True:
                return Finding("P4.S3.manual_confirmed", FAIL, f"{JD}:journals[{i}].{k}.human_confirmed", "未人工确认")
    return Finding("P4.S3.manual_confirmed", PASS, f"{JD}:journals[].human_confirmed", "关键数据已人工确认")


@register("P4.S4.pending_marker", PART, "A", f"{JD}:journals[].pending", "S4 不确定项必须标待确认，不得猜")
def _s4(ctx: Context) -> Finding:
    doc = ctx.doc(JD)
    if not _present(doc):
        return Finding("P4.S4.pending_marker", NA, JD, "期刊数据库不存在")
    for i, j in enumerate(get_in(doc, "journals", []) or []):
        pending = set(j.get("pending", []) or [])
        for k in _KEY_FIELDS:
            blk = get_in(j, k, {}) or {}
            v = blk.get("value", "__MISSING__")
            if v is None and k not in pending:
                return Finding("P4.S4.pending_marker", FAIL, f"{JD}:journals[{i}].{k}.value", "值为空但未登记 pending")
            if isinstance(v, str) and "待确认" in v and k not in pending:
                return Finding("P4.S4.pending_marker", FAIL, f"{JD}:journals[{i}].{k}.value", "标了待确认但未进 pending")
    return Finding("P4.S4.pending_marker", PASS, f"{JD}:journals[].pending", "不确定项均已登记")


@register("P4.S5.predatory_executed", PART, "A", f"{JD}:journals[].predatory_check", "S5 掠夺性筛查已执行")
def _s5(ctx: Context) -> Finding:
    doc = ctx.doc(JD)
    if not _present(doc):
        return Finding("P4.S5.predatory_executed", NA, JD, "期刊数据库不存在")
    for i, j in enumerate(get_in(doc, "journals", []) or []):
        pc = get_in(j, "predatory_check", None)
        if not isinstance(pc, dict) or not pc.get("status"):
            return Finding("P4.S5.predatory_executed", FAIL, f"{JD}:journals[{i}].predatory_check", "未做掠夺性筛查")
    return Finding("P4.S5.predatory_executed", PASS, f"{JD}:journals[].predatory_check", "均已筛查")


# ============================================================ M 系列（匹配算法）

_WEIGHTS = {
    "scope_fit": 0.25,
    "tier_fit": 0.25,
    "format_fit": 0.15,
    "policy_fit": 0.15,
    "oa_fit": 0.10,
    "apc_fit": 0.10,
}
_TOL = 0.30  # 容差覆盖示例数据的四舍五入


@register("P4.M1.has_scores", PART, "A", f"{MS}:candidates[].scores", "M1 每个维度有评分")
def _m1(ctx: Context) -> Finding:
    doc = ctx.doc(MS)
    if not _present(doc):
        return Finding("P4.M1.has_scores", NA, MS, "匹配评分不存在")
    for i, c in enumerate(get_in(doc, "candidates", []) or []):
        sc = get_in(c, "scores", {}) or {}
        miss = [d for d in MATCH_DIMS if not isinstance(sc.get(d), (int, float))]
        if miss:
            return Finding("P4.M1.has_scores", FAIL, f"{MS}:candidates[{i}].scores", f"缺评分：{miss}")
        oor = [d for d in MATCH_DIMS if not (0 <= float(sc[d]) <= 10)]
        if oor:
            return Finding("P4.M1.has_scores", FAIL, f"{MS}:candidates[{i}].scores", f"评分越界：{oor}")
    return Finding("P4.M1.has_scores", PASS, f"{MS}:candidates[].scores", "六维评分齐全且在 0–10")


@register("P4.M2.has_reason", PART, "A", f"{MS}:candidates[].reason", "M2 评分有依据")
def _m2(ctx: Context) -> Finding:
    doc = ctx.doc(MS)
    if not _present(doc):
        return Finding("P4.M2.has_reason", NA, MS, "匹配评分不存在")
    for i, c in enumerate(get_in(doc, "candidates", []) or []):
        if not str(c.get("reason", "")).strip():
            return Finding("P4.M2.has_reason", FAIL, f"{MS}:candidates[{i}].reason", "缺评分依据")
    return Finding("P4.M2.has_reason", PASS, f"{MS}:candidates[].reason", "均有依据")


@register("P4.M3.total_score_math", PART, "A", f"{MS}:candidates[].total_score", "M3 总分计算正确")
def _m3(ctx: Context) -> Finding:
    doc = ctx.doc(MS)
    if not _present(doc):
        return Finding("P4.M3.total_score_math", NA, MS, "匹配评分不存在")
    w = get_in(doc, "weights", _WEIGHTS) or _WEIGHTS
    for i, c in enumerate(get_in(doc, "candidates", []) or []):
        sc = get_in(c, "scores", {}) or {}
        if any(not isinstance(sc.get(d), (int, float)) for d in MATCH_DIMS):
            continue
        expect = sum(float(w.get(d, 0)) * float(sc[d]) for d in MATCH_DIMS)
        got = c.get("total_score")
        if not isinstance(got, (int, float)) or abs(float(got) - expect) > _TOL:
            return Finding(
                "P4.M3.total_score_math",
                FAIL,
                f"{MS}:candidates[{i}].total_score",
                f"声明 {got}，加权计算 {expect:.2f}（容差 ±{_TOL}）",
            )
    return Finding("P4.M3.total_score_math", PASS, f"{MS}:candidates[].total_score", "总分与加权平均一致")


@register("P4.M4.sorted", PART, "A", f"{MS}:candidates[].total_score#order", "M4 已按总分降序")
def _m4(ctx: Context) -> Finding:
    doc = ctx.doc(MS)
    if not _present(doc):
        return Finding("P4.M4.sorted", NA, MS, "匹配评分不存在")
    scores = [c.get("total_score") for c in get_in(doc, "candidates", []) or []]
    if any(not isinstance(s, (int, float)) for s in scores):
        return Finding("P4.M4.sorted", FAIL, f"{MS}:candidates[].total_score", "存在非数值总分")
    if scores != sorted(scores, reverse=True):
        return Finding("P4.M4.sorted", FAIL, f"{MS}:candidates[].total_score#order", f"未降序：{scores}")
    return Finding("P4.M4.sorted", PASS, f"{MS}:candidates[].total_score#order", f"已降序：{scores}")


# ============================================================ J 系列（推荐期刊）

for _i, (_cid, _key, _desc) in enumerate(
    [
        ("P4.J2.has_scores", "scope_fit", "J2 每个附评分"),
        ("P4.J3.has_reason", "reason", "J3 每个附理由"),
        ("P4.J4.has_risks", "risks", "J4 每个附风险"),
        ("P4.J5.has_source_verified", "source_verified", "J5 每个附来源（source_verified）"),
    ]
):
    def _mk(_cid=_cid, _key=_key, _desc=_desc):
        @register(_cid, PART, "A", f"{RJ}:recommended[].{_key}", _desc)
        def _fn(ctx: Context) -> Finding:
            doc = ctx.doc(RJ)
            if not _present(doc):
                return Finding(_cid, NA, RJ, "推荐列表不存在")
            items = get_in(doc, "recommended", []) or []
            if not items:
                return Finding(_cid, FAIL, f"{RJ}:recommended", "推荐列表为空")
            for i, it in enumerate(items):
                v = it.get(_key)
                if _key == "source_verified":
                    if v is True:
                        continue  # 已核实
                    # 元原则 5：不确定时标"待确认"，不得猜。允许显式登记待核实（pending/source_note），
                    # 两条路都满足可追溯性；既未核实又未登记才是违规。
                    if it.get("pending") or str(it.get("source_note", "")).strip():
                        continue
                    return Finding(_cid, FAIL, f"{RJ}:recommended[{i}].{_key}",
                                   "未核实来源且无待核实登记（不得凭记忆填期刊数据）")
                elif _key == "risks":
                    if not isinstance(v, list):
                        return Finding(_cid, FAIL, f"{RJ}:recommended[{i}].{_key}", "risks 必须是列表（可为空）")
                elif v is None or (isinstance(v, str) and not v.strip()):
                    return Finding(_cid, FAIL, f"{RJ}:recommended[{i}].{_key}", f"{_key} 为空")
            return Finding(_cid, PASS, f"{RJ}:recommended[].{_key}", _desc + "：通过")

        return _fn

    _mk()


@register("P4.J1.recommended_count", PART, "A", f"{RJ}:recommended#count", "J1 推荐期刊 1–3 个")
def _j1(ctx: Context) -> Finding:
    f = _b3(ctx)
    f.check_id = "P4.J1.recommended_count"
    f.anchor = f"{RJ}:recommended#count"
    return f


# ============================================================ O 系列（投稿顺序）

for _cid, _key, _desc in [
    ("P4.O2.has_fallback", "fallback_if_rejected", "O2 每个有 fallback"),
    ("P4.O3.has_reason", "reason", "O3 每个有理由"),
    ("P4.O4.has_risks", "risks", "O4 每个有风险"),
]:
    def _mk(_cid=_cid, _key=_key, _desc=_desc):
        @register(_cid, PART, "A", f"{SO}:order[].{_key}", _desc)
        def _fn(ctx: Context) -> Finding:
            doc = ctx.doc(SO)
            if not _present(doc):
                return Finding(_cid, NA, SO, "投稿顺序不存在")
            items = get_in(doc, "order", []) or []
            if not items:
                return Finding(_cid, FAIL, f"{SO}:order", "order 为空")
            for i, it in enumerate(items):
                if _key not in it:
                    return Finding(_cid, FAIL, f"{SO}:order[{i}].{_key}", f"缺 {_key}")
                if _key == "risks" and not isinstance(it[_key], list):
                    return Finding(_cid, FAIL, f"{SO}:order[{i}].{_key}", "risks 必须是列表")
                if _key == "reason" and not str(it[_key]).strip():
                    return Finding(_cid, FAIL, f"{SO}:order[{i}].{_key}", "理由为空")
            return Finding(_cid, PASS, f"{SO}:order[].{_key}", _desc + "：通过")

        return _fn

    _mk()


@register("P4.O1.order_present", PART, "A", f"{SO}:order", "O1 投稿顺序已给出")
def _o1(ctx: Context) -> Finding:
    doc = ctx.doc(SO)
    if not _present(doc):
        return Finding("P4.O1.order_present", NA, SO, "投稿顺序不存在")
    items = get_in(doc, "order", None)
    if not isinstance(items, list) or not items:
        return Finding("P4.O1.order_present", FAIL, f"{SO}:order", "未给出投稿顺序")
    return Finding("P4.O1.order_present", PASS, f"{SO}:order", f"{len(items)} 级顺序")


# ============================================================ P 系列（掠夺性筛查）

@register("P4.P1.executed", PART, "A", f"{PC}:checks", "P1 筛查已执行")
def _p1(ctx: Context) -> Finding:
    doc = ctx.doc(PC)
    if not _present(doc):
        return Finding("P4.P1.executed", NA, PC, "筛查记录不存在")
    checks = get_in(doc, "checks", None)
    if not isinstance(checks, list) or not checks:
        return Finding("P4.P1.executed", FAIL, f"{PC}:checks", "筛查项为空")
    return Finding("P4.P1.executed", PASS, f"{PC}:checks", f"{len(checks)} 项已执行")


@register("P4.P2.has_source", PART, "A", f"{PC}:checks[].source", "P2 每项有来源")
def _p2(ctx: Context) -> Finding:
    doc = ctx.doc(PC)
    if not _present(doc):
        return Finding("P4.P2.has_source", NA, PC, "筛查记录不存在")
    for i, c in enumerate(get_in(doc, "checks", []) or []):
        if not str(c.get("source", "")).strip():
            return Finding("P4.P2.has_source", FAIL, f"{PC}:checks[{i}].source", "缺来源")
    return Finding("P4.P2.has_source", PASS, f"{PC}:checks[].source", "均有来源")


@register("P4.P3.overall_valid", PART, "A", f"{PC}:overall#enum", "P3 overall 明确")
def _p3(ctx: Context) -> Finding:
    f = _b5(ctx)
    f.check_id = "P4.P3.overall_valid"
    f.anchor = f"{PC}:overall#enum"
    return f


@register("P4.P4.excluded_if_flagged", PART, "A", f"{PC}:overall#exclusion", "P4 命中掠夺性列表的期刊必须被排除")
def _p4(ctx: Context) -> Finding:
    pc = ctx.doc(PC)
    if not _present(pc):
        return Finding("P4.P4.excluded_if_flagged", NA, PC, "筛查记录不存在")
    flagged = get_in(pc, "journal_id", None) if get_in(pc, "overall") in ("suspicious", "predatory") else None
    if not flagged:
        return Finding("P4.P4.excluded_if_flagged", PASS, f"{PC}:overall#exclusion", "无命中，无需排除")
    rec = ctx.doc(RJ)
    ids = [r.get("journal_id") for r in get_in(rec, "recommended", []) or []] if _present(rec) else []
    if flagged in ids:
        return Finding("P4.P4.excluded_if_flagged", FAIL, f"{RJ}:recommended", f"{flagged} 命中掠夺性筛查但仍被推荐")
    return Finding("P4.P4.excluded_if_flagged", PASS, f"{PC}:overall#exclusion", f"{flagged} 已排除")


# ============================================================ I 系列（接口闭环）

def _read_log_has(ctx: Context, consumer: str, target: str) -> bool:
    log = ctx.doc(IRL)
    if not _present(log):
        return False
    for r in get_in(log, "reads", []) or []:
        if r.get("consumer") == consumer and r.get("file") == target:
            return True
    return False


for _cid, _consumer, _desc in [
    ("P4.I1.p1_read_p4a", "P1", "I1 P4-a 输出被 P1 读取"),
    ("P4.I2.p2_read_p4a", "P2", "I2 P4-a 输出被 P2 读取"),
    ("P4.I3.p3_read_p4a", "P3", "I3 P4-a 输出被 P3 读取"),
]:
    def _mk(_cid=_cid, _consumer=_consumer, _desc=_desc):
        @register(_cid, PART, "A", f"{IRL}:reads[consumer={_consumer}]", _desc)
        def _fn(ctx: Context) -> Finding:
            if not _read_log_has(ctx, _consumer, DP):
                return Finding(_cid, FAIL, f"{IRL}:reads[consumer={_consumer}]", f"{_consumer} 未读取 P4-a 输出")
            return Finding(_cid, PASS, f"{IRL}:reads[consumer={_consumer}]", _desc + "：通过")

        return _fn

    _mk()


for _cid, _src, _desc in [
    ("P4.I4.p4b_read_p1", "analysis/_index/p1_to_p4_quality.yaml", "I4 P4-b 读取 P1 产出"),
    ("P4.I5.p4b_read_p2", "02_writing/p2_to_p4b_quality.yaml", "I5 P4-b 读取 P2 产出"),
    ("P4.I6.p4b_read_p3", "03_typesetting/check_report.md", "I6 P4-b 读取 P3 产出"),
]:
    def _mk(_cid=_cid, _src=_src, _desc=_desc):
        @register(_cid, PART, "A", f"{QA}:sources[{_src}]", _desc)
        def _fn(ctx: Context) -> Finding:
            doc = ctx.doc(QA)
            if not _present(doc):
                return Finding(_cid, NA, QA, "质量评估不存在")
            srcs = get_in(doc, "sources", []) or []
            # 多数据集运行时接口文件带 _ACC 后缀，按逻辑名匹配
            key = _src.split("/")[-1].split(".")[0]
            if not any(key in str(s) for s in srcs):
                return Finding(_cid, FAIL, f"{QA}:sources", f"未读取 {_src}")
            return Finding(_cid, PASS, f"{QA}:sources", _desc + "：通过")

        return _fn

    _mk()


@register("P4.I7.feedback_path", PART, "A", f"{FB}:feedback#path", "I7 反馈路径已给出")
def _i7(ctx: Context) -> Finding:
    f = _b6(ctx)
    f.check_id = "P4.I7.feedback_path"
    f.anchor = f"{FB}:feedback#path"
    return f


# ============================================================ 变异用例（先红后绿）
# 依据：04.P4/P4纲要.txt §13.1 十六个用例


def _del(fixture: Dict[str, Any], rel: str, *path: str) -> None:
    cur = fixture[rel]
    for k in path[:-1]:
        cur = cur[k]
    cur.pop(path[-1], None)


def _set(fixture: Dict[str, Any], rel: str, path: str, value: Any) -> None:
    cur = fixture[rel]
    keys = path.split(".")
    for k in keys[:-1]:
        cur = cur[k]
    cur[keys[-1]] = value


def _journal(fixture: Dict[str, Any], idx: int) -> Dict[str, Any]:
    return fixture[JD]["journals"][idx]


def _del_journal_field(fixture: Dict[str, Any], idx: int, block: str, key: str) -> None:
    _journal(fixture, idx).get(block, {}).pop(key, None)


def _set_journal_field(fixture: Dict[str, Any], idx: int, block: str, key: str, value: Any) -> None:
    _journal(fixture, idx).setdefault(block, {})[key] = value


def _pop_recommended_key(fixture: Dict[str, Any], idx: int, key: str) -> None:
    fixture[RJ]["recommended"][idx].pop(key, None)


def _expand_recommended(fixture: Dict[str, Any], n: int) -> None:
    items = fixture[RJ]["recommended"]
    if not items:
        return
    while len(items) < n:
        items.append({**items[-1], "rank": len(items) + 1})


def _drop_read(fixture: Dict[str, Any], consumer: str) -> None:
    log = fixture[IRL]
    log["reads"] = [r for r in log.get("reads", []) if r.get("consumer") != consumer]


case("P4-A1", "P4.A1.topic_judgment", "topic_judgment.novelty_level", "删除 novelty_level",
     lambda f: _del(f, DP, "topic_judgment", "novelty_level"), PART, "删字段 → 完整性检查 FAIL")
case("P4-A2", "P4.A2.directions_count", "journal_direction.candidate_directions", "方向改为 1 个",
     lambda f: _set(f, DP, "journal_direction.candidate_directions", ["生信方法学"]), PART, "改 1 个 → 计数检查 FAIL")
case("P4-A3", "P4.A3.excluded_reason", "journal_direction.excluded[0].reason", "理由留空",
     lambda f: _set(f, DP, "journal_direction.excluded", [{"direction": "Nature 系", "reason": "  "}]), PART,
     "留空 → 理由检查 FAIL")
case("P4-A7", "P4.A7.user_confirmed", "status", "status 改为 draft",
     lambda f: _set(f, DP, "status", "draft"), PART, "未确认 → 确认检查 FAIL")
case("P4-C1", "P4.C1.package_fields", "typesetting_constraints", "删除整个排版约束块",
     lambda f: _del(f, DP, "typesetting_constraints"), PART, "删块 → 完整性检查 FAIL")
case("P4-C2", "P4.C2.topic_evidence", "topic_judgment.study_type", "study_type 置空",
     lambda f: _set(f, DP, "topic_judgment.study_type", None), PART, "留空 → 依据检查 FAIL")
case("P4-C5", "P4.C5.analysis_requirements", "analysis_requirements.required_modules", "改为 0 条",
     lambda f: _set(f, DP, "analysis_requirements.required_modules", []), PART, "改 0 → 计数检查 FAIL")
case("P4-E3", "P4.E3.compare_a_b", "comparison", "删除对比块",
     lambda f: _del(f, QA, "comparison"), PART, "跳过对比 → 对比检查 FAIL")
case("P4-S1", "P4.S1.has_source", "journals[0].impact_factor.source", "删除来源",
     lambda f: _del_journal_field(f, 0, "impact_factor", "source"), PART, "删来源 → 来源检查 FAIL")
case("P4-S4", "P4.S4.pending_marker", "journals[0].partition.value", "值置空且不登记 pending",
     lambda f: _set_journal_field(f, 0, "partition", "value", None), PART, "未登记 → 标记检查 FAIL")
case("P4-J1", "P4.J1.recommended_count", "recommended", "推荐数改为 5",
     lambda f: _expand_recommended(f, 5), PART, "改 5 个 → 计数检查 FAIL")
case("P4-J4", "P4.J4.has_risks", "recommended[0].risks", "删除 risks 键",
     lambda f: _pop_recommended_key(f, 0, "risks"), PART, "删风险 → 字段检查 FAIL")
case("P4-O1", "P4.O1.order_present", "order", "删除投稿顺序",
     lambda f: _set(f, SO, "order", []), PART, "删顺序 → 字段检查 FAIL")
case("P4-P1", "P4.P1.executed", "checks", "筛查项清空",
     lambda f: _set(f, PC, "checks", []), PART, "跳过 → 标记检查 FAIL")
case("P4-P4", "P4.P4.excluded_if_flagged", "overall", "overall 改为 predatory 且该刊仍在推荐列表",
     lambda f: _set(f, PC, "overall", "predatory"), PART, "未排除 → 逻辑检查 FAIL")
case("P4-I1", "P4.I1.p1_read_p4a", "reads[consumer=P1]", "删除 P1 的读取记录",
     lambda f: _drop_read(f, "P1"), PART, "未读取 → 日志检查 FAIL")
