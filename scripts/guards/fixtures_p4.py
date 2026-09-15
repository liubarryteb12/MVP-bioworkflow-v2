"""P4 最小合规基线 fixture。

用途：
1. 骨架阶段验证守卫框架"先红后绿"机制可用（不依赖真实数据）。
2. 各阶段实现时作为字段结构参考。

纪律：本 fixture 是**结构示例**，不是真实期刊数据。真实期刊数据必须来自权威源并带来源/时间/人工确认（P4 纲要 §7.3）。
"""

from __future__ import annotations

from typing import Any, Dict

TS = "2026-09-15T15:00:00+08:00"

DIRECTION_PACKAGE: Dict[str, Any] = {
    "package_id": "jdp_20260915_150000",
    "timestamp": TS,
    "stage": "P4-a",
    "status": "confirmed",
    "confirmed_by": "user",
    "topic_judgment": {
        "primary_topic": "转录组差异表达与富集分析",
        "secondary_topic": "细胞周期通路",
        "study_type": "生信分析（无实验验证）",
        "novelty_level": "medium",
        "data_type": "transcriptomics",
        "sample_size": 24,
    },
    "journal_direction": {
        "candidate_directions": ["生信方法学", "分子生物学", "肿瘤生物学"],
        "target_tier": "Q2-Q3",
        "likely_publishers": ["BMC", "Elsevier", "Frontiers"],
        "excluded": [
            {"direction": "Nature 系", "reason": "创新性不足"},
            {"direction": "Cell 系", "reason": "缺少实验验证"},
        ],
    },
    "analysis_requirements": {
        "required_modules": ["quality_control", "differential_expression", "enrichment"],
        "optional_modules": ["survival_analysis", "external_validation"],
        "minimum_evidence": ["至少一个主图", "至少一个验证分析"],
        "data_requirements": ["样本量 ≥ 6", "需外部验证集"],
    },
    "writing_constraints": {
        "structure": "S1",
        "abstract_type": "structured",
        "abstract_limit": 350,
        "keywords_count": "3-10",
        "reference_style": "Vancouver",
        "reference_limit": 60,
        "figure_limit": 8,
        "table_limit": 4,
        "language": "English",
        "audience": "生信 / 临床交叉",
        "story_type": "data-driven",
        "evidence_boundary": "候选",
    },
    "typesetting_constraints": {
        "publisher_system": "BMC",
        "template": "官方模板或通用安全格式",
        "line_spacing": "double",
        "line_numbers": "required",
        "figure_width_single": 85,
        "figure_width_double": 170,
        "figure_format": "five",
    },
    "risks": ["创新性中等，可能影响期刊层级", "缺少实验验证", "缺少外部验证"],
    "uncertainties": ["用户是否有多数据集？", "是否有临床数据？"],
    "pending_items": ["目标期刊", "故事线偏好", "证据边界", "图数上限"],
}

QUALITY_ASSESSMENT: Dict[str, Any] = {
    "stage": "P4-b",
    "timestamp": TS,
    "confirmed_by": "user",
    "p4a_estimate": {
        "novelty": "medium",
        "method_rigor": "high",
        "data_scale": "small",
        "clinical_value": "medium",
        "topic_heat": "warm",
        "competition": "medium",
    },
    "p4b_measured": {
        "narrative_completeness": "high",
        "evidence_consistency": "high",
        "method_rigor": "high",
        "statistical_validity": "high",
        "writing_quality": "medium",
        "figure_quality": "high",
        "novelty": "medium",
        "clinical_value": "medium",
    },
    "comparison": [
        {"dimension": "novelty", "p4a": "medium", "p4b": "medium", "delta": 0, "action": "维持目标层级"},
        {"dimension": "method_rigor", "p4a": "high", "p4b": "high", "delta": 0, "action": "维持"},
        {"dimension": "clinical_value", "p4a": "medium", "p4b": "medium", "delta": 0, "action": "维持"},
    ],
    "sources": [
        "analysis/_index/p1_to_p4_quality.yaml",
        "02_writing/p2_to_p4b_quality.yaml",
        "03_typesetting/check_report.md",
    ],
}

MATCH_SCORE: Dict[str, Any] = {
    "timestamp": TS,
    "weights": {
        "scope_fit": 0.25,
        "tier_fit": 0.25,
        "format_fit": 0.15,
        "policy_fit": 0.15,
        "oa_fit": 0.10,
        "apc_fit": 0.10,
    },
    "candidates": [
        {
            "journal_id": "jtm",
            "name": "Journal of Translational Medicine",
            "scores": {
                "scope_fit": 9,
                "tier_fit": 9,
                "format_fit": 9,
                "policy_fit": 9,
                "oa_fit": 10,
                "apc_fit": 7,
            },
            "total_score": 8.90,
            "reason": "范围匹配、层级匹配、格式匹配",
        },
        {
            "journal_id": "bmc_cancer",
            "name": "BMC Cancer",
            "scores": {
                "scope_fit": 8,
                "tier_fit": 9,
                "format_fit": 9,
                "policy_fit": 9,
                "oa_fit": 10,
                "apc_fit": 8,
            },
            "total_score": 8.75,
            "reason": "层级匹配、格式匹配",
        },
        {
            "journal_id": "front_oncol",
            "name": "Frontiers in Oncology",
            "scores": {
                "scope_fit": 8,
                "tier_fit": 7,
                "format_fit": 9,
                "policy_fit": 8,
                "oa_fit": 10,
                "apc_fit": 6,
            },
            "total_score": 7.90,
            "reason": "范围匹配、格式匹配",
        },
    ],
}

RECOMMENDED_JOURNALS: Dict[str, Any] = {
    "timestamp": TS,
    "stage": "P4-b",
    "recommended": [
        {
            "rank": 1,
            "journal_id": "jtm",
            "name": "Journal of Translational Medicine",
            "publisher": "BMC",
            "tier": "Q1",
            "scope_fit": 9,
            "tier_fit": 9,
            "format_fit": 9,
            "policy_fit": 9,
            "oa_fit": 10,
            "apc_fit": 7,
            "total_score": 8.90,
            "reason": "范围匹配、层级匹配、格式匹配",
            "risks": [],
            "source_verified": True,
        },
        {
            "rank": 2,
            "journal_id": "bmc_cancer",
            "name": "BMC Cancer",
            "publisher": "BMC",
            "tier": "Q2",
            "scope_fit": 8,
            "tier_fit": 9,
            "format_fit": 9,
            "policy_fit": 9,
            "oa_fit": 10,
            "apc_fit": 8,
            "total_score": 8.75,
            "reason": "层级匹配、格式匹配",
            "risks": ["审稿周期可能较长"],
            "source_verified": True,
        },
        {
            "rank": 3,
            "journal_id": "front_oncol",
            "name": "Frontiers in Oncology",
            "publisher": "Frontiers",
            "tier": "Q2",
            "scope_fit": 8,
            "tier_fit": 7,
            "format_fit": 9,
            "policy_fit": 8,
            "oa_fit": 10,
            "apc_fit": 6,
            "total_score": 7.90,
            "reason": "范围匹配、格式匹配",
            "risks": ["版面费较高"],
            "source_verified": True,
        },
    ],
}

SUBMISSION_ORDER: Dict[str, Any] = {
    "timestamp": TS,
    "order": [
        {
            "priority": 1,
            "journal_id": "jtm",
            "name": "Journal of Translational Medicine",
            "reason": "范围与层级最佳匹配",
            "risks": [],
            "fallback_if_rejected": "bmc_cancer",
        },
        {
            "priority": 2,
            "journal_id": "bmc_cancer",
            "name": "BMC Cancer",
            "reason": "层级匹配，格式一致",
            "risks": ["审稿周期可能较长"],
            "fallback_if_rejected": "front_oncol",
        },
        {
            "priority": 3,
            "journal_id": "front_oncol",
            "name": "Frontiers in Oncology",
            "reason": "范围匹配",
            "risks": ["版面费较高"],
            "fallback_if_rejected": None,
        },
    ],
    "notes": ["投稿顺序不是硬性要求，用户可调整", "每次被拒后回到 P4-b 重新评估"],
}


def _predatory_checks() -> list:
    return [
        {"name": "not_in_beall_list", "status": "passed", "source": "https://beallslist.net/"},
        {"name": "in_doaj_or_scopus", "status": "passed", "source": "https://doaj.org/"},
        {
            "name": "official_website_complete",
            "status": "passed",
            "source": "https://translational-medicine.biomedcentral.com/",
        },
        {"name": "review_cycle_reasonable", "status": "passed", "value": "4-8 weeks", "source": "期刊官网"},
        {"name": "apc_reasonable", "status": "passed", "value": "2790 USD", "source": "期刊官网"},
        {"name": "editorial_board_verifiable", "status": "passed", "source": "期刊官网"},
        {"name": "contact_verifiable", "status": "passed", "source": "期刊官网"},
        {"name": "published_articles_verifiable", "status": "passed", "source": "期刊官网"},
        {"name": "not_in_warning_list", "status": "passed", "source": "中科院预警名单 2024"},
    ]


PREDATORY_CHECK: Dict[str, Any] = {
    "journal_id": "jtm",
    "name": "Journal of Translational Medicine",
    "timestamp": TS,
    "checks": _predatory_checks(),
    "overall": "clean",
}


def _journal(jid: str, name: str, publisher: str, issn: str, if_v, part_v, apc_v) -> dict:
    return {
        "journal_id": jid,
        "name": name,
        "publisher": publisher,
        "issn": issn,
        "impact_factor": {
            "value": if_v,
            "year": 2024,
            "source": "https://jcr.clarivate.com/",
            "verified_at": TS,
            "human_confirmed": True,
        },
        "partition": {
            "value": part_v,
            "source": "中科院分区表 2024",
            "verified_at": TS,
            "human_confirmed": True,
        },
        "review_cycle": {"value": "4-8 weeks", "source": "期刊官网", "verified_at": TS},
        "apc": {
            "value": apc_v,
            "source": "期刊官网",
            "verified_at": TS,
            "human_confirmed": True,
        },
        "open_access": True,
        "scope": ["oncology", "cancer_biology"],
        "pending": [],
        "predatory_check": {"status": "clean", "source": "DOAJ", "verified_at": TS},
    }


JOURNAL_DATABASE: Dict[str, Any] = {
    "updated_at": TS,
    "data_policy": "每条数据必须带来源 + 时间 + 人工确认；不确定项登记到 pending，不得猜",
    "journals": [
        _journal("jtm", "Journal of Translational Medicine", "BMC", "1479-5876", 6.1, "Q1", "2790 USD"),
        _journal("bmc_cancer", "BMC Cancer", "BMC", "1471-2407", 3.4, "Q2", "2790 USD"),
        _journal("front_oncol", "Frontiers in Oncology", "Frontiers", "2234-943X", 3.5, "Q2", "3295 USD"),
    ],
}

FEEDBACK: Dict[str, Any] = {
    "timestamp": TS,
    "feedback": [
        {
            "target": "P1",
            "reason": "缺少外部验证集，创新性被判为 medium",
            "action": "补充外部验证分析（GSE 独立队列）",
            "blocking": True,
        },
        {
            "target": "P2",
            "reason": "写作质量为 medium",
            "action": "按 NC-1~7 重跑一致性检查并润色",
            "blocking": False,
        },
    ],
}

INTERFACE_READ_LOG: Dict[str, Any] = {
    "updated_at": TS,
    "reads": [
        {"consumer": "P1", "file": "04_journal/journal_direction_package.yaml", "at": TS},
        {"consumer": "P2", "file": "04_journal/journal_direction_package.yaml", "at": TS},
        {"consumer": "P3", "file": "04_journal/journal_direction_package.yaml", "at": TS},
        {"consumer": "P4-b", "file": "analysis/_index/p1_to_p4_quality.yaml", "at": TS},
        {"consumer": "P4-b", "file": "02_writing/p2_to_p4b_quality.yaml", "at": TS},
        {"consumer": "P4-b", "file": "03_typesetting/check_report.md", "at": TS},
    ],
}

FIXTURE: Dict[str, Any] = {
    "04_journal/journal_direction_package.yaml": DIRECTION_PACKAGE,
    "04_journal/quality_assessment.yaml": QUALITY_ASSESSMENT,
    "04_journal/match_score.yaml": MATCH_SCORE,
    "04_journal/recommended_journals.yaml": RECOMMENDED_JOURNALS,
    "04_journal/submission_order.yaml": SUBMISSION_ORDER,
    "04_journal/predatory_check.yaml": PREDATORY_CHECK,
    "04_journal/journal_database.yaml": JOURNAL_DATABASE,
    "04_journal/feedback.yaml": FEEDBACK,
    "04_journal/_runs/interface_read_log.yaml": INTERFACE_READ_LOG,
}
