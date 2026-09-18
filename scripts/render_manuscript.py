#!/usr/bin/env python3
"""把 P2 的 markdown 正文渲染为可交付的 docx，并转出 pdf。

为什么需要它：此前 P2 只产出 markdown 大纲，P3 因而没有任何稿件文件可交——
用户拿到的是"分析结果"而不是"文稿"。本脚本补上最后一公里。

排版依据（02版 P3 规范）：
- A4 显式 210 × 297 mm（python-docx 默认是 Letter，必须显式设）
- 页边距 2.54 cm；正文 1.5 倍行距
- 标题加粗、按级别递减字号（14 / 13 / 12 pt）
- 图注/表注段 line_spacing = 1.0（否则图下会出现大段空白）
- 正文 Arial

用法：
    python scripts/render_manuscript.py --md 02_writing/manuscript/manuscript_v1.md \
        --outdir 03_typesetting/output/A
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys


def _set_run_font(run, name="Arial", size=None, bold=None):
    from docx.shared import Pt
    run.font.name = name
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    # 东亚字体也指到同一族，避免 Word 回退到宋体
    try:
        from docx.oxml.ns import qn
        run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    except Exception:
        pass


def _add_para(doc, text, size=11, bold=False, spacing=1.5, style=None):
    from docx.shared import Pt
    p = doc.add_paragraph(style=style)
    pf = p.paragraph_format
    pf.line_spacing = spacing
    pf.space_after = Pt(6)
    run = p.add_run(text)
    _set_run_font(run, size=size, bold=bold)
    return p


def _add_table(doc, rows):
    t = doc.add_table(rows=len(rows), cols=len(rows[0]))
    t.style = "Table Grid"
    for i, row in enumerate(rows):
        for j, cell in enumerate(row):
            c = t.cell(i, j)
            c.text = ""
            p = c.paragraphs[0]
            p.paragraph_format.line_spacing = 1.0
            run = p.add_run(cell)
            _set_run_font(run, size=9, bold=(i == 0))
    return t


def render_docx(md_path: str, out_docx: str) -> dict:
    try:
        import docx  # noqa: F401
    except ImportError:
        return {"status": "failed", "error": "python-docx 未安装（pip install python-docx）"}

    from docx import Document
    from docx.shared import Mm, Pt

    with open(md_path, encoding="utf-8") as f:
        lines = f.read().splitlines()

    doc = Document()

    # A4 显式尺寸（python-docx 默认 Letter）
    sec = doc.sections[0]
    sec.page_width = Mm(210)
    sec.page_height = Mm(297)
    for attr in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, attr, Mm(25.4))

    base = os.path.dirname(os.path.abspath(md_path))
    n_fig = 0
    i = 0
    in_front = False
    while i < len(lines):
        raw = lines[i]
        line = raw.strip()

        # 跳过 yaml front matter
        if i == 0 and line == "---":
            in_front = True
            i += 1
            continue
        if in_front:
            if line == "---":
                in_front = False
            i += 1
            continue

        if not line:
            i += 1
            continue

        # 图片：![](path)
        m = re.match(r"^!\[\]\((.+)\)$", line)
        if m:
            img = m.group(1)
            cand = img if os.path.isabs(img) else os.path.join(base, img)
            if os.path.exists(cand):
                try:
                    doc.add_picture(cand, width=Mm(160))
                    n_fig += 1
                except Exception as exc:
                    _add_para(doc, f"[图片插入失败：{img} — {exc}]", size=9, spacing=1.0)
            else:
                _add_para(doc, f"[缺图：{img}]", size=9, spacing=1.0)
            i += 1
            continue

        # 表格块
        if line.startswith("|") and i + 1 < len(lines) and set(lines[i + 1].strip()) <= set("|-: "):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            if rows:
                _add_table(doc, rows)
                doc.add_paragraph()
            continue

        if line.startswith("### "):
            _add_para(doc, line[4:], size=12, bold=True, spacing=1.5)
        elif line.startswith("## "):
            _add_para(doc, line[3:], size=13, bold=True, spacing=1.5)
        elif line.startswith("# "):
            _add_para(doc, line[2:], size=14, bold=True, spacing=1.5)
        elif re.match(r"^\*\*(Figure|Table)\b", line):
            # 图注/表注：line_spacing 必须 1.0，否则图下留白
            _add_para(doc, line, size=10, spacing=1.0)
        else:
            txt = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
            _add_para(doc, txt, size=11, spacing=1.5)
        i += 1

    os.makedirs(os.path.dirname(os.path.abspath(out_docx)), exist_ok=True)
    doc.save(out_docx)
    return {"status": "ok", "docx": out_docx, "figures_embedded": n_fig}


def docx_to_pdf(docx_path: str, outdir: str) -> dict:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return {"status": "skipped", "reason": "LibreOffice 不可用（apt-get install -y libreoffice-writer）"}
    try:
        p = subprocess.run(
            [soffice, "--headless", "--norestore", "--convert-to", "pdf",
             "--outdir", outdir, docx_path],
            capture_output=True, text=True, timeout=600)
        pdf = os.path.join(outdir, os.path.splitext(os.path.basename(docx_path))[0] + ".pdf")
        ok = os.path.exists(pdf)
        return {"status": "ok" if ok else "failed",
                "pdf": pdf if ok else None,
                "log": (p.stdout or p.stderr or "")[-400:]}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


def main() -> int:
    ap = argparse.ArgumentParser(description="markdown 正文 → docx → pdf")
    ap.add_argument("--md", required=True)
    ap.add_argument("--outdir", default="03_typesetting/output/A")
    args = ap.parse_args()

    if not os.path.exists(args.md):
        print(f"[render] 找不到正文：{args.md}", file=sys.stderr)
        return 1

    os.makedirs(args.outdir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(args.md))[0]
    out_docx = os.path.join(args.outdir, stem + ".docx")

    r1 = render_docx(args.md, out_docx)
    print(f"[render] docx: {r1}")
    if r1.get("status") != "ok":
        return 1

    r2 = docx_to_pdf(out_docx, args.outdir)
    print(f"[render] pdf: {r2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
