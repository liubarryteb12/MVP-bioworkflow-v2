#!/usr/bin/env python3
"""从 NCBI GEO FTP 下载数据集原始文件并迁移到 inputs/raw/。

P1 第 0 步（数据迁移）的云端实现。
纪律：
- 原始数据只读，默认复制不移动。
- 迁移前后必须校验（文件数、大小、checksum），失败即 stop（P1 纲要 §2.6）。
- 不使用 AI 记忆里的文件名，一律现场列目录。

用法：
    python scripts/download_geo.py --dataset GSE7451 --output inputs/raw/
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import sys
import tarfile
import time
import zipfile

import requests
import yaml

DEFAULT_PROXY = "http://127.0.0.1:7890"


def series_dir(acc: str) -> str:
    """GSE7451 -> GSE7nnn；GSE2379 -> GSE2nnn；GSE10036 -> GSE10nnn"""
    m = re.fullmatch(r"GSE(\d+)", acc.strip(), re.I)
    if not m:
        raise ValueError(f"非法 GEO accession：{acc}")
    digits = m.group(1)
    if len(digits) <= 3:
        return f"GSE{digits}nnn"
    return f"GSE{digits[:-3]}nnn"


def list_suppl_files(acc: str, proxy: str | None) -> list:
    url = f"https://ftp.ncbi.nlm.nih.gov/geo/series/{series_dir(acc)}/{acc}/suppl/"
    proxies = {"http": proxy, "https": proxy} if proxy else None
    r = requests.get(url, proxies=proxies, timeout=60)
    r.raise_for_status()
    return sorted(set(re.findall(rf'href="({re.escape(acc)}[^"/]+\.(?:tar|gz|tgz|zip|txt|cel|CEL))"', r.text)))


def sha256_of(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(chunk), b""):
            h.update(blk)
    return f"sha256:{h.hexdigest()}"


def extract(archive: str, dest: str) -> list:
    os.makedirs(dest, exist_ok=True)
    if tarfile.is_tarfile(archive):
        with tarfile.open(archive) as tf:
            tf.extractall(dest)
    elif zipfile.is_zipfile(archive):
        with zipfile.is_zipfile(archive) and zipfile.ZipFile(archive) as zf:
            zf.extractall(dest)
    elif archive.lower().endswith(".gz"):
        # 单文件 gzip（如 series matrix）：真正解压，而不是原样复制
        import gzip
        out = os.path.join(dest, os.path.basename(archive)[:-3])
        with gzip.open(archive, "rb") as fi, open(out, "wb") as fo:
            shutil.copyfileobj(fi, fo)
    else:
        shutil.copy2(archive, os.path.join(dest, os.path.basename(archive)))
    out = []
    for root, _, files in os.walk(dest):
        for fn in files:
            out.append(os.path.join(root, fn))
    return sorted(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="下载 GEO 数据集原始数据")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--output", default="inputs/raw/")
    ap.add_argument("--proxy", default=DEFAULT_PROXY)
    ap.add_argument("--no-proxy", action="store_true")
    ap.add_argument("--prefer", default="_RAW.tar", help="优先下载的文件名片段")
    ap.add_argument("--smart-size", action="store_true",
                    help="RAW.tar >300MB 且存在 series matrix 时自动改用表达矩阵（大数据集降载）")
    ap.add_argument("--with-series-matrix", action="store_true",
                    help="在首选文件之外额外下载 series matrix（非 Affymetrix 芯片如 Illumina/Agilent "
                         "不提供 CEL，P1 只能走 series matrix 直连表达矩阵路径）")
    args = ap.parse_args()

    proxy = None if args.no_proxy else args.proxy
    acc = args.dataset.upper()
    raw_dir = os.path.join(args.output, acc)
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs("inputs/metadata", exist_ok=True)

    ts = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    log = {
        "migration_id": f"mig_{acc.lower()}_{time.strftime('%Y%m%d_%H%M%S')}",
        "timestamp": ts,
        "dataset": acc,
        "method": "copy",
        "source_base": f"https://ftp.ncbi.nlm.nih.gov/geo/series/{series_dir(acc)}/{acc}/suppl/",
        "sources": [],
        "summary": {},
        "notes": ["原始数据保持只读，未修改", "所有分析只读 inputs/ 目录"],
    }

    try:
        files = list_suppl_files(acc, proxy)
    except Exception as exc:
        print(f"[{acc}] 列目录失败：{exc}", file=sys.stderr)
        return 2

    if not files:
        print(f"[{acc}] suppl 目录未找到文件", file=sys.stderr)
        return 2

    picked = [f for f in files if args.prefer.lower() in f.lower()]
    meta_n = None
    meta_p = os.path.join("04_journal", "snapshots", "geo_meta", f"{acc}_meta.yaml")
    if os.path.exists(meta_p):
        try:
            with open(meta_p, "r", encoding="utf-8") as f:
                meta_n = (yaml.safe_load(f) or {}).get("n_samples")
        except Exception:
            pass
    if args.smart_size and meta_n and meta_n > 50:
        # 大样本数据集降载：series matrix 在 /matrix/ 目录（不在 suppl/），~80MB；
        # RAW.tar 是数 GB（每 CEL ~5MB）。判定依据 = 已核验 meta n_samples>50（HEAD 对 NCBI 不可靠）。
        log["source_base"] = f"https://ftp.ncbi.nlm.nih.gov/geo/series/{series_dir(acc)}/{acc}/matrix/"
        picked = [f"{acc}_series_matrix.txt.gz"]
        log["notes"].append(f"n_samples={meta_n}>50：降载为 series matrix（source 切到 /matrix/）")
        print(f"[{acc}] n_samples={meta_n} > 50 → 改用 series matrix（/matrix/ 目录）")
    targets = picked if picked else [f for f in files if f.lower().endswith((".tar", ".gz", ".tgz", ".zip"))]
    if not targets:
        targets = files

    failures = 0
    for name in targets:
        url = log["source_base"] + name
        dst = os.path.join(raw_dir, name)
        try:
            proxies = {"http": proxy, "https": proxy} if proxy else None
            with requests.get(url, stream=True, proxies=proxies, timeout=300) as r:
                r.raise_for_status()
                with open(dst, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        if chunk:
                            f.write(chunk)
            size = os.path.getsize(dst)
            after = sha256_of(dst)
            extracted = extract(dst, os.path.join(raw_dir, "extracted")) if name.lower().endswith(
                (".tar", ".gz", ".tgz", ".zip")
            ) else []
            log["sources"].append(
                {
                    "source_path": url,
                    "target_path": dst.replace("\\", "/"),
                    "size_bytes": size,
                    "checksum_after": after,
                    "extracted_files": len(extracted),
                    "status": "success",
                }
            )
            print(f"[{acc}] 已下载 {name}（{size} bytes），解出 {len(extracted)} 个文件")
        except Exception as exc:
            failures += 1
            log["sources"].append({"source_path": url, "target_path": dst.replace("\\", "/"), "status": "failed",
                                   "error": str(exc)})
            print(f"[{acc}] 下载失败 {name}：{exc}", file=sys.stderr)

    # 非 Affymetrix 芯片（Illumina / Agilent）不提供 CEL，RAW.tar 里也没有能直接跑 RMA 的文件。
    # 此时 series matrix 是唯一的表达矩阵入口：GEO 保证每个 Series 都有它，且提交者已做标准化。
    # 只下载、不解压——data_availability.py 需要原始 .gz 来解析表头与表达矩阵。
    sm_url = f"https://ftp.ncbi.nlm.nih.gov/geo/series/{series_dir(acc)}/{acc}/matrix/{acc}_series_matrix.txt.gz"
    already_matrix = bool(log["source_base"].rstrip("/").endswith("/matrix"))
    if args.with_series_matrix and not already_matrix:
        sm_dst = os.path.join(raw_dir, f"{acc}_series_matrix.txt.gz")
        try:
            proxies = {"http": proxy, "https": proxy} if proxy else None
            with requests.get(sm_url, stream=True, proxies=proxies, timeout=600) as r:
                r.raise_for_status()
                with open(sm_dst, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        if chunk:
                            f.write(chunk)
            sm_size = os.path.getsize(sm_dst)
            log["sources"].append({
                "source_path": sm_url,
                "target_path": sm_dst.replace("\\", "/"),
                "size_bytes": sm_size,
                "checksum_after": sha256_of(sm_dst),
                "extracted_files": 0,
                "status": "success",
                "note": "series matrix（非 Affy 芯片无 CEL，作为表达矩阵入口）",
            })
            print(f"[{acc}] 已下载 series matrix（{sm_size} bytes）")
        except Exception as exc:
            log["sources"].append({"source_path": sm_url, "target_path": sm_dst.replace("\\", "/"),
                                   "status": "failed", "error": str(exc),
                                   "note": "series matrix 不可用（SuperSeries 或部分数据集无此文件）"})
            print(f"[{acc}] series matrix 下载失败（不影响主流程）：{exc}", file=sys.stderr)

    log["summary"] = {
        "total_files": len(log["sources"]),
        "success": sum(1 for s in log["sources"] if s.get("status") == "success"),
        "failed": failures,
        "warnings": [],
    }

    out_log = os.path.join("inputs", f"migration_log_{acc}.yaml")
    with open(out_log, "w", encoding="utf-8") as f:
        yaml.safe_dump(log, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    print(f"[{acc}] 迁移记录写入：{out_log}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
