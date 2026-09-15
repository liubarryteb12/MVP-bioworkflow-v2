#!/usr/bin/env python3
"""检查 P4-a 期刊方向包是否满足 A1–A7 与 C1–C9。

用法：
    python scripts/check_direction_package.py 04_journal/journal_direction_package.yaml
    python scripts/check_direction_package.py 04_journal/packages/GSE2379.yaml
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from guards import base, checks_p4  # noqa: E402


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="检查 P4-a 期刊方向包")
    ap.add_argument("path", help="方向包 yaml 路径")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.path):
        print(f"文件不存在：{args.path}")
        return 2

    doc = base.load_yaml(args.path)
    ctx = base.Context(workspace=".")
    ctx.docs[checks_p4.DP] = doc

    ids = sorted(c for c in base.CHECKS if c.startswith("P4.A") or c.startswith("P4.C"))
    ok = True
    for cid in ids:
        f = base.run_check(ctx, cid)
        if f.status == "fail":
            ok = False
        if not args.quiet or f.status == "fail":
            print(f"{f.status:5}  {f.check_id:26}  {f.message}")
    print(f"---\n[{os.path.basename(args.path)}] {len(ids)} 条判据：{'全部通过' if ok else '存在 FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
