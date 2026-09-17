#!/usr/bin/env python3
"""下载 GEO 平台注释表，生成「探针 → ENTREZ」映射表。

存在的理由：Bioconductor 芯片注释库（illuminaHumanv4.db 等）在云端环境可能装得上、
却完成不了探针→ENTREZ 映射（select(keytype=PROBEID) 与 Bimap 均取不到条目）。
此时 GEO 官方平台注释表（GPL*.annot.gz，含 ID / Gene symbol / Gene ID）是权威替代，
且不依赖任何 R 包。没有它，Illumina / Agilent 芯片就无法做通路富集。

纪律：不凭记忆猜列名与路径——平台目录按 GEO 规则推导，列名现场从表头识别。

用法：
    python scripts/fetch_platform_annot.py --dataset GSE113865 --workspace . --no-proxy
"""

from __future__ import annotations

import argparse
import csv
import gzip
import os
import re
import sys

import requests
import yaml

DEFAULT_PROXY = "http://127.0.0.1:7890"

# 表头列名因平台而异，按优先级识别
ENTREZ_COLS = ["Gene ID", "Entrez Gene ID", "ENTREZ_GENE_ID", "Entrez_Gene_ID", "ENTREZID"]
SYMBOL_COLS = ["Gene symbol", "Symbol", "GENE_SYMBOL", "SYMBOL"]


def platform_dir(gpl: str) -> str:
    """GPL10558 -> GPL10nnn；GPL570 -> GPL570（GEO 平台目录命名规则）。"""
    m = re.fullmatch(r"GPL(\d+)", gpl.strip(), re.I)
    if not m:
        raise ValueError(f"非法平台号：{gpl}")
    d = m.group(1)
    return f"GPL{d}" if len(d) <= 3 else f"GPL{d[:len(d) - 3]}nnn"


def main() -> int:
    ap = argparse.ArgumentParser(description="下载 GEO 平台注释并生成探针→ENTREZ 映射")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--platform", default=None, help="平台号；缺省时从 data_availability 读取")
    ap.add_argument("--proxy", default=DEFAULT_PROXY)
    ap.add_argument("--no-proxy", action="store_true")
    args = ap.parse_args()

    ws = os.path.abspath(args.workspace)
    acc = args.dataset.upper()
    proxy = None if args.no_proxy else args.proxy

    gpl = args.platform
    if not gpl:
        da = os.path.join(ws, "analysis", "_index", f"data_availability_{acc}.yaml")
        if os.path.exists(da):
            with open(da, encoding="utf-8") as f:
                gpl = (yaml.safe_load(f) or {}).get("inputs", {}).get("platform_id")
    if not gpl:
        print(f"[{acc}] 未拿到 platform_id，跳过平台注释表（富集将依赖 Bioconductor 注释库）")
        return 0

    url = f"https://ftp.ncbi.nlm.nih.gov/geo/platforms/{platform_dir(gpl)}/{gpl}/annot/{gpl}.annot.gz"
    dst_dir = os.path.join(ws, "inputs", "raw", "_platform")
    os.makedirs(dst_dir, exist_ok=True)
    gz = os.path.join(dst_dir, f"{gpl}.annot.gz")
    try:
        proxies = {"http": proxy, "https": proxy} if proxy else None
        with requests.get(url, stream=True, proxies=proxies, timeout=600) as r:
            r.raise_for_status()
            with open(gz, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    if chunk:
                        f.write(chunk)
    except Exception as exc:
        print(f"[{acc}] 平台注释表下载失败：{exc}", file=sys.stderr)
        return 0

    out_rel = os.path.join("inputs", "metadata", f"{acc}_probe_map.csv")
    out_abs = os.path.join(ws, out_rel)
    n_total = n_mapped = 0
    entrez_col = None
    symbol_col = None
    with gzip.open(gz, "rt", encoding="utf-8", errors="replace") as fi, \
            open(out_abs, "w", encoding="utf-8", newline="") as fo:
        w = csv.writer(fo)
        w.writerow(["probe_id", "entrez", "symbol"])
        in_tab = False
        header_done = False
        for line in fi:
            if line.startswith("!platform_table_begin"):
                in_tab = True
                continue
            if line.startswith("!platform_table_end"):
                break
            if not in_tab:
                continue
            row = [c.strip() for c in line.rstrip("\n").split("\t")]
            if not header_done:
                header = row
                for c in ENTREZ_COLS:
                    if c in header:
                        entrez_col = header.index(c)
                        break
                for c in SYMBOL_COLS:
                    if c in header:
                        symbol_col = header.index(c)
                        break
                if entrez_col is None:
                    print(f"[{acc}] 平台注释表缺少 Entrez 列（表头前 8 项：{header[:8]}）", file=sys.stderr)
                    return 0
                header_done = True
                continue
            n_total += 1
            pid = row[0] if row else ""
            ent = row[entrez_col] if entrez_col < len(row) else ""
            sym = row[symbol_col] if (symbol_col is not None and symbol_col < len(row)) else ""
            if not pid or not ent:
                continue
            ent = ent.split("|")[0].strip()      # 一探针对多基因时取首个
            if not ent:
                continue
            n_mapped += 1
            w.writerow([pid, ent, sym])
    print(f"[{acc}] 平台注释 {gpl}：{n_mapped}/{n_total} 探针有 Entrez ID → {out_rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
