"""变异测试驱动：先红后绿。

唯一有效证据 = 注入违规后判据能抓到 FAIL，恢复后回到 PASS。
抓不到 = 空规，不得计入通过（总纲要 §18）。

流程（每个用例）：
  1. 基线：检查 → 期望 PASS；否则记 verdict=基线非绿
  2. 注入：mutate(fixture) → 检查 → 期望 FAIL；仍 PASS 则 caught=False → 空规
  3. 恢复：用原始 fixture → 检查 → 期望 PASS；否则 verdict=未复原
"""

from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from .base import FAIL, PASS, Context, Finding, run_check


@dataclass
class MutationCase:
    case_id: str
    check_id: str
    anchor: str
    injected: str
    mutate: Callable[[Dict[str, Any]], None]
    expect_fail: bool = True
    note: str = ""


CASES: Dict[str, List[MutationCase]] = {}


def case(
    case_id: str,
    check_id: str,
    anchor: str,
    injected: str,
    mutate: Callable[[Dict[str, Any]], None],
    part: str,
    note: str = "",
):
    if case_id in {c.case_id for lst in CASES.values() for c in lst}:
        raise ValueError(f"变异用例重复：{case_id}")
    CASES.setdefault(part, []).append(
        MutationCase(case_id, check_id, anchor, injected, mutate, True, note)
    )


def _ctx_from_fixture(fixture: Dict[str, Any], meta: Dict[str, Any] | None = None) -> Context:
    ctx = Context(workspace=".")
    ctx.docs = copy.deepcopy(fixture)
    ctx.meta.update(meta or {})
    return ctx


def run_part_mutations(part: str, fixture: Dict[str, Any], meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
    cases = CASES.get(part, [])
    results: Dict[str, Any] = {
        "part": part,
        "n_pass": 0,
        "total": len(cases),
        "coverage": "0%",
        "cases": [],
    }
    for mc in cases:
        # 1) 基线
        base_ctx = _ctx_from_fixture(fixture, meta)
        baseline: Finding = run_check(base_ctx, mc.check_id)

        # 2) 注入
        mutated = copy.deepcopy(fixture)
        mc.mutate(mutated)
        mut_ctx = Context(workspace=".")
        mut_ctx.docs = mutated
        mut_ctx.meta.update(meta or {})
        after: Finding = run_check(mut_ctx, mc.check_id)
        caught = after.status == FAIL if mc.expect_fail else after.status == PASS

        # 3) 恢复
        rest_ctx = _ctx_from_fixture(fixture, meta)
        restored: Finding = run_check(rest_ctx, mc.check_id)

        if baseline.status != PASS:
            verdict = "基线非绿"
        elif not caught:
            verdict = "空规"
        elif restored.status != PASS:
            verdict = "未复原"
        else:
            verdict = "PASS"

        if verdict == "PASS":
            results["n_pass"] += 1

        results["cases"].append(
            {
                "case_id": mc.case_id,
                "check_id": mc.check_id,
                "anchor": mc.anchor,
                "injected": mc.injected,
                "expect_fail": mc.expect_fail,
                "caught": bool(caught),
                "baseline_status": baseline.status,
                "after_status": after.status,
                "restored_status": restored.status,
                "verdict": verdict,
                "message": after.message,
            }
        )

    total = results["total"] or 1
    results["coverage"] = f"{results['n_pass'] / total * 100:.0f}%"
    return results


def write_results(results: Dict[str, Any], out_path: str) -> None:
    d = os.path.dirname(out_path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def fixture_to_workspace(fixture: Dict[str, Any], workspace: str) -> None:
    """把内存 fixture 落盘到工作空间（真实运行时由各阶段产出，此函数仅供初始化/演示）。"""
    from .base import dump_yaml

    for rel, doc in fixture.items():
        dump_yaml(os.path.join(workspace, rel), doc)
