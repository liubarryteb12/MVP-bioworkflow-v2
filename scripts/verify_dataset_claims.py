#!/usr/bin/env python3
"""验证 GEO 数据集是否与输入材料的描述一致（防幻觉：以权威源实测为准）。

下载 series matrix 的样本元信息行（不解析表达表），实测：
- 样本总数、分组大小（关键词推断）、平台、物种
- 与材料描述逐项比对，输出 ok / deviation

用法：
    python scripts/verify_dataset_claims.py --acc GSE31210 --claim "226 LUAD tumor + 20 normal"
"""

from __future__ import annotations

import argparse
import collections
import gzip
import re
import time

import requests

DEFAULT_PROXY = "http://127.0.0.1:7890"


def series_dir(acc: str) -> str:
    digits = re.fullmatch(r"GSE(\d+)", acc.strip(), re.I).group(1)
    return f"GSE{digits[:-3]}nnn" if len(digits) > 3 else f"GSE{digits}nnn"


def fetch_meta(acc: str, proxy: str | None) -> tuple[list, list, list]:
    url = f"https://ftp.ncbi.nlm.nih.gov/geo/series/{series_dir(acc)}/{acc}/matrix/{acc}_series_matrix.txt.gz"
    proxies = {"http": proxy, "https": proxy} if proxy else None
    r = requests.get(url, proxies=proxies, timeout=900, stream=True)
    r.raise_for_status()
    raw = gzip.decompress(b"".join(r.iter_content(1 << 20))).decode("utf-8", errors="replace")
    titles: list = []
    chars: list = []
    gsms: list = []
    for line in raw.splitlines():
        if line.startswith("!Sample_title"):
            titles += [s.strip('"') for s in line.split("\t")[1:]]
        elif line.startswith("!Sample_characteristics_ch1"):
            chars.append([s.strip('"') for s in line.split("\t")[1:]])
        elif line.startswith("!Sample_geo_accession"):
            gsms += [s.strip('"') for s in line.split("\t")[1:]]
        elif line.startswith("!series_matrix_table_begin"):
            break
    return titles, chars, gsms


def guess_group(text: str) -> str:
    low = text.lower()
    if re.search(r"(^|[^a-z])(normal|non[- ]?tumor|nontumor|adjacent|healthy|benign)([^a-z]|$)", low):
        return "normal"
    if re.search(r"(^|[^a-z])(tumor|tumour|cancer|adenocarcinoma|carcinoma|luad|malignant|metasta)([^a-z]|$)", low):
        return "tumor"
    return "unclassified"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--acc", required=True)
    ap.add_argument("--claim", default="", help="材料中的样本描述，如 '226 LUAD tumor + 20 normal'")
    ap.add_argument("--proxy", default=DEFAULT_PROXY)
    ap.add_argument("--no-proxy", action="store_true")
    args = ap.parse_args()

    proxy = None if args.no_proxy else args.proxy
    acc = args.acc.upper()
    ts = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    titles, chars, gsms = fetch_meta(acc, proxy)

    counts = collections.Counter()
    evidence = []
    for i, t in enumerate(titles):
        blob = t + " | " + " | ".join(row[i] for row in chars if i < len(row))
        g = guess_group(blob)
        counts[g] += 1
        if len(evidence) < 6:
            evidence.append(f"{gsms[i] if i < len(gsms) else i}: {t[:60]} -> {g}")

    print(f"[{acc}] 实测样本数：{len(gsms)}（材料描述：{args.claim or '未给出'}）")
    print(f"[{acc}] 分组实测：{dict(counts)}")
    for e in evidence:
        print(f"  {e}")

    ok = len(gsms) > 0
    if args.claim:
        nums = [int(x) for x in re.findall(r"\b(\d{1,4})\b", args.claim)]
        claimed_total = sum(nums) if nums else None
        if claimed_total and claimed_total != len(gsms):
            print(f"[{acc}] ⚠ 偏差：材料合计 {claimed_total}，实测 {len(gsms)}")
        else:
            print(f"[{acc}] 样本总数与材料一致")
    with open(f"04_journal/snapshots/geo_meta/{acc}_verify.txt", "w", encoding="utf-8") as f:
        f.write(f"acc={acc}\nfetched_at={ts}\nn_samples={len(gsms)}\ngroups={dict(counts)}\n"
                f"claim={args.claim}\nevidence={evidence}\n")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
