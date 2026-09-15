#!/usr/bin/env python3
"""图件五格式导出：pdf / svg / png / tiff / jpg。

纪律（P3 纲要 §12 / §13 / §17）：
- 矢量是母版，位图是派生：pdf → svg 用 pdftocairo（矢量→矢量，不损失）。
- 位图先出 600 dpi PNG，再由 PNG 派生 TIFF（LZW）与 JPG（quality≥90）。
- 不插值放大：位图分辨率由矢量原始渲染决定，不靠改 dpi 标签伪造。
- 单文件 < 10 MB（Wiley 硬规定），超限需走降级顺序。

用法（作为模块被 run_p1 调用，也可单独）：
    python -c "from figure_export import export_one; print(export_one('path/to/fig.pdf'))"
"""

from __future__ import annotations

import os
import shutil
import subprocess

MAX_BYTES = 10 * 1024 * 1024
PNG_DPI = 600
JPG_DPI = 300
JPG_QUALITY = 95


def _run(cmd: list) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return p.returncode, (p.stderr or p.stdout or "")[-800:]
    except Exception as exc:
        return 1, str(exc)


def export_one(pdf_path: str, dpi: int = PNG_DPI) -> dict:
    base = os.path.splitext(pdf_path)[0]
    out = {"pdf": os.path.basename(pdf_path), "status": "ok", "formats": {}, "warnings": []}

    cairo = shutil.which("pdftocairo")
    if not cairo:
        out["status"] = "tool_missing"
        out["warnings"].append("pdftocairo 不可用（需 poppler-utils），svg/png 无法生成")
        return out

    # 1) pdf -> svg（矢量母版）
    rc, err = _run([cairo, "-svg", pdf_path, base + ".svg"])
    out["formats"]["svg"] = "ok" if rc == 0 and os.path.exists(base + ".svg") else f"fail: {err}"

    # 2) pdf -> png（位图母版，600 dpi 真渲染）
    rc, err = _run([cairo, "-png", "-r", str(dpi), pdf_path, base])
    png_path = base + ".png"
    tmp = f"{base}-1.png"
    if rc == 0 and os.path.exists(tmp) and not os.path.exists(png_path):
        os.replace(tmp, png_path)
    if os.path.exists(tmp) and os.path.exists(png_path) and tmp != png_path:
        os.remove(tmp)
    out["formats"]["png"] = "ok" if os.path.exists(png_path) else f"fail: {err}"
    if not os.path.exists(png_path):
        return out

    # 3) png -> tiff (LZW) 与 jpg
    try:
        from PIL import Image

        with Image.open(png_path) as im:
            rgb = im.convert("RGB")
            tiff_path = base + ".tiff"
            rgb.save(tiff_path, format="TIFF", compression="tiff_lzw", dpi=(dpi, dpi))
            out["formats"]["tiff"] = "ok"

            jpg_path = base + ".jpg"
            rgb.save(jpg_path, format="JPEG", quality=JPG_QUALITY, dpi=(JPG_DPI, JPG_DPI))
            out["formats"]["jpg"] = "ok"

        for f in ("pdf", "svg", "png", "tiff", "jpg"):
            p = f"{base}.{f}"
            if os.path.exists(p):
                size = os.path.getsize(p)
                out.setdefault("sizes_bytes", {})[f] = size
                if size > MAX_BYTES:
                    out["warnings"].append(f"{f} 超过 10MB（{size} bytes），需走降级顺序")
    except Exception as exc:
        out["warnings"].append(f"位图派生失败：{exc}")
        out["formats"].setdefault("tiff", f"fail: {exc}")
        out["formats"].setdefault("jpg", f"fail: {exc}")

    if out["warnings"]:
        out["status"] = "ok_with_warnings"
    return out


if __name__ == "__main__":
    import sys

    for arg in sys.argv[1:]:
        print(arg, export_one(arg))
