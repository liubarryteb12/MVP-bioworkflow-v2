#!/usr/bin/env python3
"""从范例文献 PDF 提取体裁结构（P2 写作模板 / P3 排版参照）。

用途：这批 PDF 是用户指定的"排版与内容写作用参考文献"。
P2 纲要 §7 结构序判定 与 §8 声明块 需要按真实期刊论文校准；
P3 纲要 §7 期刊核对 R1–R5 也需要 Guide/样例。
本脚本把每篇的结构（节序、摘要形态、声明块、参考文献制式）提取为可对照的清单。

纪律：只提取事实结构，不做主观评价；逐字引用的行文留原文，便于后续比对。
"""

from __future__ import annotations

import os
import re
import sys

import pymupdf

SECTION_PATTERNS = [
    r"^(Abstract|Background|Methods|Method|Results|Result|Discussion|Conclusions|Conclusion|"
    r"Introduction|Materials and methods|Methods and materials|Results and discussion|"
    r"Study design|Data availability|Code availability|Declarations|Declaration|"
    r"Acknowledgements|Funding|Author details|Authors.{0,3} contributions|"
    r"Ethics approval|Consent|Competing interests|Conflict of interest|"
    r"Supplementary Information|References|Availability of data and materials)\b",
]

DECLARATION_KEYS = [
    "Ethics approval", "Consent for publication", "Availability of data and materials",
    "Competing interests", "Funding", "Authors' contributions", "Author contributions",
    "Acknowledgements", "Declaration of generative AI", "Artificial intelligence",
    "Data availability", "Code availability",
]


def extract(pdf_path: str, outdir: str) -> dict:
    doc = pymupdf.open(pdf_path)
    pages = [p.get_text("text") for p in doc]
    full = "\n".join(pages)
    stem = os.path.splitext(os.path.basename(pdf_path))[0]

    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, f"{stem}.txt"), "w", encoding="utf-8") as f:
        f.write(full)

    # 节标题：行首匹配（Word/期刊排版常把标题单独成行）
    lines = [ln.strip() for ln in full.splitlines() if ln.strip()]
    sections = []
    for ln in lines:
        if len(ln) > 80:
            continue
        for pat in SECTION_PATTERNS:
            if re.match(pat, ln, re.I):
                if ln not in sections:
                    sections.append(ln)
                break

    # 摘要形态：结构式关键词
    abstract_zone = full[:6000]
    structured = bool(re.search(r"\bBackground\b", abstract_zone, re.I)) and \
        bool(re.search(r"\bMethods?\b", abstract_zone, re.I)) and \
        bool(re.search(r"\bResults\b", abstract_zone, re.I))

    # 声明块：逐个关键词找 "Key: value" 或 "Key ... content" 形态
    declarations = {}
    for key in DECLARATION_KEYS:
        m = re.search(rf"{key}\s*:?\s*(.{{0,160}})", full, re.I)
        if m:
            declarations[key] = re.sub(r"\s+", " ", m.group(1)).strip()[:160]

    # 参考文献制式：抓 References 之后前 3 条的形态
    refs_sample = []
    m = re.search(r"\bReferences\b(.{0,1200})", full, re.S)
    if m:
        block = m.group(1)
        refs_sample = [re.sub(r"\s+", " ", s).strip()[:150]
                       for s in re.split(r"\n\s*\n|\n(?=\d+\.)", block) if s.strip()][:4]
    numbered = bool(re.search(r"References\s*\n\s*1\.", full))
    doi_in_refs = "doi.org" in full or "DOI:" in full or "https://doi" in full

    return {
        "file": os.path.basename(pdf_path),
        "n_pages": len(pages),
        "n_chars": len(full),
        "sections_found": sections,
        "abstract_structured": structured,
        "declarations": declarations,
        "references_numbered": numbered,
        "references_have_doi": doi_in_refs,
        "references_sample": refs_sample,
    }


def main() -> int:
    src = sys.argv[1]
    out_root = sys.argv[2]
    os.makedirs(out_root, exist_ok=True)

    results = []
    for fn in sorted(os.listdir(src)):
        if not fn.lower().endswith(".pdf"):
            continue
        path = os.path.join(src, fn)
        try:
            r = extract(path, out_root)
        except Exception as exc:
            r = {"file": fn, "error": str(exc)}
        results.append(r)
        print(f"[{fn}] pages={r.get('n_pages')} sections={len(r.get('sections_found', []))} "
              f"abstract_structured={r.get('abstract_structured')} "
              f"refs_numbered={r.get('references_numbered')} refs_doi={r.get('references_have_doi')}")

    # 汇总
    lines = ["# 范例文献体裁结构提取（P2 模板 / P3 排版参照）", "",
             "> 来源：`06.原始输入材料/排版与内容写作用参考文献/`（用户指定）",
             "> 提取工具：`scripts/extract_reference_structure.py`（逐字留痕：同目录 *.txt）", ""]
    for r in results:
        if "error" in r:
            lines += [f"## {r['file']}", f"- 提取失败：{r['error']}", ""]
            continue
        lines += [
            f"## {r['file']}（{r['n_pages']} 页 / {r['n_chars']} 字符）", "",
            f"- 摘要形态：{'结构式（Background/Methods/Results...）' if r['abstract_structured'] else '非结构式/单段'}",
            f"- 参考文献制式：{'编号制' if r['references_numbered'] else '非编号（作者-年份？需人工确认）'}；含 DOI/链接：{r['references_have_doi']}",
            "",
            "### 节标题（按出现顺序）",
        ] + [f"- {s}" for s in r["sections_found"]] + ["", "### 声明块（逐字片段）"]
        for k, v in r["declarations"].items():
            lines.append(f"- **{k}**：{v}")
        lines += ["", "### 参考文献样例（前几条）"]
        lines += [f"- {s}" for s in r["references_sample"]] + [""]

    with open(os.path.join(out_root, "体裁结构汇总.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"汇总写入：{os.path.join(out_root, '体裁结构汇总.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
