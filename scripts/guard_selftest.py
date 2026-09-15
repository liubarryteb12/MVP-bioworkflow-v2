#!/usr/bin/env python3
"""守卫自测 / 变异测试入口。

先红后绿是唯一有效证据：每个变异用例必须「注入后抓到 FAIL → 恢复后回到 PASS」。
抓不到 = 空规，不计入通过（总纲要 §18）。

用法：
    python scripts/guard_selftest.py --part P4 --fixture            # 骨架自测：内置基线
    python scripts/guard_selftest.py --part P1 --fixture --dataset GSE7451
    python scripts/guard_selftest.py --part P1 --dataset GSE7451    # 真实运行：读工作空间产出
    python scripts/guard_selftest.py --part P4 --check              # 只跑判据，不跑变异
"""

from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from guards import base, mutation  # noqa: E402
from guards import checks_p1, checks_p4  # noqa: F401,E402  注册 P1 / P4 判据与变异用例
from guards import fixtures_p4  # noqa: E402

OUT_PATHS = {
    "P1": "analysis/_runs/mutation_results.json",
    "P2": "02_writing/_runs/mutation_results.json",
    "P3": "03_typesetting/_runs/mutation_results.json",
    "P4": "04_journal/_runs/mutation_results.json",
}


def _fixture_for(part: str, dataset: str) -> dict:
    if part == "P4":
        return fixtures_p4.FIXTURE
    if part == "P1":
        return checks_p1._fig_fixture(dataset or "GSE7451")
    return {}


def _rels_for(part: str, dataset: str) -> list:
    if part == "P4":
        return list(fixtures_p4.FIXTURE.keys())
    if part == "P1":
        acc = (dataset or "GSE7451").upper()
        return [
            f"inputs/migration_log_{acc}.yaml",
            f"analysis/_index/data_availability_{acc}.yaml",
            f"analysis/_index/figure_export_{acc}.yaml",
            f"analysis/_index/p1_to_p2_evidence_{acc}.yaml",
        ]
    return []


def _load_fixture(workspace: str, part: str, dataset: str) -> dict:
    ctx = base.Context(workspace=workspace)
    for rel in _rels_for(part, dataset):
        ctx.doc(rel)
    return ctx.docs


def _print_check_summary(part: str, findings) -> None:
    impl = [m for m in base.CHECKS.values() if m.part == part and m.implemented]
    empty = [m for m in base.CHECKS.values() if m.part == part and not m.implemented]
    print(f"[{part}] 判据总数 {len(impl) + len(empty)} / 已实现 {len(impl)} / 空规 {len(empty)}")
    s = base.summarize(findings)
    print(f"[{part}] 本轮判定：pass={s['pass']}  fail={s['fail']}  N/A={s['N/A']}")
    for f in findings:
        if f.status == "fail":
            print(f"  FAIL  {f.check_id}  @{f.anchor}  {f.message}")
    if empty:
        print(f"[{part}] 空规清单（不计入通过）：")
        for m in empty:
            print(f"  空规  {m.check_id}  @{m.anchor}")


def main() -> int:
    ap = argparse.ArgumentParser(description="P1-P4 守卫自测与变异测试")
    ap.add_argument("--workspace", default=".", help="project_root 路径")
    ap.add_argument("--part", default="P4", choices=["P1", "P2", "P3", "P4"])
    ap.add_argument("--dataset", default=None, help="数据集编号（P1 需要，如 GSE7451）")
    ap.add_argument("--fixture", action="store_true", help="用内置最小合规基线（骨架自测）")
    ap.add_argument("--check", action="store_true", help="只跑判据，不跑变异")
    ap.add_argument("--out", default=None, help="变异结果输出路径")
    args = ap.parse_args()

    dataset = (args.dataset or "").upper() or None

    if args.fixture:
        fixture = _fixture_for(args.part, dataset)
        if not fixture:
            print(f"内置 fixture 暂不支持 {args.part}")
            return 2
    else:
        fixture = _load_fixture(args.workspace, args.part, dataset)

    ctx = base.Context(workspace=args.workspace)
    ctx.docs = fixture
    ctx.meta["dataset"] = dataset
    findings = base.run_part(ctx, args.part)
    _print_check_summary(args.part, findings)

    if args.check:
        return 0 if all(f.status != "fail" for f in findings) else 1

    results = mutation.run_part_mutations(args.part, fixture, meta={"dataset": dataset})
    out = args.out or os.path.join(args.workspace, OUT_PATHS[args.part])
    mutation.write_results(results, out)

    print(f"[{args.part}] 变异用例 {results['total']} / PASS {results['n_pass']} / 覆盖率 {results['coverage']}")
    for c in results["cases"]:
        if c["verdict"] != "PASS":
            print(
                f"  {c['verdict']}  {c['case_id']} ({c['check_id']})  "
                f"基线={c['baseline_status']} 注入后={c['after_status']} 恢复后={c['restored_status']}"
            )
    print(f"[{args.part}] 结果写入：{out}")

    return 0 if results["n_pass"] == results["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
