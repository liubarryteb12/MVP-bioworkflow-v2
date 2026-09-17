#!/usr/bin/env python3
"""数据可用性分析（P1 第 0 步第 5 动作）。

产出 analysis/_index/data_availability.yaml：
- 识别数据类型（微阵列 / RNA-seq / 单细胞 / 空间 / 小 RNA）
- 识别样本量与分组（分组推断必须留依据，不得凭记忆）
- 列出可用分析与不可用分析（不可用必须带理由）

用法：
    python scripts/data_availability.py --dataset GSE7451 --workspace .
"""

from __future__ import annotations

import argparse
import gzip
import io
import os
import re
import time

import requests
import yaml

DEFAULT_PROXY = "http://127.0.0.1:7890"

# 分组关键词（按优先级从上到下匹配）
GROUP_KEYWORDS = [
    ("control", ("control", "normal", "healthy", "non-tumor", "nontumor", "adjacent", "con")),
    ("tumor", ("tumor", "tumour", "cancer", "carcinoma", "malignant", "hnscc", "scc")),
    ("disease", ("sjogren", "pss", "disease", "case", "patient")),
]


def series_dir(acc: str) -> str:
    digits = re.fullmatch(r"GSE(\d+)", acc.strip(), re.I).group(1)
    return f"GSE{digits[:-3]}nnn" if len(digits) > 3 else f"GSE{digits}nnn"


def guess_group(text: str) -> str | None:
    low = text.lower()
    for label, keys in GROUP_KEYWORDS:
        for k in keys:
            if re.search(rf"(^|[^a-z]){re.escape(k)}([^a-z]|$)", low):
                return label
    return None


def fetch_series_matrix(acc: str, proxy: str | None) -> str | None:
    url = f"https://ftp.ncbi.nlm.nih.gov/geo/series/{series_dir(acc)}/{acc}/matrix/{acc}_series_matrix.txt.gz"
    try:
        proxies = {"http": proxy, "https": proxy} if proxy else None
        r = requests.get(url, proxies=proxies, timeout=180)
        r.raise_for_status()
        return gzip.decompress(r.content).decode("utf-8", errors="replace")
    except Exception as exc:
        print(f"[{acc}] series matrix 获取失败：{exc}")
        return None


def parse_matrix(text: str) -> dict:
    titles, chars = [], []
    for line in text.splitlines():
        if line.startswith("!Sample_title"):
            titles = [s.strip().strip('"') for s in line.split("\t")[1:]]
        elif line.startswith("!Sample_characteristics_ch1"):
            chars.append([s.strip().strip('"') for s in line.split("\t")[1:]])
        elif line.startswith("!Sample_geo_accession"):
            gsms = [s.strip().strip('"') for s in line.split("\t")[1:]]
    return {"titles": titles, "characteristics": chars, "gsms": gsms}


def infer_groups(acc: str, meta: dict, proxy: str | None) -> dict:
    """推断分组。返回 {method, groups:{label:[gsm]}, evidence:[...]}"""
    text = fetch_series_matrix(acc, proxy)
    if not text:
        return {"method": "unresolved", "groups": {}, "evidence": ["series matrix 不可获取，分组待 P1 执行时确认"]}

    m = parse_matrix(text)
    titles = m["titles"] or m["gsms"]
    chars = m["characteristics"]
    groups: dict[str, list] = {}
    evidence = []
    for i, t in enumerate(titles):
        blob = t
        for row in chars:
            if i < len(row):
                blob += " | " + row[i]
        g = guess_group(blob)
        if g is None:
            g = "unclassified"
        groups.setdefault(g, []).append(m["gsms"][i] if i < len(m["gsms"]) else f"idx{i}")
        evidence.append(f"{m['gsms'][i] if i < len(m['gsms']) else i}: {t} -> {g}")

    return {
        "method": "series_matrix_title_and_characteristics",
        "groups": {k: v for k, v in sorted(groups.items())},
        "group_sizes": {k: len(v) for k, v in sorted(groups.items())},
        "evidence_head": evidence[:40],
    }


def detect_data_type(meta: dict, raw_dir: str) -> str:
    gtype = (meta.get("type") or "").lower()
    if "single cell" in gtype:
        return "single_cell"
    if "spatial" in gtype:
        return "spatial_transcriptomics"
    if "non-coding rna" in gtype or "small rna" in gtype:
        return "small_rna_sequencing"
    if "array" in gtype:
        return "microarray"
    if "rna-seq" in gtype or "sequencing" in gtype:
        return "rna_seq"
    return "unknown"


def count_raw_files(raw_dir: str, patterns: tuple) -> int:
    """统计原始文件数。GEO 的 CEL 常为 .CEL.gz，需先去 .gz 再判扩展名。"""
    if not os.path.isdir(raw_dir):
        return 0
    n = 0
    for root, _, files in os.walk(raw_dir):
        for fn in files:
            name = fn.lower()
            if name.endswith(".gz"):
                name = name[:-3]
            if name.endswith(patterns):
                n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description="P1 数据可用性分析")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--proxy", default=DEFAULT_PROXY)
    ap.add_argument("--no-proxy", action="store_true")
    args = ap.parse_args()

    proxy = None if args.no_proxy else args.proxy
    acc = args.dataset.upper()
    ws = args.workspace
    raw_dir = os.path.join(ws, "inputs", "raw", acc)
    meta_path = os.path.join(ws, "04_journal", "snapshots", "geo_meta", f"{acc}_meta.yaml")

    meta = {}
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = yaml.safe_load(f) or {}

    data_type = detect_data_type(meta, raw_dir)
    n_cel = count_raw_files(raw_dir, (".cel",))
    n_fastq = count_raw_files(raw_dir, (".fastq", ".fq", ".fastq.gz", ".fq.gz"))
    groups = infer_groups(acc, meta, proxy)

    analysis_catalog = {
        "microarray": {
            "available": ["quality_control", "rma_normalization", "probe_filtering",
                          "differential_expression_limma", "pathway_enrichment", "pca", "heatmap"],
            "unavailable": {"survival_analysis": "缺少临床随访信息", "single_cell_qc": "非单细胞数据"},
        },
        "small_rna_sequencing": {
            "available": ["read_quality_control", "adapter_trimming", "length_distribution", "abundance_summary"],
            "unavailable": {
                "differential_expression_limma": "n<6 且样本非生物学重复，统计推断不成立",
                "pathway_enrichment": "无差异基因输入，且缺少小 RNA 靶基因富集支撑",
                "rma_normalization": "非微阵列数据",
            },
        },
        "rna_seq": {
            "available": ["quality_control", "deseq2", "pathway_enrichment"],
            "unavailable": {"rma_normalization": "非微阵列数据"},
        },
        "single_cell": {
            "available": ["single_cell_qc", "clustering", "marker_genes"],
            "unavailable": {"deseq2": "单细胞数据需用专用差异方法"},
        },
        "spatial_transcriptomics": {
            "available": ["spatial_qc", "spatial_clustering"],
            "unavailable": {"deseq2": "空间数据需专用方法"},
        },
    }

    cat = analysis_catalog.get(data_type, {"available": [], "unavailable": {"all": "数据类型未识别"}})

    # 大数据集降载：series matrix 直出表达矩阵（提交者已处理/RMA），供 limma 直连
    series_expr = None
    sm_gz = None
    for _r, _d, _fs in os.walk(raw_dir):
        for _fn in _fs:
            if _fn.lower() == f"{acc.lower()}_series_matrix.txt.gz":
                sm_gz = os.path.join(_r, _fn)
    if data_type == "microarray" and n_cel == 0 and sm_gz:
        try:
            import csv as _csv
            import gzip as _gz

            out_rel = os.path.join("inputs", "metadata", f"{acc}_expr_matrix.csv")
            out_abs = os.path.join(ws, out_rel)
            os.makedirs(os.path.dirname(out_abs), exist_ok=True)
            n_cols = 0
            with _gz.open(sm_gz, "rt", encoding="utf-8", errors="replace") as f, \
                 open(out_abs, "w", encoding="utf-8", newline="") as w:
                wr = _csv.writer(w)
                in_table = False
                for line in f:
                    if line.startswith("!series_matrix_table_begin"):
                        in_table = True
                        continue
                    if line.startswith("!series_matrix_table_end"):
                        break
                    if in_table:
                        row = line.rstrip("\n").split("\t")
                        n_cols = max(n_cols, len(row) - 1)
                        wr.writerow(row)
            series_expr = out_rel.replace("\\", "/")
            print(f"[{acc}] series matrix 直出表达矩阵：{out_rel}（{n_cols} 样本）")
        except Exception as exc:
            print(f"[{acc}] series matrix 解析失败：{exc}")

    doc = {
        "project_id": f"project_v2_e2e_{acc.lower()}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "dataset": acc,
        "source_meta": meta_path.replace("\\", "/"),
        "inputs": {
            "raw_dir": os.path.relpath(raw_dir, ws).replace("\\", "/"),
            "geo_title": meta.get("title"),
            "platform_id": meta.get("platform_id"),
            "organism": meta.get("organism"),
            "geo_type": meta.get("type"),
            "pubmed_id": meta.get("pubmed_id"),
            "n_samples_geo": meta.get("n_samples"),
            "n_cel_files": n_cel,
            "n_fastq_files": n_fastq,
            "series_matrix_expr": series_expr,
            },
        "data_type": data_type,
        "sample_size": meta.get("n_samples") or (n_cel or n_fastq),
        "group_inference": groups,
        "available_analyses": cat["available"],
        "unavailable_analyses": [{"name": k, "reason": v} for k, v in cat["unavailable"].items()],
        "recommendations": [],
    }

    if data_type == "microarray" and n_cel == 0:
        doc["recommendations"].append("未发现 CEL 文件，需确认 RAW.tar 是否已正确解压")
    if groups.get("method") == "unresolved":
        doc["recommendations"].append("分组未解析成功，P1 执行前必须人工确认分组")

    out_dir = os.path.join(ws, "analysis", "_index")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"data_availability_{acc}.yaml")
    with open(out, "w", encoding="utf-8") as f:
        yaml.safe_dump(doc, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    print(f"[{acc}] data_type={data_type}  n={doc['sample_size']}  CEL={n_cel}  FASTQ={n_fastq}")
    print(f"[{acc}] 分组：{groups.get('group_sizes', groups.get('groups'))}")
    print(f"[{acc}] 可用分析：{len(doc['available_analyses'])} / 不可用：{len(doc['unavailable_analyses'])}")
    print(f"[{acc}] 写入：{out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
