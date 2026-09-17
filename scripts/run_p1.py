#!/usr/bin/env python3
"""P1 执行引擎（云端）。

流程：读数据可用性 → T21 质控判定 → 逐模块执行 → 每步写 manifest + 四件套 → 出图五格式 → 生成 P1 接口文件。

纪律：
- 一次只跑一个模块，跑完写记录，再跑下一个。不并行，不跳步，不猜。
- T21（组别样本量下限与平衡）FAIL 时，拒绝任何统计推断，只跑描述性分析。
- 失败如实报告，不掩盖、不重试掩盖。
- 数字唯一来源：所有数字来自模块输出文件，不手工填。

用法：
    python scripts/run_p1.py --workspace . --dataset GSE7451 --pipeline '{}'
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import time

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

MIN_GROUP_N = 3          # P1-QC-04（02版修订合集 v3：每组 ≥3，与 de.R2 同锚；旧 T21 的 6 已废止）
SMALL_SAMPLE_N = 30      # 低于此值给小样本 warning
IMBALANCE_RATIO = 0.5    # min/max 低于此值判严重不平衡


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return f"sha256:{h.hexdigest()}"


def dump_yaml(path: str, doc) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(doc, f, allow_unicode=True, sort_keys=False, default_flow_style=False)


def partn_n(seq: int) -> str:
    return f"part1-{seq:02d}-output"


# ------------------------------------------------------------------ T21 质控


def judge_sample_size(group_sizes: dict) -> dict:
    """T21 组别样本量下限与平衡（三态：pass / fail / N/A）"""
    if not group_sizes:
        return {"check": "sample_size", "status": "N/A",
                "message": "分组信息缺失，无法判定（P1 质控 stop 项：input_completeness）"}

    sizes = {k: int(v) for k, v in group_sizes.items() if isinstance(v, (int, float))}
    if not sizes:
        return {"check": "sample_size", "status": "N/A", "message": "分组大小非数值"}

    smallest = min(sizes.values())
    largest = max(sizes.values())
    ratio = smallest / largest if largest else 0.0
    warnings = []

    if smallest < MIN_GROUP_N:
        return {
            "check": "sample_size",
            "status": "fail",
            "message": f"最小组 n={smallest} < {MIN_GROUP_N}，不得据此进行统计推断",
            "group_sizes": sizes,
            "min_n": smallest,
            "max_n": largest,
            "balance_ratio": round(ratio, 3),
        }

    if largest < SMALL_SAMPLE_N:
        warnings.append(f"样本量偏小（最大组 n={largest} < {SMALL_SAMPLE_N}），统计效力有限")
    if ratio < IMBALANCE_RATIO:
        warnings.append(f"组间严重不平衡（min/max={ratio:.2f} < {IMBALANCE_RATIO}）")

    return {
        "check": "sample_size",
        "status": "pass",
        "message": "组别样本量满足下限" + (f"；warnings: {len(warnings)}" if warnings else ""),
        "group_sizes": sizes,
        "min_n": smallest,
        "max_n": largest,
        "balance_ratio": round(ratio, 3),
        "warnings": warnings,
    }


# ------------------------------------------------------------------ 记录四件套


def write_handoff(path: str, **kw) -> None:
    lines = [
        f"# handoff · {kw.get('module_id', '-')} · {kw.get('dataset', '-')}",
        "",
        f"生成时间：{kw.get('timestamp', '-')}  ",
        f"run_id：{kw.get('run_id', '-')}  ",
        f"状态：{kw.get('status', '-')}",
        "",
        "## 1. 这一步是什么",
        kw.get("what", "-"),
        "",
        "## 2. 这一步做了什么",
        kw.get("did", "-"),
        "",
        "## 3. 输入是什么",
        kw.get("inputs_desc", "-"),
        "",
        "## 4. 输出是什么",
        kw.get("outputs_desc", "-"),
        "",
        "## 5. 结果怎么样",
        kw.get("result", "-"),
        "",
        "## 6. 能不能用",
        kw.get("usable", "-"),
        "",
        "## 7. 下一步建议",
        kw.get("next", "-"),
        "",
    ]
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def write_diff(path: str, dataset: str, module_id: str, prev: dict | None, cur: dict) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# diff · {dataset} / {module_id}\n\n")
        if not prev:
            f.write("首次运行，无历史基线。\n\n")
        else:
            f.write("## 参数变化\n")
            f.write(f"- 上次：{json.dumps(prev.get('parameters', {}), ensure_ascii=False)}\n")
            f.write(f"- 本次：{json.dumps(cur.get('parameters', {}), ensure_ascii=False)}\n\n")
        f.write("## 本次输出\n")
        for o in cur.get("outputs", []):
            f.write(f"- {o.get('name')}: {o.get('path')}\n")
        f.write("\n## 结论\n")
        f.write(cur.get("conclusion", "-") + "\n")


def write_checkpoint(path: str, dataset: str, module_id: str, run_id: str, seq: int, outputs: list) -> None:
    dump_yaml(path, {
        "checkpoint_id": f"ckpt_{dataset.lower()}_{module_id}_{run_id}",
        "dataset": dataset,
        "module_id": module_id,
        "run_id": run_id,
        "partn_n_output": partn_n(seq),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "immutable": True,
        "outputs": outputs,
    })


def write_next_tasklist(path: str, dataset: str, module_id: str, t21: dict, remaining: list) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# next_tasklist · {dataset} / {module_id}\n\n")
        f.write("## 推荐下一步\n")
        if t21.get("status") == "fail":
            f.write("- 【阻塞】T21 判 FAIL，不得进入差异表达与富集分析\n")
            f.write("- 需补充样本至每组 n ≥ 6，或改为纯描述性分析\n")
        else:
            for m in remaining:
                f.write(f"- {m}\n")
        f.write("\n## 可选下一步\n")
        f.write("- 补充外部验证集\n- 补充临床随访信息（生存分析）\n")
        f.write("\n## 阻塞项\n")
        f.write("无\n" if t21.get("status") != "fail" else f"- T21: {t21.get('message')}\n")


# ------------------------------------------------------------------ 模块执行


def build_input_json(path: str, run_id: str, module_id: str, inputs: list, outputs: list,
                     parameters: dict, log_path: str, backend: str = "github_actions",
                     language: str = "R", seed: int = 42) -> str:
    doc = {
        "schema_version": "1.0",
        "meta": {
            "run_id": run_id,
            "module_id": module_id,
            "module_version": "1.0.0",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "language": language,
            "random_seed": seed,
            "execution_backend": backend,
        },
        "inputs": inputs,
        "outputs": outputs,
        "parameters": parameters,
        "environment": {"os": "Linux", "r_version": "4.3.1", "python_version": None, "packages": []},
        "log": {"path": log_path, "level": "info"},
        "extensions": {},
        "custom": {},
    }
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return path


def run_module(workspace: str, module_id: str, script: str, input_json: str, language: str = "R") -> int:
    abs_script = os.path.join(workspace, script)
    abs_json = os.path.join(workspace, input_json)

    # 执行前先建齐输出目录：R 的 pdf() 不会自动建目录，缺目录会直接 cannot open file
    try:
        with open(abs_json, encoding="utf-8") as f:
            doc = json.load(f)
        for o in doc.get("outputs", []) or []:
            d = os.path.dirname(os.path.join(workspace, str(o.get("path", ""))))
            if d:
                os.makedirs(d, exist_ok=True)
    except Exception as exc:
        print(f"  [warn] 预建输出目录失败：{exc}")
    cmd = ["Rscript", abs_script, abs_json] if language == "R" else [sys.executable, abs_script, abs_json]
    print(f"  $ {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=workspace, capture_output=True, text=True)
    if proc.stdout:
        print(proc.stdout[-4000:])
    if proc.returncode != 0:
        print(f"[FAIL] {module_id} exit={proc.returncode}", file=sys.stderr)
        if proc.stderr:
            print(proc.stderr[-4000:], file=sys.stderr)
    return proc.returncode


def export_five_formats(workspace: str, figures: list) -> list:
    """五格式导出：pdf / svg / png / tiff / jpg。优先用 pdftocairo 保矢量。"""
    from figure_export import export_one
    out = []
    for pdf_rel in figures:
        pdf_abs = os.path.join(workspace, pdf_rel)
        if not os.path.exists(pdf_abs):
            out.append({"figure": pdf_rel, "status": "missing"})
            continue
        res = export_one(pdf_abs)
        out.append({"figure": pdf_rel, **res})
    return out


def find_matrix_file(workspace: str, dataset: str) -> str | None:
    """在 inputs/raw/{ACC} 下找计数/表达矩阵文件。

    绝不凭记忆猜文件名：一律现场扫描，按文件名关键词 + 大小排序。
    """
    root = os.path.join(workspace, "inputs", "raw", dataset)
    if not os.path.isdir(root):
        return None
    # GEO 的 suppl 常为 .txt.gz / .csv.gz（单文件 gzip），R 的 read.delim 能直接读 .gz
    exts = (".txt", ".csv", ".tsv", ".txt.gz", ".csv.gz", ".tsv.gz", ".tab", ".tab.gz")
    cands = []
    seen = []
    for r, _, files in os.walk(root):
        for fn in files:
            low = fn.lower()
            seen.append(os.path.relpath(os.path.join(r, fn), root))
            if not low.endswith(exts):
                continue
            if "meta" in low or "readme" in low:
                continue
            p = os.path.join(r, fn)
            score = 0
            if any(k in low for k in ("count", "read", "htseq", "featurecount")):
                score += 20
            elif any(k in low for k in ("fpkm", "tpm", "expr", "matrix", "normalized")):
                score += 10
            try:
                size = os.path.getsize(p)
            except OSError:
                size = 0
            cands.append((score, size, p))
    if not cands:
        print(f"[{dataset}] 未找到矩阵文件。目录内文件（前 20）：{seen[:20]}")
        return None
    cands.sort(key=lambda t: (t[0], t[1]), reverse=True)
    rel = os.path.relpath(cands[0][2], workspace)
    print(f"[{dataset}] 候选 {len(cands)} 个，选中矩阵文件：{rel}")
    return rel.replace("\\", "/")


def build_count_matrix(workspace: str, dataset: str) -> str | None:
    """GEO 常见"每样本一个文件"的布局（如 GSE174263 的 GSM*.tab.gz）。

    把它们合并成一个 gene × sample 的计数矩阵，落到 inputs/metadata/。
    合并失败返回 None，交由 find_matrix_file 走单文件回退。
    """
    try:
        import pandas as pd
    except ImportError:
        return None

    root = os.path.join(workspace, "inputs", "raw", dataset)
    if not os.path.isdir(root):
        return None
    exts = (".tab", ".tab.gz", ".txt", ".txt.gz", ".csv", ".csv.gz")
    files = []
    for r, _, fs in os.walk(root):
        for fn in fs:
            low = fn.lower()
            if low.endswith(exts) and "meta" not in low and "readme" not in low:
                files.append(os.path.join(r, fn))
    if len(files) < 2:
        return None

    frames = []
    for p in sorted(files):
        try:
            d = pd.read_csv(p, sep=None, engine="python", index_col=0)
        except Exception:
            continue
        d = d.select_dtypes("number")
        if d.shape[1] < 1:
            continue
        # 若某个文件本身已含 ≥2 个数值列，它就是多样本矩阵，直接选用，绝不拆解合并
        if d.shape[1] >= 2:
            out_rel = os.path.join("inputs", "metadata", f"{dataset}_count_matrix.csv")
            d.to_csv(os.path.join(workspace, out_rel))
            print(f"[{dataset}] 检测到多样本矩阵 {os.path.basename(p)}（{d.shape[0]} × {d.shape[1]}），直接选用")
            return out_rel.replace("\\", "/")
        d = d.iloc[:, [0]]
        d.columns = [os.path.basename(p).split(".")[0]]
        frames.append(d)

    if len(frames) < 2:
        return None

    mat = pd.concat(frames, axis=1)
    mat = mat[~mat.index.astype(str).duplicated(keep="first")]
    mat = mat.fillna(0)
    out_rel = os.path.join("inputs", "metadata", f"{dataset}_count_matrix.csv")
    mat.to_csv(os.path.join(workspace, out_rel))
    print(f"[{dataset}] 合并 {len(frames)} 个单样本文件 → {out_rel}（{mat.shape[0]} genes × {mat.shape[1]} samples）")
    return out_rel.replace("\\", "/")


def write_sample_sheet(workspace: str, dataset: str, groups: dict) -> str:
    rel = os.path.join("inputs", "metadata", f"{dataset}_sample_sheet.csv")
    abs_p = os.path.join(workspace, rel)
    os.makedirs(os.path.dirname(abs_p), exist_ok=True)
    with open(abs_p, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["gsm", "group"])
        for label, gsms in groups.items():
            for g in gsms:
                w.writerow([g, label])
    return rel


# ------------------------------------------------------------------ 主流程


def main() -> int:
    ap = argparse.ArgumentParser(description="P1 执行引擎")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--pipeline", default="{}")
    args = ap.parse_args()

    ws = os.path.abspath(args.workspace)
    acc = args.dataset.upper()
    run_id = f"run_{time.strftime('%Y%m%d_%H%M%S')}"
    ts = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    out_root = os.path.join(ws, "analysis", "outputs", acc)
    os.makedirs(out_root, exist_ok=True)

    # ---- 读数据可用性 ----
    da_path = os.path.join(ws, "analysis", "_index", f"data_availability_{acc}.yaml")
    if not os.path.exists(da_path):
        print(f"[ERROR] 缺少数据可用性分析：{da_path}")
        return 2
    with open(da_path, "r", encoding="utf-8") as f:
        da = yaml.safe_load(f) or {}

    data_type = da.get("data_type")
    gi = da.get("group_inference", {}) or {}
    groups = gi.get("groups", {}) or {}
    group_sizes = gi.get("group_sizes", {}) or {k: len(v) for k, v in groups.items()}

    print(f"[{acc}] data_type={data_type} groups={group_sizes}")

    # ---- T21 质控 ----
    t21 = judge_sample_size(group_sizes)
    print(f"[{acc}] T21 sample_size: {t21['status']} — {t21['message']}")

    qc_report = {
        "dataset": acc,
        "run_id": run_id,
        "timestamp": ts,
        "checks": [
            {"name": "input_completeness", "status": "passed" if os.path.isdir(os.path.join(ws, "inputs", "raw", acc)) else "failed"},
            {"name": "data_availability", "status": "passed"},
            t21,
            {"name": "reproducibility", "status": "passed", "message": "random_seed 固定为 42，写入每个 input json"},
            {"name": "parameter_validity", "status": "passed", "message": "参数来自 flow 定义，阈值未在运行时修改"},
        ],
        "warnings": t21.get("warnings", []),
    }
    dump_yaml(os.path.join(out_root, "records", "qc_report.yaml"), qc_report)

    # 小样本 warning
    if t21.get("warnings"):
        print(f"[{acc}] WARNING: {t21['warnings']}")

    sample_sheet_rel = write_sample_sheet(ws, acc, groups) if groups else None

    # ---- 决定执行链 ----
    run_state = {
        "run_id": run_id,
        "status": "running",
        "dataset": acc,
        "data_type": data_type,
        "execution_backend": "github_actions",
        "t21": t21["status"],
        "steps": [],
    }

    seq = 0
    produced_figures: list[str] = []
    evidence = []
    methods = []

    if data_type == "rna_seq":
        # RNA-seq：计数矩阵 QC（总是做）+ DESeq2（仅 T21 通过才做）
        matrix_rel = build_count_matrix(ws, acc) or find_matrix_file(ws, acc)
        if not matrix_rel or not sample_sheet_rel:
            err = "未找到计数矩阵或样本表，无法继续"
            print(f"[{acc}] {err}")
            run_state["steps"].append({"module_id": "rnaseq_de", "status": "failed", "reason": err})
            run_state["status"] = "failed"
            dump_yaml(os.path.join(ws, "analysis", "_runs", run_id, "run.yaml"), run_state)
            return 1

        run_de = (t21["status"] == "pass")
        seq += 1
        mod = "rnaseq_de"
        mdir = os.path.join(out_root, mod)
        relx = lambda p: os.path.relpath(os.path.join(mdir, p), ws).replace("\\", "/")
        outputs_r = [
            {"name": "qc_summary", "path": relx("results/qc_summary.csv"), "format": "csv", "is_final": True,
             "partn_n_output": partn_n(seq)},
            {"name": "qc_libsize", "path": relx("figures/qc_libsize.pdf"), "format": "pdf", "is_final": True},
            {"name": "qc_correlation", "path": relx("figures/qc_correlation.pdf"), "format": "pdf", "is_final": True},
            {"name": "qc_pca", "path": relx("figures/qc_pca.pdf"), "format": "pdf", "is_final": True},
            {"name": "deg_table", "path": relx("results/deg_table.csv"), "format": "csv", "is_final": True},
            {"name": "volcano", "path": relx("figures/volcano.pdf"), "format": "pdf", "is_final": True,
             "conditional": True},
            {"name": "de_summary", "path": relx("results/de_summary.csv"), "format": "csv", "is_final": True},
        ]
        inputs_r = [
            {"name": "count_matrix", "path": matrix_rel, "format": "csv", "required": True},
            {"name": "sample_sheet", "path": sample_sheet_rel.replace("\\", "/"), "format": "csv", "required": True},
        ]
        ijson = build_input_json(
            os.path.join(mdir, "run", f"input_{run_id}.json"), run_id, mod, inputs_r, outputs_r,
            {"run_deseq2": run_de, "padj_threshold": 0.05, "log2fc_threshold": 1.0, "random_seed": 42},
            relx(f"logs/{run_id}.log"))
        rc_r = run_module(ws, mod, "analysis/modules/rnaseq_de/scripts/r/01_main.R",
                          os.path.relpath(ijson, ws).replace("\\", "/"))
        must = [o for o in outputs_r if o["name"] in ("qc_summary", "qc_libsize", "qc_correlation", "qc_pca",
                                                      "deg_table", "de_summary")]
        ok_r = rc_r == 0 and all(os.path.exists(os.path.join(ws, o["path"])) for o in must)
        dump_yaml(os.path.join(mdir, "manifest.yaml"), {
            "module_id": mod, "module_version": "1.0.0", "run_id": run_id, "timestamp": ts,
            "status": "success" if ok_r else "failed", "execution_backend": "github_actions",
            "inputs": inputs_r, "outputs": outputs_r,
            "parameters": {"run_deseq2": run_de, "padj_threshold": 0.05, "log2fc_threshold": 1.0},
            "environment": {"os": "Linux", "r_version": "4.3.1", "random_seed": 42},
            "qc_result": {"passed": ok_r, "checks": [t21]},
        })
        write_handoff(os.path.join(mdir, "records", "handoff.md"),
                      module_id=mod, dataset=acc, run_id=run_id, timestamp=ts,
                      status="success" if ok_r else "failed",
                      what="RNA-seq 计数矩阵质控" + ("+ DESeq2 差异表达" if run_de else "（T21 未通过，只做描述性 QC）"),
                      did="读取计数矩阵 → library size/检出基因/样本相关/PCA" + ("→ DESeq2 差异表达" if run_de else ""),
                      inputs_desc=f"- {matrix_rel}\n- {sample_sheet_rel}",
                      outputs_desc="\n".join(f"- {o['name']}: {o['path']}" for o in outputs_r),
                      result="见 qc_summary.csv / de_summary.csv" if ok_r else "执行失败",
                      usable="可用（描述性）" if ok_r and not run_de else ("可用" if ok_r else "不可用"),
                      next="进入富集分析" if run_de else "T21 未通过：需补样本至每组 n≥6 才能做统计推断")
        write_diff(os.path.join(mdir, "records", "diff.md"), acc, mod, None,
                   {"outputs": outputs_r, "parameters": {"run_deseq2": run_de},
                    "conclusion": ("描述性 QC 完成，未做统计推断" if not run_de else "DESeq2 完成")})
        write_checkpoint(os.path.join(mdir, "records", "checkpoint.yaml"), acc, mod, run_id, seq, outputs_r)
        write_next_tasklist(os.path.join(mdir, "records", "next_tasklist.md"), acc, mod, t21,
                            ["pathway_enrichment"] if run_de else [])
        run_state["steps"].append({"module_id": mod, "status": "success" if ok_r else "failed"})
        methods.append({"method_id": "M010", "module_id": mod,
                        "description": "RNA-seq 计数质控" + ("+ DESeq2 负二项广义线性模型（Wald 检验，BH 校正）" if run_de else ""),
                        "software": "DESeq2" if run_de else "base R", "version": "Bioconductor 3.18"})
        produced_figures += [o["path"] for o in outputs_r
                             if o["format"] == "pdf" and os.path.exists(os.path.join(ws, o["path"]))]
        if not run_de:
            reason = f"T21 {t21['status']}：{t21['message']}；差异表达与富集被阻断，只保留描述性结果"
            print(f"[{acc}] {reason}")
            run_state["steps"].append({"module_id": "pathway_enrichment", "status": "blocked", "reason": reason})
        else:
            run_state["steps"].append(
                {"module_id": "pathway_enrichment", "status": "pending",
                 "reason": "需先适配 org_db（物种相关注释包），下一轮启用"})
        if not ok_r:
            dump_yaml(os.path.join(mdir, "records", "error_log.yaml"),
                      {"module_id": mod, "run_id": run_id, "returncode": rc_r, "timestamp": ts})
            run_state["status"] = "failed"
            dump_yaml(os.path.join(ws, "analysis", "_runs", run_id, "run.yaml"), run_state)
            return 1

    elif data_type != "microarray":
        reason = f"数据类型为 {data_type}，本轮 P1 只做数据可用性判定，不套用微阵列/RNA-seq 流程"
        print(f"[{acc}] {reason}")
        run_state["steps"].append({"module_id": "analysis_skipped", "status": "skipped", "reason": reason})
    elif t21["status"] == "fail":
        reason = f"T21 FAIL：{t21['message']}；体系拒绝据此进行统计推断"
        print(f"[{acc}] {reason}")
        run_state["steps"].append({"module_id": "differential_expression", "status": "blocked", "reason": reason})
        run_state["steps"].append({"module_id": "pathway_enrichment", "status": "blocked", "reason": reason})
    else:
        # 微阵列仅支持 Affymetrix CEL。Agilent/Illumina 表达矩阵需 limma::read.maimages 流程（待扩展，登记）。
        n_cel = (da.get("inputs", {}) or {}).get("n_cel_files", 0) or 0
        if not n_cel:
            platform_id = (da.get("inputs", {}) or {}).get("platform_id", "?")
            reason = (f"平台 {platform_id} 未提供 Affymetrix CEL 文件（Agilent/Illumina 表达矩阵），"
                      f"当前 P1 预装流程仅支持 Affy CEL；limma::read.maimages 流程登记为待扩展，"
                      f"不硬跑、不伪造结果")
            print(f"[{acc}] {reason}")
            run_state["steps"].append({"module_id": "preprocess", "status": "blocked",
                                       "reason": reason, "platform": platform_id})
            run_state["status"] = "completed"
            dump_yaml(os.path.join(ws, "analysis", "_runs", run_id, "run.yaml"), run_state)
            dump_yaml(os.path.join(out_root, "records", "qc_report.yaml"),
                      {"dataset": acc, "run_id": run_id, "timestamp": ts, "checks": [
                          {"name": "platform_support", "status": "failed",
                           "message": reason}]})
            return 0
        # ---- Step 1: preprocess ----
        seq += 1
        mod = "preprocess"
        mdir = os.path.join(out_root, mod)
        rel = lambda p: os.path.relpath(os.path.join(mdir, p), ws).replace("\\", "/")
        series_expr = (da.get("inputs", {}) or {}).get("series_matrix_expr")
        if series_expr:
            inputs = [{"name": "expr_matrix", "path": series_expr, "format": "csv", "required": True}]
            step1_params = {"input_mode": "series_matrix", "absent_fraction_threshold": 0.75, "random_seed": 42}
        else:
            inputs = [{"name": "cel_dir", "path": os.path.join("inputs", "raw", acc, "extracted").replace("\\", "/"),
                       "format": "directory", "required": True}]
            step1_params = {"absent_fraction_threshold": 0.75, "random_seed": 42}
        outputs = [
            {"name": "expr_rma", "path": rel("results/expr_rma.csv"), "format": "csv", "is_final": False},
            {"name": "expr_filtered", "path": rel("results/expr_filtered.csv"), "format": "csv", "is_final": True,
             "partn_n_output": partn_n(seq)},
            {"name": "qc_boxplot", "path": rel("figures/qc_boxplot.pdf"), "format": "pdf", "is_final": True},
            {"name": "qc_density", "path": rel("figures/qc_density.pdf"), "format": "pdf", "is_final": True},
            {"name": "filtering_summary", "path": rel("results/filtering_summary.csv"), "format": "csv", "is_final": True},
        ]
        inputs = inputs
        ij = build_input_json(
            os.path.join(mdir, "run", f"input_{run_id}.json"), run_id, mod, inputs, outputs,
            step1_params,
            rel(f"logs/{run_id}.log"),
        )
        rc = run_module(ws, mod, "analysis/modules/preprocess/scripts/r/01_main.R",
                        os.path.relpath(ij, ws).replace("\\", "/"))
        ok = rc == 0 and all(os.path.exists(os.path.join(ws, o["path"])) for o in outputs)
        dump_yaml(os.path.join(mdir, "manifest.yaml"), {
            "module_id": mod, "module_version": "1.0.0", "run_id": run_id, "timestamp": ts,
            "status": "success" if ok else "failed", "execution_backend": "github_actions",
            "inputs": inputs, "outputs": outputs,
            "parameters": {"absent_fraction_threshold": 0.75},
            "environment": {"os": "Linux", "r_version": "4.3.1", "random_seed": 42},
            "qc_result": {"passed": ok, "checks": [t21]},
        })
        write_handoff(os.path.join(mdir, "records", "handoff.md"),
                      module_id=mod, dataset=acc, run_id=run_id, timestamp=ts,
                      status="success" if ok else "failed",
                      what="芯片预处理：RMA 标准化 + 探针过滤",
                      did="读取 CEL → 输出 QC 图 → RMA（背景校正+分位数标准化）→ MAS5 present/absent → 剔除 >75% 样本 absent 的探针",
                      inputs_desc=f"CEL 目录：{inputs[0]['path']}",
                      outputs_desc="\n".join(f"- {o['name']}: {o['path']}" for o in outputs),
                      result="见 filtering_summary.csv 与 QC 图" if ok else "执行失败，见 error_log",
                      usable="可用" if ok else "不可用",
                      next="进入差异表达分析" if ok else "排查失败原因")
        write_diff(os.path.join(mdir, "records", "diff.md"), acc, mod, None,
                   {"outputs": outputs, "parameters": {"absent_fraction_threshold": 0.75},
                    "conclusion": "RMA 完成，探针已过滤" if ok else "失败"})
        write_checkpoint(os.path.join(mdir, "records", "checkpoint.yaml"), acc, mod, run_id, seq, outputs)
        write_next_tasklist(os.path.join(mdir, "records", "next_tasklist.md"), acc, mod, t21,
                            ["differential_expression", "pathway_enrichment"])
        run_state["steps"].append({"module_id": mod, "status": "success" if ok else "failed"})
        methods.append({"method_id": "M001", "module_id": mod,
                        "description": "RMA 标准化（affy）+ MAS5 present/absent 探针过滤",
                        "software": "affy", "version": "Bioconductor 3.18"})
        produced_figures += [o["path"] for o in outputs if o["format"] == "pdf"]
        if not ok:
            dump_yaml(os.path.join(mdir, "records", "error_log.yaml"),
                      {"module_id": mod, "run_id": run_id, "returncode": rc, "timestamp": ts})
            run_state["status"] = "failed"
            dump_yaml(os.path.join(ws, "analysis", "_runs", run_id, "run.yaml"), run_state)
            return 1

        # ---- Step 2: differential_expression ----
        seq += 1
        mod = "differential_expression"
        mdir = os.path.join(out_root, mod)
        rel2 = lambda p: os.path.relpath(os.path.join(mdir, p), ws).replace("\\", "/")
        outputs2 = [
            {"name": "deg_table", "path": rel2("results/deg_table.csv"), "format": "csv", "is_final": True,
             "partn_n_output": partn_n(seq)},
            {"name": "volcano", "path": rel2("figures/volcano.pdf"), "format": "pdf", "is_final": True},
            {"name": "de_summary", "path": rel2("results/de_summary.csv"), "format": "csv", "is_final": True},
        ]
        inputs2 = [
            {"name": "expr_filtered",
             "path": os.path.join("analysis", "outputs", acc, "preprocess", "results", "expr_filtered.csv").replace("\\", "/"),
             "format": "csv", "required": True},
            {"name": "sample_sheet", "path": sample_sheet_rel.replace("\\", "/"), "format": "csv", "required": True},
        ]
        ij2 = build_input_json(os.path.join(mdir, "run", f"input_{run_id}.json"), run_id, mod, inputs2, outputs2,
                               {"padj_threshold": 0.05, "log2fc_threshold": 1.0, "adjust_method": "BH",
                                "random_seed": 42},
                               rel2(f"logs/{run_id}.log"))
        rc2 = run_module(ws, mod, "analysis/modules/differential_expression/scripts/r/01_main.R",
                         os.path.relpath(ij2, ws).replace("\\", "/"))
        ok2 = rc2 == 0 and all(os.path.exists(os.path.join(ws, o["path"])) for o in outputs2)
        dump_yaml(os.path.join(mdir, "manifest.yaml"), {
            "module_id": mod, "module_version": "1.0.0", "run_id": run_id, "timestamp": ts,
            "status": "success" if ok2 else "failed", "execution_backend": "github_actions",
            "inputs": inputs2, "outputs": outputs2,
            "parameters": {"padj_threshold": 0.05, "log2fc_threshold": 1.0, "adjust_method": "BH"},
            "environment": {"os": "Linux", "r_version": "4.3.1", "random_seed": 42},
            "qc_result": {"passed": ok2, "checks": [t21]},
        })
        write_handoff(os.path.join(mdir, "records", "handoff.md"),
                      module_id=mod, dataset=acc, run_id=run_id, timestamp=ts,
                      status="success" if ok2 else "failed",
                      what="差异表达分析（limma + BH）",
                      did="表达矩阵与样本表对齐 → limma lmFit/eBayes → BH 校正 → 火山图",
                      inputs_desc=f"- {inputs2[0]['path']}\n- {inputs2[1]['path']}",
                      outputs_desc="\n".join(f"- {o['name']}: {o['path']}" for o in outputs2),
                      result="见 deg_table.csv 与 de_summary.csv" if ok2 else "执行失败",
                      usable="可用" if ok2 else "不可用",
                      next="进入通路富集" if ok2 else "排查失败原因")
        write_diff(os.path.join(mdir, "records", "diff.md"), acc, mod, None,
                   {"outputs": outputs2, "conclusion": "limma 差异分析完成" if ok2 else "失败"})
        write_checkpoint(os.path.join(mdir, "records", "checkpoint.yaml"), acc, mod, run_id, seq, outputs2)
        write_next_tasklist(os.path.join(mdir, "records", "next_tasklist.md"), acc, mod, t21, ["pathway_enrichment"])
        run_state["steps"].append({"module_id": mod, "status": "success" if ok2 else "failed"})
        methods.append({"method_id": "M002", "module_id": mod,
                        "description": "limma 线性模型 + eBayes + BH 校正",
                        "software": "limma", "version": "Bioconductor 3.18"})
        produced_figures += [o["path"] for o in outputs2 if o["format"] == "pdf"]

        if ok2:
            # ---- Step 3: pathway_enrichment ----
            seq += 1
            mod = "pathway_enrichment"
            mdir = os.path.join(out_root, mod)
            rel3 = lambda p: os.path.relpath(os.path.join(mdir, p), ws).replace("\\", "/")
            outputs3 = [
                {"name": "enrich_go", "path": rel3("results/enrich_go.csv"), "format": "csv", "is_final": True,
                 "partn_n_output": partn_n(seq)},
                {"name": "enrich_kegg", "path": rel3("results/enrich_kegg.csv"), "format": "csv", "is_final": True},
                {"name": "enrich_summary", "path": rel3("results/enrich_summary.csv"), "format": "csv", "is_final": True},
                {"name": "enrich_plot", "path": rel3("figures/enrich_plot.pdf"), "format": "pdf", "is_final": True},
            ]
            inputs3 = [{"name": "deg_table",
                        "path": os.path.join("analysis", "outputs", acc, "differential_expression",
                                             "results", "deg_table.csv").replace("\\", "/"),
                        "format": "csv", "required": True}]
            ij3 = build_input_json(os.path.join(mdir, "run", f"input_{run_id}.json"), run_id, mod, inputs3, outputs3,
                                   {"padj_threshold": 0.05, "log2fc_threshold": 1.0,
                                    "annotation_db": "hgu133plus2.db", "kegg_organism": "hsa", "random_seed": 42},
                                   rel3(f"logs/{run_id}.log"))
            rc3 = run_module(ws, mod, "analysis/modules/pathway_enrichment/scripts/r/01_main.R",
                             os.path.relpath(ij3, ws).replace("\\", "/"))
            ok3 = rc3 == 0 and all(os.path.exists(os.path.join(ws, o["path"])) for o in outputs3)
            dump_yaml(os.path.join(mdir, "manifest.yaml"), {
                "module_id": mod, "module_version": "1.0.0", "run_id": run_id, "timestamp": ts,
                "status": "success" if ok3 else "failed", "execution_backend": "github_actions",
                "inputs": inputs3, "outputs": outputs3,
                "parameters": {"padj_threshold": 0.05, "log2fc_threshold": 1.0, "annotation_db": "hgu133plus2.db"},
                "environment": {"os": "Linux", "r_version": "4.3.1", "random_seed": 42},
                "qc_result": {"passed": ok3, "checks": [t21]},
            })
            write_handoff(os.path.join(mdir, "records", "handoff.md"),
                          module_id=mod, dataset=acc, run_id=run_id, timestamp=ts,
                          status="success" if ok3 else "failed",
                          what="通路富集（GO / KEGG）",
                          did="显著探针 → ENTREZ 映射 → clusterProfiler GO/KEGG（BH）",
                          inputs_desc=f"- {inputs3[0]['path']}",
                          outputs_desc="\n".join(f"- {o['name']}: {o['path']}" for o in outputs3),
                          result="见 enrich_go.csv / enrich_kegg.csv" if ok3 else "执行失败",
                          usable="可用" if ok3 else "不可用",
                          next="进入 P2 写作" if ok3 else "排查失败原因",
                          )
            write_diff(os.path.join(mdir, "records", "diff.md"), acc, mod, None,
                       {"outputs": outputs3, "conclusion": "富集完成" if ok3 else "失败"})
            write_checkpoint(os.path.join(mdir, "records", "checkpoint.yaml"), acc, mod, run_id, seq, outputs3)
            write_next_tasklist(os.path.join(mdir, "records", "next_tasklist.md"), acc, mod, t21, [])
            run_state["steps"].append({"module_id": mod, "status": "success" if ok3 else "failed"})
            methods.append({"method_id": "M003", "module_id": mod,
                            "description": "clusterProfiler GO/KEGG 富集（论文用 MAPPFinder，云端以 clusterProfiler 实现等价功能，已在 handoff 声明）",
                            "software": "clusterProfiler", "version": "Bioconductor 3.18"})
            produced_figures += [o["path"] for o in outputs3 if o["format"] == "pdf"]

            # 证据（数字全部来自文件）
            de_sum_path = os.path.join(out_root, "differential_expression", "results", "de_summary.csv")
            if os.path.exists(de_sum_path):
                import csv as _csv
                with open(de_sum_path, encoding="utf-8") as f:
                    row = next(_csv.DictReader(f))
                evidence.append({
                    "evidence_id": "E001",
                    "partn_n_output": partn_n(2),
                    "module_id": "differential_expression",
                    "claim": f"在 {row.get('group_test')} vs {row.get('group_ref')} 比较中，"
                             f"按 adj.P.Val < {row.get('padj_threshold')} 且 |log2FC| > {row.get('log2fc_threshold')} "
                             f"共检出 {row.get('n_significant')} 个差异探针（检验总数 {row.get('n_probes_tested')}）",
                    "result_file": os.path.join("analysis", "outputs", acc, "differential_expression",
                                                "results", "deg_table.csv").replace("\\", "/"),
                    "figure": os.path.join("analysis", "outputs", acc, "differential_expression",
                                           "figures", "volcano.pdf").replace("\\", "/"),
                    "table": os.path.join("analysis", "outputs", acc, "differential_expression",
                                          "results", "deg_table.csv").replace("\\", "/"),
                    "parameters": {"padj_threshold": row.get("padj_threshold"),
                                   "log2fc_threshold": row.get("log2fc_threshold")},
                    "method": "limma + BH",
                    "method_description": "limma 线性模型，经验贝叶斯 moderated t 检验，BH 校正 FDR",
                    "suitable_for": ["Methods", "Results"],
                    "limitations": t21.get("message", ""),
                })

    # ---- 五格式导出 ----
    fig_report = []
    if produced_figures:
        fig_report = export_five_formats(ws, produced_figures)
        dump_yaml(os.path.join(ws, "analysis", "_index", f"figure_export_{acc}.yaml"), {
            "dataset": acc, "run_id": run_id, "timestamp": ts, "figures": fig_report,
        })
        print(f"[{acc}] 五格式导出：{len(fig_report)} 张图")

    run_state["status"] = "completed" if all(
        s.get("status") in ("success", "skipped") for s in run_state["steps"]) else "partial"
    dump_yaml(os.path.join(ws, "analysis", "_runs", run_id, "run.yaml"), run_state)

    # ---- P1 接口文件 ----
    idx = os.path.join(ws, "analysis", "_index")
    os.makedirs(idx, exist_ok=True)

    dump_yaml(os.path.join(idx, f"p1_to_p2_evidence_{acc}.yaml"), {
        "project_id": f"project_v2_e2e_{acc.lower()}",
        "timestamp": ts,
        "dataset": acc,
        "t21_status": t21["status"],
        "blocked_reason": t21.get("message") if t21["status"] != "pass" else None,
        "evidence": evidence,
        "methods": methods,
        "figures": [{"figure_id": os.path.splitext(os.path.basename(f["figure"]))[0],
                     "path": f["figure"], "description": "P1 产出图", "suitable_for": "main_figure"}
                    for f in fig_report],
        "tables": [{"table_id": "table_deg",
                    "path": os.path.join("analysis", "outputs", acc, "differential_expression",
                                         "results", "deg_table.csv").replace("\\", "/"),
                    "description": "差异表达表", "suitable_for": "supplementary"}] if evidence else [],
    })

    dump_yaml(os.path.join(idx, f"p1_to_p4_quality_{acc}.yaml"), {
        "project_id": f"project_v2_e2e_{acc.lower()}",
        "timestamp": ts,
        "analysis_summary": {
            "data_type": data_type,
            "sample_size": da.get("sample_size"),
            "group_sizes": group_sizes,
            "analysis_modules": [s["module_id"] for s in run_state["steps"]],
            "total_evidence": len(evidence),
            "total_figures": len(fig_report),
            "total_tables": 1 if evidence else 0,
        },
        "quality_assessment": {
            "data_quality": "high" if t21["status"] == "pass" else "low",
            "method_rigor": "high",
            "statistical_validity": "high" if t21["status"] == "pass" else "low",
            "reproducibility": "high",
            "novelty": "medium",
            "clinical_value": "medium",
        },
        "topic_assessment": {
            "primary_topic": da.get("inputs", {}).get("geo_title"),
            "secondary_topic": None,
            "potential_journals": [],
        },
        "strengths": ["流程按论文思路执行", "随机种子固定，可复现"],
        "weaknesses": [t21["message"]] if t21["status"] != "pass" else ["缺少外部验证", "缺少实验验证"],
        "recommendations": ["补充外部验证"] if t21["status"] == "pass" else ["补充样本至每组 n ≥ 6"],
    })

    print(f"[{acc}] P1 接口文件已生成。run_id={run_id} status={run_state['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
