#!/usr/bin/env python3
"""从 NCBI GEO 抓取数据集元信息快照。

用途：P4-a 题材初判的输入。
纪律：P4 纲要 §1.4 —— 数据必须可验证，不得依赖 AI 记忆。
      因此每个数据集的原始 GEO 记录都要落盘留痕，并附抓取时间与来源 URL。

用法：
    python scripts/fetch_geo_meta.py --acc GSE7451 --acc GSE2379 --acc GSE10036
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List

import requests
import yaml

ACC_URL = "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi"
DEFAULT_PROXY = "http://127.0.0.1:7890"


def fetch_brief(acc: str, proxy: str | None, timeout: int = 60) -> str:
    proxies = {"http": proxy, "https": proxy} if proxy else None
    r = requests.get(
        ACC_URL,
        params={"acc": acc, "targ": "self", "form": "text", "view": "brief"},
        proxies=proxies,
        timeout=timeout,
    )
    r.raise_for_status()
    r.encoding = "utf-8"
    return r.text


def parse_brief(text: str) -> Dict[str, Any]:
    meta: Dict[str, Any] = {
        "accession": None,
        "title": None,
        "summary": [],
        "overall_design": [],
        "type": None,
        "platform_id": None,
        "organism": None,
        "pubmed_id": None,
        "sample_ids": [],
        "supplementary_files": [],
        "status": None,
        "submission_date": None,
    }
    for line in text.splitlines():
        if not line.startswith("!") and not line.startswith("^"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if key == "^SERIES":
            meta["accession"] = val
        elif key == "!Series_title":
            meta["title"] = val
        elif key == "!Series_summary":
            meta["summary"].append(val)
        elif key == "!Series_overall_design":
            meta["overall_design"].append(val)
        elif key == "!Series_type":
            meta["type"] = val
        elif key == "!Series_platform_id":
            meta["platform_id"] = val
        elif key == "!Series_sample_organism":
            meta["organism"] = val
        elif key == "!Series_pubmed_id":
            meta["pubmed_id"] = val
        elif key == "!Series_status":
            meta["status"] = val
        elif key == "!Series_submission_date":
            meta["submission_date"] = val
        elif key == "!Series_sample_id":
            meta["sample_ids"].append(val)
        elif key == "!Series_supplementary_file":
            meta["supplementary_files"].append(val)
    meta["n_samples"] = len(meta["sample_ids"])
    return meta


def main() -> int:
    ap = argparse.ArgumentParser(description="抓取 GEO 数据集元信息快照")
    ap.add_argument("--acc", action="append", required=True, help="GEO accession，可多次传入")
    ap.add_argument("--outdir", default="04_journal/snapshots/geo_meta")
    ap.add_argument("--proxy", default=DEFAULT_PROXY)
    ap.add_argument("--no-proxy", action="store_true")
    args = ap.parse_args()

    proxy = None if args.no_proxy else args.proxy
    os.makedirs(args.outdir, exist_ok=True)
    index: List[Dict[str, Any]] = []

    for acc in args.acc:
        ts = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        try:
            raw = fetch_brief(acc, proxy)
        except Exception as exc:
            print(f"[{acc}] 抓取失败：{exc}", file=sys.stderr)
            index.append({"accession": acc, "status": "failed", "error": str(exc)})
            continue

        raw_path = os.path.join(args.outdir, f"{acc}_brief.txt")
        with open(raw_path, "w", encoding="utf-8") as f:
            f.write(raw)

        meta = parse_brief(raw)
        meta["source_url"] = f"{ACC_URL}?acc={acc}&targ=self&form=text&view=brief"
        meta["fetched_at"] = ts
        meta["raw_snapshot"] = raw_path.replace("\\", "/")

        yaml_path = os.path.join(args.outdir, f"{acc}_meta.yaml")
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(meta, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

        index.append(
            {
                "accession": acc,
                "status": "ok",
                "title": meta["title"],
                "n_samples": meta["n_samples"],
                "platform_id": meta["platform_id"],
                "organism": meta["organism"],
                "type": meta["type"],
                "pubmed_id": meta["pubmed_id"],
                "yaml": yaml_path.replace("\\", "/"),
            }
        )
        print(f"[{acc}] {meta['n_samples']} samples / {meta['platform_id']} / {meta['type']}")
        print(f"[{acc}] title: {meta['title']}")

    with open(os.path.join(args.outdir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    return 0 if all(i["status"] == "ok" for i in index) else 1


if __name__ == "__main__":
    raise SystemExit(main())
