#!/usr/bin/env python3
"""守卫自测 / 变异测试入口。

先红后绿是唯一有效证据：每个变异用例必须「注入后抓到 FAIL → 恢复后回到 PASS」。
抓不到 = 空规，不计入通过（总纲要 §18）。

用法：
    python scripts/guard_selftest.py --part P4 --fixture   # 骨架自测：内置基线，不读工作空间
    python scripts/guard_selftest.py --part P4             # 真实运行：读工作空间已产出的接口文件
    python scripts/guard_selftest.py --part P4 --check     # 只跑判据，不跑变异
"""

from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from guards import base, mutation  # noqa: E402
from guards import checks_p4  # noqa: F401,E402  注册 P4 判据与变异用例

try:
    from guards import fixtures_p4
except ImportError:  # pragma: no cover
    fixtures_p4 = None

OUT_PATHS = {
    "P1": "analysis/_runs/mutation_results.json",
    "P2": "02_writing/_runs/mutation_results.json",
    "P3": "03_typesetting/_runs/mutation_results.json",
    "P4": "04_journal/_runs/mutation_results.json",
}


def _rels_for(part: str):
    if part == "P4" and fixtures_p4 is not None:
        return list(fixtures_p4.FIXTURE.keys())
    return []


def _load_fixture(workspace: str, part: str) -> dict:
    ctx = base.Context(workspace=workspace)
    for rel in _rels_for(part):
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
    ap.add_argument("--fixture", action="store_true", help="用内置最小合规基线（骨架自测）")
    ap.add_argument("--check", action="store_true", help="只跑判据，不跑变异")
    ap.add_argument("--out", default=None, help="变异结果输出路径")
    args = ap.parse_args()

    if args.fixture:
        if fixtures_p4 is None or args.part != "P4":
            print("内置 fixture 目前仅支持 P4")
            return 2
        fixture = fixtures_p4.FIXTURE
    else:
        fixture = _load_fixture(args.workspace, args.part)

    ctx = base.Context(workspace=args.workspace)
    ctx.docs = fixture
    findings = base.run_part(ctx, args.part)
    _print_check_summary(args.part, findings)

    if args.check:
        return 0 if all(f.status != "fail" for f in findings) else 1

    results = mutation.run_part_mutations(args.part, fixture)
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
