#!/usr/bin/env python3
"""参考文献库（reference library）构建与维护。

用途：把"要参考/模仿"的论文 PDF 丢进库，机器提取体裁结构（节序/摘要形态/声明块/文献制式），
      生成逐篇 structure yaml + 统一索引，供 P2（结构序判定、声明块句式、D1 关键词表）、
      P3（R1 期刊核对、V1–V7 激活）、P4-a（期刊方向实证）消费。

纪律（与 P4 §7.3 防幻觉同源）：
- 每条结构数据必须带 source_path（原 PDF）+ extracted_at（时间）+ 全文留痕（txt）。
- 机器提取的是**事实结构**；"期刊判定/结构序归类"等判读标记 status: draft，
  必须人工确认后改 confirmed 才能被下游判据采信。
- 库是唯一真源（元原则 8）：其他文件只留指针。

用法：
    python scripts/build_reference_library.py --src "<PDF目录>" --add
    python scripts/build_reference_library.py --confirm <paper_id> --field structure_order --value S1
    python scripts/build_reference_library.py --list
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from extract_reference_structure import extract  # noqa: E402

LIB = os.path.join("02_writing", "reference_library")
PAPERS = os.path.join(LIB, "papers")


def load_index() -> dict:
    path = os.path.join(LIB, "reference_index.yaml")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {"library_version": "1.0", "updated_at": None,
            "policy": "status=draft 的条目仅供起草参考；只有 confirmed 条目可被判据采信（人工确认）",
            "papers": []}


def save_index(idx: dict) -> None:
    idx["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    os.makedirs(LIB, exist_ok=True)
    with open(os.path.join(LIB, "reference_index.yaml"), "w", encoding="utf-8") as f:
        yaml.safe_dump(idx, f, allow_unicode=True, sort_keys=False, default_flow_style=False)


def cmd_add(src: str) -> int:
    idx = load_index()
    known = {p["paper_id"] for p in idx.get("papers", [])}
    added = 0
    for fn in sorted(os.listdir(src)):
        if not fn.lower().endswith(".pdf"):
            continue
        paper_id = os.path.splitext(fn)[0]
        if paper_id in known:
            print(f"[{paper_id}] 已在库，跳过")
            continue
        pdir = os.path.join(PAPERS, paper_id)
        os.makedirs(pdir, exist_ok=True)
        # 全文留痕 + 结构提取（事实部分）
        info = extract(os.path.join(src, fn), pdir)
        # 原件副本（供溯源与人工翻阅；PDF 不进 git 由 .gitignore 控制）
        shutil.copy2(os.path.join(src, fn), os.path.join(pdir, fn))

        entry = {
            "paper_id": paper_id,
            "source_pdf": os.path.abspath(os.path.join(src, fn)).replace("\\", "/"),
            "library_copy": f"{LIB}/papers/{paper_id}/{fn}".replace("\\", "/"),
            "fulltext_txt": f"{LIB}/papers/{paper_id}/{paper_id}.txt".replace("\\", "/"),
            "structure_yaml": f"{LIB}/papers/{paper_id}/{paper_id}_structure.yaml".replace("\\", "/"),
            "extracted_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "facts": {
                "n_pages": info["n_pages"],
                "abstract_structured": info["abstract_structured"],
                "sections_in_order": info["sections_found"],
                "references_have_doi": info["references_have_doi"],
                "declaration_keys_found": sorted(info["declarations"].keys()),
            },
            # —— 以下为判读字段，机器只给草稿，必须人工确认 ——
            "journal_id": None,
            "publisher": None,
            "structure_order": None,       # S1 / S2-a / S2-b / S2-c
            "reference_style": None,       # numbered / author-year
            "figure_reference_style": None,  # "Figs." / "Figure N" ...
            "status": "draft",
            "confirmed_by": None,
            "confirmed_at": None,
        }
        with open(os.path.join(pdir, f"{paper_id}_structure.yaml"), "w", encoding="utf-8") as f:
            yaml.safe_dump(entry, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

        idx.setdefault("papers", []).append({
            "paper_id": paper_id, "status": "draft",
            "facts": entry["facts"], "extracted_at": entry["extracted_at"],
        })
        added += 1
        print(f"[{paper_id}] 入库：facts 已提取，status=draft（待人工确认判读字段）")

    save_index(idx)
    print(f"共新增 {added} 篇；索引：{LIB}/reference_index.yaml")
    return 0


def cmd_confirm(paper_id: str, field: str, value) -> int:
    idx = load_index()
    spath = os.path.join(PAPERS, paper_id, f"{paper_id}_structure.yaml")
    if not os.path.exists(spath):
        print(f"库中无 {paper_id}")
        return 2
    with open(spath, "r", encoding="utf-8") as f:
        doc = yaml.safe_load(f) or {}
    doc[field] = value
    doc["status"] = "confirmed"
    doc["confirmed_by"] = "user"
    doc["confirmed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    with open(spath, "w", encoding="utf-8") as f:
        yaml.safe_dump(doc, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    for p in idx.get("papers", []):
        if p["paper_id"] == paper_id:
            p["status"] = "confirmed"
            p.setdefault("confirmed_fields", {})[field] = value
    save_index(idx)
    print(f"[{paper_id}] {field} = {value}（status=confirmed）")
    return 0


def cmd_list() -> int:
    idx = load_index()
    for p in idx.get("papers", []):
        print(f"{p['status']:10} {p['paper_id']}  abstract_structured={p['facts'].get('abstract_structured')}  "
              f"sections={len(p['facts'].get('sections_in_order', []))}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="参考文献库")
    ap.add_argument("--src", help="PDF 来源目录")
    ap.add_argument("--add", action="store_true")
    ap.add_argument("--confirm", metavar="PAPER_ID")
    ap.add_argument("--field")
    ap.add_argument("--value")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.add and args.src:
        return cmd_add(args.src)
    if args.confirm:
        if not (args.field and args.value is not None):
            ap.error("--confirm 需要 --field 与 --value")
        return cmd_confirm(args.confirm, args.field, args.value)
    if args.list:
        return cmd_list()
    ap.error("需要 --add --src / --confirm / --list")


if __name__ == "__main__":
    raise SystemExit(main())
