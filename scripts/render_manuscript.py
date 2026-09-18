#!/usr/bin/env python3
"""P3 排版：把 P2 的 manuscript.md 渲染为投稿包（A 路 docx / B 路 latex）。

依据 02版《合集-全五份》P3 部分（唯一真源）：
- §2.4 排版双路径：`.md` →A docx→ pdf ／ `.md` →B latex→ pdf。禁混路、同源、各路自足。
       A 路产物：output/A/manuscript.docx、A/manuscript_排版核对版.docx、A/manuscript.pdf、A/submission_package.zip
       B 路产物：output/B/main.tex → B/manuscript.pdf、B/manuscript_核对版.pdf、B/submission_package.zip
       两路 manifest 均记 source_md_sha256（P3-PATH-90）
- §8 双轨行距：审稿版=双倍行距+连续行号；安全版=1.5 倍+无行号
- §9.1 Word 模板参数：英文 Times New Roman 12pt；A4；四边 2.5cm；左对齐不缩进；
       标题编号 1/1.1/1.1.1；页脚居中自动页码
- §10 图表位置纪律：图题在图下、表题在表上、图注独立成段；表格为原生 Word 表格，
       **无竖线、无底纹**（三线表）
- §3.1③ 参考文献一条一段 + 悬挂缩进

用法：
    python scripts/render_manuscript.py --route A_B --md 02_writing/manuscript/manuscript_v1.md \
        --outdir 03_typesetting/output
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

FIGS_SUBDIR = ("analysis", "outputs")

W_A, H_A = 210, 297          # A4 mm（§9.1）
MARGIN_MM = 25               # §9.1 四边 2.5 cm（不是 2.54cm：那会让版心变 159.2mm，与 T3 的 160mm 冲突）
EN_FONT = "Times New Roman"  # §9.1
EN_SIZE = 12
CN_FONT = "宋体"


# ----------------------------------------------------------------- 工具

def sha256_file(p: str) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def _resolve_img(payload: str, md_base: str, ws: str):
    """图片路径解析：md 里记的是 workspace 相对路径，不能只按 md 所在目录拼。"""
    cands = []
    if os.path.isabs(payload):
        cands.append(payload)
    else:
        cands += [os.path.join(ws, payload), os.path.join(md_base, payload), payload]
    for c in cands:
        if os.path.exists(c):
            return c
    return None


def _set_run(run, size=EN_SIZE, bold=False, italic=False, cn=CN_FONT):
    from docx.shared import Pt
    from docx.oxml.ns import qn
    run.font.name = EN_FONT
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    try:
        run._element.rPr.rFonts.set(qn("w:eastAsia"), cn)
    except Exception:
        pass


def _para(doc, text, size=EN_SIZE, bold=False, spacing=2.0, first_line=None,
          hanging=False, keep_with_next=False, align_left=True):
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.line_spacing = spacing
    pf.space_after = Pt(6)
    if align_left:
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT      # §9.1 / §9.2 禁止两端对齐
    if hanging:
        # §3.1③ 悬挂缩进：左缩进 + 首行负缩进
        pf.left_indent = Pt(21)
        pf.first_line_indent = Pt(-21)
    elif first_line is not None:
        pf.first_line_indent = Pt(first_line)
    if keep_with_next:
        pf.keep_with_next = True
    run = p.add_run(text)
    _set_run(run, size=size, bold=bold)
    return p


def _add_page_number_footer(doc):
    """§9.1 页脚居中自动页码（PAGE 域）。"""
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    footer = doc.sections[0].footer
    p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    _set_run(run, size=10)
    fld_begin = OxmlElement("w:fldChar"); fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText"); instr.set(qn("xml:space"), "preserve"); instr.text = "PAGE"
    fld_end = OxmlElement("w:fldChar"); fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin); run._r.append(instr); run._r.append(fld_end)


def _set_line_numbers(doc, enable=True):
    """审稿版连续行号（§8.1）；安全版关闭（T46）。"""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    sectPr = doc.sections[0]._sectPr
    for el in sectPr.findall(qn("w:lnNumType")):
        sectPr.remove(el)
    if enable:
        ln = OxmlElement("w:lnNumType")
        ln.set(qn("w:countBy"), "1")
        ln.set(qn("w:restart"), "continuous")
        ln.set(qn("w:distance"), "360")
        sectPr.append(ln)


def _no_border_table(doc, rows):
    """§10.1 表格为原生 Word 表格、**无竖线、无底纹**（三线表：顶线/表头下线/底线）。"""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt

    t = doc.add_table(rows=len(rows), cols=len(rows[0]))
    t.style = "Table Grid"
    tbl = t._tbl
    tblPr = tbl.tblPr
    for el in tblPr.findall(qn("w:tblBorders")):
        tblPr.remove(el)
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "bottom"):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), "single"); e.set(qn("w:sz"), "8")
        e.set(qn("w:space"), "0"); e.set(qn("w:color"), "000000")
        borders.append(e)
    for edge in ("left", "right", "insideV", "insideH"):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), "none"); e.set(qn("w:sz"), "0")
        e.set(qn("w:space"), "0"); e.set(qn("w:color"), "auto")
        borders.append(e)
    tblPr.append(borders)
    for i, row in enumerate(rows):
        for j, cell in enumerate(row):
            c = t.cell(i, j)
            c.text = ""
            p = c.paragraphs[0]
            p.paragraph_format.line_spacing = 1.0
            p.paragraph_format.space_after = Pt(2)
            run = p.add_run(cell)
            _set_run(run, size=10, bold=(i == 0))
        if i == 0:                       # 表头下横线
            for j in range(len(row)):
                tcPr = t.cell(0, j)._tc.get_or_add_tcPr()
                tcb = OxmlElement("w:tcBorders")
                b = OxmlElement("w:bottom")
                b.set(qn("w:val"), "single"); b.set(qn("w:sz"), "8")
                b.set(qn("w:space"), "0"); b.set(qn("w:color"), "000000")
                tcb.append(b)
                tcPr.append(tcb)
    return t


# ----------------------------------------------------------------- md 解析

def parse_md(md_path: str):
    with open(md_path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    blocks, i = [], 0
    in_front = False
    while i < len(lines):
        line = lines[i].strip()
        if i == 0 and line == "---":
            in_front = True; i += 1; continue
        if in_front:
            if line == "---":
                in_front = False
            i += 1; continue
        if not line:
            i += 1; continue
        m = re.match(r"^!\[\]\((.+)\)$", line)
        if m:
            blocks.append(("img", m.group(1))); i += 1; continue
        if line.startswith("|") and i + 1 < len(lines) and set(lines[i + 1].strip()) <= set("|-: "):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            blocks.append(("table", rows)); continue
        if line.startswith("### "):
            blocks.append(("h3", line[4:]))
        elif line.startswith("## "):
            blocks.append(("h2", line[3:]))
        elif line.startswith("# "):
            blocks.append(("h1", line[2:]))
        elif re.match(r"^\*\*(Figure|Table)\b", line):
            blocks.append(("caption", re.sub(r"\*\*(.+?)\*\*", r"\1", line)))
        elif re.match(r"^\d+\.\s", line):
            blocks.append(("ref", line))
        else:
            blocks.append(("p", re.sub(r"\*\*(.+?)\*\*", r"\1", line)))
        i += 1
    return blocks


def build_docx(blocks, md_path: str, out_docx: str, review_track: bool, ws: str = ".") -> dict:
    from docx import Document
    from docx.shared import Mm

    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Mm(W_A)
    sec.page_height = Mm(H_A)
    for attr in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, attr, Mm(MARGIN_MM))

    spacing = 2.0 if review_track else 1.5      # §8.1 审稿版双倍 / 安全版 1.5
    _set_line_numbers(doc, enable=review_track)  # T44 / T46
    _add_page_number_footer(doc)                 # T53

    base = os.path.dirname(os.path.abspath(md_path))
    n_fig = n_tab = n_ref = 0
    h1 = h2 = h3 = 0
    for kind, payload in blocks:
        if kind == "h1":
            h1 += 1
            _para(doc, payload, size=14, bold=True, spacing=spacing, keep_with_next=True)
        elif kind == "h2":
            h2 += 1
            _para(doc, payload, size=13, bold=True, spacing=spacing, keep_with_next=True)
        elif kind == "h3":
            h3 += 1
            _para(doc, payload, size=12, bold=True, spacing=spacing, keep_with_next=True)
        elif kind == "caption":
            # §10.1 图注独立成段、不贴图；行距随轨
            _para(doc, payload, size=10, spacing=spacing)
        elif kind == "ref":
            n_ref += 1
            _para(doc, payload, size=11, spacing=spacing, hanging=True)   # §3.1③
        elif kind == "table":
            _no_border_table(doc, payload)                                 # §10.1
            doc.add_paragraph()
            n_tab += 1
        elif kind == "img":
            cand = _resolve_img(payload, base, ws)
            if cand:
                try:
                    # §3.1② 图件嵌入宽度上限 = 版心宽 160 mm，不叠加更小的人为上限
                    doc.add_picture(cand, width=Mm(160))
                    n_fig += 1
                except Exception as exc:
                    _para(doc, f"[图片插入失败：{payload} — {exc}]", size=9, spacing=1.0)
            else:
                _para(doc, f"[缺图：{payload}]", size=9, spacing=1.0)
        else:
            _para(doc, payload, size=EN_SIZE, spacing=spacing)

    os.makedirs(os.path.dirname(os.path.abspath(out_docx)), exist_ok=True)
    doc.save(out_docx)
    return {"docx": os.path.basename(out_docx), "figures": n_fig, "tables": n_tab,
            "references": n_ref, "headings": {"h1": h1, "h2": h2, "h3": h3},
            "track": "review(double+line numbers)" if review_track else "safe(1.5, no line numbers)"}


# ----------------------------------------------------------------- B 路 LaTeX

def build_latex(md_path: str, out_tex: str, ws: str = ".") -> dict:
    blocks = parse_md(md_path)
    md_base = os.path.dirname(os.path.abspath(md_path))
    fig_dir = os.path.join(os.path.dirname(os.path.abspath(out_tex)), "figures")
    esc = lambda s: (s.replace("\\", r"\textbackslash{}").replace("&", r"\&")
                      .replace("%", r"\%").replace("_", r"\_").replace("#", r"\#"))
    body = []
    n_fig = 0
    for kind, payload in blocks:
        if kind == "h1":
            body.append(f"\\section*{{{esc(payload)}}}")
        elif kind == "h2":
            body.append(f"\\section{{{esc(payload)}}}")
        elif kind == "h3":
            body.append(f"\\subsection{{{esc(payload)}}}")
        elif kind == "caption":
            body.append(f"\\noindent\\small {esc(payload)}\\par")
        elif kind == "ref":
            # §3.1③ 参考文献一条一段 + 悬挂缩进
            body.append(f"\\noindent\\hangindent=2em\\hangafter=1 {esc(payload)}\\par")
        elif kind == "table":
            cols = " ".join("l" for _ in payload[0])
            body.append("\\begin{center}\\begin{tabular}{" + cols + "}\\toprule")
            for i, row in enumerate(payload):
                body.append(" & ".join(esc(c) for c in row) + r" \\" + ("\\midrule" if i == 0 else ""))
            body.append("\\bottomrule\\end{tabular}\\end{center}")
        elif kind == "img":
            # 各路自足（§2.4 硬约束③）：把图复制到本路 figures/，不引用外部相对路径
            cand = _resolve_img(payload, md_base, ws)
            if cand:
                os.makedirs(fig_dir, exist_ok=True)
                dst = os.path.join(fig_dir, os.path.basename(cand))
                if not os.path.exists(dst):
                    shutil.copy2(cand, dst)
                body.append("\\begin{center}\\includegraphics[width=0.62\\textwidth]"
                            "{figures/" + os.path.basename(cand) + "}\\end{center}")
                n_fig += 1
        else:
            body.append(esc(payload))

    tex = r"""% B 路：P3 自建 main.tex（禁由 .docx 转换，见 P3 §2.4 硬约束②）
\documentclass[12pt,a4paper]{article}
\usepackage[margin=2.5cm]{geometry}      % §9.1 四边 2.5cm
\usepackage{fontspec}
\usepackage{booktabs}
\usepackage{graphicx}
\usepackage{ragged2e}
% §9.1 英文字体；Linux 无真 Times New Roman 时用度量兼容的 Liberation Serif
\IfFontExistsTF{Times New Roman}{\setmainfont{Times New Roman}}{\setmainfont{Liberation Serif}}
\pagestyle{plain}                        % 居中页码
\linespread{2.0}                         % 审稿版双倍行距
\RaggedRight                             % §9.2 左对齐，禁两端对齐
\begin{document}
""" + "\n".join(body) + "\n\\end{document}\n"
    os.makedirs(os.path.dirname(os.path.abspath(out_tex)), exist_ok=True)
    with open(out_tex, "w", encoding="utf-8") as f:
        f.write(tex)
    # 核对要素（用于 P3-PATH-91 两路比对）
    return {"tex": os.path.basename(out_tex),
            "figures": n_fig,
            "tables": sum(1 for k, _ in blocks if k == "table"),
            "references": sum(1 for k, _ in blocks if k == "ref")}


def compile_pdf(tex_path: str, outdir: str) -> dict:
    xe = shutil.which("xelatex")
    if not xe:
        return {"status": "skipped", "reason": "xelatex 不可用（apt-get install -y texlive-xetex texlive-latex-recommended）"}
    try:
        for _ in range(2):   # 两趟，交叉引用稳定
            p = subprocess.run([xe, "-interaction=nonstopmode", "-halt-on-error",
                                os.path.basename(tex_path)],
                               cwd=os.path.dirname(tex_path) or ".", capture_output=True, text=True, timeout=900)
        pdf = os.path.splitext(tex_path)[0] + ".pdf"
        ok = os.path.exists(pdf)
        return {"status": "ok" if ok else "failed",
                "pdf": pdf if ok else None,
                "log": ((p.stdout or "") + (p.stderr or ""))[-500:]}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


def docx_to_pdf(docx_path: str, outdir: str) -> dict:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return {"status": "skipped", "reason": "LibreOffice 不可用"}
    try:
        p = subprocess.run([soffice, "--headless", "--norestore", "--convert-to", "pdf",
                            "--outdir", outdir, docx_path],
                           capture_output=True, text=True, timeout=900)
        pdf = os.path.join(outdir, os.path.splitext(os.path.basename(docx_path))[0] + ".pdf")
        ok = os.path.exists(pdf)
        return {"status": "ok" if ok else "failed", "pdf": pdf if ok else None,
                "log": (p.stdout or p.stderr or "")[-300:]}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


def make_zip(zip_path: str, files: list, ws: str) -> dict:
    n = 0
    os.makedirs(os.path.dirname(os.path.abspath(zip_path)), exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            p = f if os.path.isabs(f) else os.path.join(ws, f)
            if os.path.exists(p):
                z.write(p, os.path.basename(p))
                n += 1
    return {"zip": os.path.basename(zip_path), "files": n,
            "size": os.path.getsize(zip_path) if os.path.exists(zip_path) else 0}


# ----------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description="P3 排版（A 路 docx / B 路 latex）")
    ap.add_argument("--route", default="A_B", choices=["A", "B", "A_B"])
    ap.add_argument("--md", required=True)
    ap.add_argument("--outdir", default="03_typesetting/output")
    ap.add_argument("--workspace", default=".")
    args = ap.parse_args()

    ws = os.path.abspath(args.workspace)
    md_abs = args.md if os.path.isabs(args.md) else os.path.join(ws, args.md)
    if not os.path.exists(md_abs):
        print(f"[P3] manuscript.md 缺失（两路都无源，禁止从 docx 反抽）：{args.md}", file=sys.stderr)
        return 1

    src_sha = sha256_file(md_abs)
    blocks = parse_md(md_abs)
    result = {"route": args.route, "source_md": args.md, "source_md_sha256": src_sha}

    if args.route in ("A", "A_B"):
        a_dir = os.path.join(ws, args.outdir, "A")
        os.makedirs(a_dir, exist_ok=True)
        main_docx = os.path.join(a_dir, "manuscript.docx")
        check_docx = os.path.join(a_dir, "manuscript_排版核对版.docx")
        r_main = build_docx(blocks, md_abs, main_docx, review_track=True, ws=ws)     # §8.1 审稿版
        r_check = build_docx(blocks, md_abs, check_docx, review_track=False, ws=ws)  # §8.1 安全版
        r_pdf = docx_to_pdf(main_docx, a_dir)
        a_files = [main_docx, check_docx] + ([r_pdf["pdf"]] if r_pdf.get("pdf") else [])
        a_zip = os.path.join(a_dir, "submission_package.zip")
        r_zip = make_zip(a_zip, a_files, ws)
        result["A"] = {"docx": r_main, "check_docx": r_check, "pdf": r_pdf, "zip": r_zip}
        print(f"[P3-A] docx={r_main} / 核对版={r_check['track']} / pdf={r_pdf.get('status')} / zip={r_zip}")

    if args.route == "A_B":
        b_dir = os.path.join(ws, args.outdir, "B")
        os.makedirs(b_dir, exist_ok=True)
        main_tex = os.path.join(b_dir, "main.tex")
        r_tex = build_latex(md_abs, main_tex, ws=ws)
        r_pdf_b = compile_pdf(main_tex, b_dir)
        b_files = [main_tex] + ([r_pdf_b["pdf"]] if r_pdf_b.get("pdf") else [])
        b_zip = os.path.join(b_dir, "submission_package.zip")
        r_zip_b = make_zip(b_zip, b_files, ws)
        result["B"] = {"tex": r_tex, "pdf": r_pdf_b, "zip": r_zip_b}
        print(f"[P3-B] tex={r_tex} / pdf={r_pdf_b.get('status')} / zip={r_zip_b}")

    manifest = os.path.join(ws, "03_typesetting", "manifest.yaml")
    import yaml
    os.makedirs(os.path.dirname(manifest), exist_ok=True)
    with open(manifest, "w", encoding="utf-8") as f:
        yaml.safe_dump(result, f, allow_unicode=True, sort_keys=False)
    print(f"[P3] manifest 写入：03_typesetting/manifest.yaml（source_md_sha256={src_sha[:12]}…）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
