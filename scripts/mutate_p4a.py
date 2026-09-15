#!/usr/bin/env python3
"""对真实 P4-a 期刊方向包跑变异测试（A1–A7 / C1–C9 相关用例）。

先红后绿：注入违规 → 判据必须抓到 FAIL → 恢复到真实包 → 必须回到 PASS。
抓不到 = 空规，不计入通过。

用法：
    python scripts/mutate_p4a.py 04_journal/journal_direction_package.yaml
    python scripts/mutate_p4a.py --all-basic      # 三个基础集依次跑
"""

from __future__ import annotations

import argparse
import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from guards import base, checks_p4, fixtures_p4, mutation  # noqa: E402

P4A_CASE_IDS = {"P4-A1", "P4-A2", "P4-A3", "P4-A7", "P4-C1", "P4-C2", "P4-C5"}


def run_one(path: str, out_path: str) -> int:
    doc = base.load_yaml(path)
    if not isinstance(doc, dict):
        print(f"方向包解析失败：{path}")
        return 2

    fixture = copy.deepcopy(fixtures_p4.FIXTURE)
    fixture[checks_p4.DP] = doc

    all_cases = mutation.CASES.get("P4", [])
    selected = [c for c in all_cases if c.case_id in P4A_CASE_IDS]
    mutation.CASES["P4"] = selected
    try:
        results = mutation.run_part_mutations("P4", fixture)
    finally:
        mutation.CASES["P4"] = all_cases

    results["target"] = path.replace("\\", "/")
    mutation.write_results(results, out_path)

    print(f"[{os.path.basename(path)}] 变异用例 {results['total']} / PASS {results['n_pass']} / 覆盖率 {results['coverage']}")
    for c in results["cases"]:
        if c["verdict"] != "PASS":
            print(
                f"  {c['verdict']}  {c['case_id']} ({c['check_id']}) "
                f"基线={c['baseline_status']} 注入后={c['after_status']} 恢复后={c['restored_status']}"
            )
    print(f"[{os.path.basename(path)}] 结果写入：{out_path}")
    return 0 if results["n_pass"] == results["total"] else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="P4-a 方向包变异测试")
    ap.add_argument("path", nargs="?", help="方向包 yaml 路径")
    ap.add_argument("--all-basic", action="store_true", help="依次跑三个基础集")
    ap.add_argument("--outdir", default="04_journal/_runs")
    args = ap.parse_args()

    targets = []
    if args.all_basic:
        targets = [
            "04_journal/journal_direction_package.yaml",
            "04_journal/packages/GSE2379.yaml",
            "04_journal/packages/GSE10036.yaml",
        ]
    elif args.path:
        targets = [args.path]
    else:
        ap.error("需要指定 path 或 --all-basic")

    rc = 0
    for t in targets:
        name = os.path.splitext(os.path.basename(t))[0]
        out = os.path.join(args.outdir, f"mutation_results_{name}.json")
        rc |= run_one(t, out)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
