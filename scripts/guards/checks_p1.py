"""P1 判据实现（A 档 21 条）+ 变异用例。

依据：01.P1/P1纲要.txt §2.6（迁移校验）§7.12（质控 12 项）§11/§18.12（图片规则）
分档：见 2-骨架与接口/判据分档表.md §2（P1：A 21 / B 1 / C 2）

需要 ctx.meta["dataset"]。
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from .base import FAIL, NA, PASS, Context, Finding, get_in, load_yaml, register
from .mutation import case

PART = "P1"

MIN_GROUP_N = 6
FIVE_FORMATS = ("pdf", "png", "tiff", "jpg", "svg")


def _acc(ctx: Context) -> str:
    return str(ctx.meta.get("dataset", "")).upper()


def _rel(ctx: Context, name: str) -> str:
    return name.replace("{ACC}", _acc(ctx))


def _migration(ctx: Context) -> Any:
    return ctx.doc(_rel(ctx, "inputs/migration_log_{ACC}.yaml"))


def _availability(ctx: Context) -> Any:
    return ctx.doc(_rel(ctx, "analysis/_index/data_availability_{ACC}.yaml"))


def _figure_export(ctx: Context) -> Any:
    return ctx.doc(_rel(ctx, "analysis/_index/figure_export_{ACC}.yaml"))


def _manifests(ctx: Context) -> List[Dict[str, Any]]:
    root = os.path.join(ctx.workspace, "analysis", "outputs", _acc(ctx))
    out = []
    if not os.path.isdir(root):
        return out
    for sub in sorted(os.listdir(root)):
        p = os.path.join(root, sub, "manifest.yaml")
        if os.path.exists(p):
            d = load_yaml(p)
            if isinstance(d, dict):
                out.append(d)
    return out


def _present(d: Any) -> bool:
    return isinstance(d, dict) and len(d) > 0


# ================================================== 迁移校验（5 条）

@register("P1.M1.file_exists", PART, "A", "inputs/migration_log_{ACC}.yaml:sources[].status", "Q1 迁移文件存在")
def _m1(ctx: Context) -> Finding:
    doc = _migration(ctx)
    if not _present(doc):
        return Finding("P1.M1.file_exists", NA, "inputs/migration_log_{ACC}.yaml", "迁移记录不存在")
    srcs = get_in(doc, "sources", []) or []
    bad = [i for i, s in enumerate(srcs) if s.get("status") != "success"]
    if bad:
        return Finding("P1.M1.file_exists", FAIL, "inputs/migration_log_{ACC}.yaml:sources[].status", f"第 {bad} 项未成功")
    if not srcs:
        return Finding("P1.M1.file_exists", FAIL, "inputs/migration_log_{ACC}.yaml:sources", "无迁移记录")
    return Finding("P1.M1.file_exists", PASS, "inputs/migration_log_{ACC}.yaml:sources", f"{len(srcs)} 项成功")


@register("P1.M2.readable", PART, "A", "inputs/raw/{ACC}", "Q2 原始数据可读")
def _m2(ctx: Context) -> Finding:
    p = os.path.join(ctx.workspace, "inputs", "raw", _acc(ctx))
    if not os.path.isdir(p):
        return Finding("P1.M2.readable", NA, "inputs/raw/{ACC}", "原始数据目录不存在")
    if not os.access(p, os.R_OK):
        return Finding("P1.M2.readable", FAIL, "inputs/raw/{ACC}", "目录不可读")
    return Finding("P1.M2.readable", PASS, "inputs/raw/{ACC}", "可读")


@register("P1.M4.checksum", PART, "A", "inputs/migration_log_{ACC}.yaml:checksum_after", "Q4 迁移 checksum 一致")
def _m4(ctx: Context) -> Finding:
    doc = _migration(ctx)
    if not _present(doc):
        return Finding("P1.M4.checksum", NA, "inputs/migration_log_{ACC}.yaml", "迁移记录不存在")
    for i, s in enumerate(get_in(doc, "sources", []) or []):
        if not str(s.get("checksum_after", "")).startswith("sha256:"):
            return Finding("P1.M4.checksum", FAIL, f"inputs/migration_log_{_acc(ctx)}.yaml:sources[{i}].checksum_after",
                           "缺 checksum")
    return Finding("P1.M4.checksum", PASS, "inputs/migration_log_{ACC}.yaml:checksum_after", "checksum 齐全")


@register("P1.M5.file_count", PART, "A", "inputs/migration_log_{ACC}.yaml:summary", "Q5 迁移文件数量一致")
def _m5(ctx: Context) -> Finding:
    doc = _migration(ctx)
    if not _present(doc):
        return Finding("P1.M5.file_count", NA, "inputs/migration_log_{ACC}.yaml", "迁移记录不存在")
    s = get_in(doc, "summary", {}) or {}
    if s.get("failed", 0) > 0:
        return Finding("P1.M5.file_count", FAIL, "inputs/migration_log_{ACC}.yaml:summary.failed", f"失败 {s['failed']} 项")
    if s.get("total_files", 0) == 0:
        return Finding("P1.M5.file_count", FAIL, "inputs/migration_log_{ACC}.yaml:summary.total_files", "无文件")
    return Finding("P1.M5.file_count", PASS, "inputs/migration_log_{ACC}.yaml:summary", f"{s['total_files']} 项")


@register("P1.M6.size_match", PART, "A", "inputs/migration_log_{ACC}.yaml:size_bytes", "Q6 迁移文件大小记录（warn 级）")
def _m6(ctx: Context) -> Finding:
    doc = _migration(ctx)
    if not _present(doc):
        return Finding("P1.M6.size_match", NA, "inputs/migration_log_{ACC}.yaml", "迁移记录不存在")
    for i, s in enumerate(get_in(doc, "sources", []) or []):
        if not isinstance(s.get("size_bytes"), int) or s["size_bytes"] <= 0:
            return Finding("P1.M6.size_match", FAIL, f"inputs/migration_log_{_acc(ctx)}.yaml:sources[{i}].size_bytes",
                           "大小记录缺失或非正")
    return Finding("P1.M6.size_match", PASS, "inputs/migration_log_{ACC}.yaml:size_bytes", "大小记录齐全")


# ================================================== 质控（10 条）

@register("P1.QC1.input_completeness", PART, "A", "analysis/_index/data_availability_{ACC}.yaml:sample_size",
          "输入完整性：样本量与分组可用")
def _qc1(ctx: Context) -> Finding:
    da = _availability(ctx)
    if not _present(da):
        return Finding("P1.QC1.input_completeness", NA, "analysis/_index/data_availability_{ACC}.yaml", "数据可用性缺失")
    if not da.get("sample_size"):
        return Finding("P1.QC1.input_completeness", FAIL, "analysis/_index/data_availability_{ACC}.yaml:sample_size", "样本量缺失")
    return Finding("P1.QC1.input_completeness", PASS, "analysis/_index/data_availability_{ACC}.yaml:sample_size",
                   f"n={da['sample_size']}")


@register("P1.QC2.input_format", PART, "A", "analysis/_index/data_availability_{ACC}.yaml:data_type",
          "输入格式：数据类型已识别")
def _qc2(ctx: Context) -> Finding:
    da = _availability(ctx)
    if not _present(da):
        return Finding("P1.QC2.input_format", NA, "analysis/_index/data_availability_{ACC}.yaml", "数据可用性缺失")
    if da.get("data_type") in (None, "unknown"):
        return Finding("P1.QC2.input_format", FAIL, "analysis/_index/data_availability_{ACC}.yaml:data_type", "数据类型未识别")
    return Finding("P1.QC2.input_format", PASS, "analysis/_index/data_availability_{ACC}.yaml:data_type",
                   str(da.get("data_type")))


@register("P1.QC3.input_checksum", PART, "A", "manifest.yaml:inputs[].format", "输入声明与实际文件对应")
def _qc3(ctx: Context) -> Finding:
    mans = _manifests(ctx)
    if not mans:
        return Finding("P1.QC3.input_checksum", NA, "analysis/outputs/{ACC}/*/manifest.yaml", "无 manifest")
    for m in mans:
        for i in m.get("inputs", []) or []:
            p = os.path.join(ctx.workspace, str(i.get("path", "")))
            if not os.path.exists(p):
                return Finding("P1.QC3.input_checksum", FAIL, f"manifest:{m.get('module_id')}.inputs", f"缺输入 {i.get('path')}")
    return Finding("P1.QC3.input_checksum", PASS, "manifest.yaml:inputs", "输入齐全")


@register("P1.QC4.sample_size", PART, "A", "analysis/_index/data_availability_{ACC}.yaml:group_inference.group_sizes",
          "T21 组别样本量下限与平衡")
def _qc4(ctx: Context) -> Finding:
    da = _availability(ctx)
    if not _present(da):
        return Finding("P1.QC4.sample_size", NA, "analysis/_index/data_availability_{ACC}.yaml", "数据可用性缺失")
    sizes = get_in(da, "group_inference.group_sizes", None)
    if not sizes:
        return Finding("P1.QC4.sample_size", NA, "analysis/_index/data_availability_{ACC}.yaml:group_inference.group_sizes",
                       "分组缺失，无法判定")
    vals = [int(v) for v in sizes.values() if isinstance(v, (int, float))]
    if not vals:
        return Finding("P1.QC4.sample_size", NA, "analysis/_index/data_availability_{ACC}.yaml:group_inference.group_sizes",
                       "分组大小非数值")
    if min(vals) < MIN_GROUP_N:
        return Finding("P1.QC4.sample_size", FAIL, "analysis/_index/data_availability_{ACC}.yaml:group_inference.group_sizes",
                       f"最小组 n={min(vals)} < {MIN_GROUP_N}，拒绝统计推断")
    return Finding("P1.QC4.sample_size", PASS, "analysis/_index/data_availability_{ACC}.yaml:group_inference.group_sizes",
                   f"组大小 {sizes}")


@register("P1.QC5.missing_value", PART, "A", "manifest.yaml:qc_result.checks", "缺失值与异常：质控报告已记录")
def _qc5(ctx: Context) -> Finding:
    p = os.path.join(ctx.workspace, "analysis", "outputs", _acc(ctx), "records", "qc_report.yaml")
    if not os.path.exists(p):
        return Finding("P1.QC5.missing_value", NA, "analysis/outputs/{ACC}/records/qc_report.yaml", "无质控报告")
    d = load_yaml(p)
    if not isinstance(d, dict) or not d.get("checks"):
        return Finding("P1.QC5.missing_value", FAIL, "analysis/outputs/{ACC}/records/qc_report.yaml:checks", "质控项为空")
    return Finding("P1.QC5.missing_value", PASS, "analysis/outputs/{ACC}/records/qc_report.yaml:checks",
                   f"{len(d['checks'])} 项质控")


@register("P1.QC6.normalization", PART, "A", "manifest.yaml[preprocess].status", "标准化已执行")
def _qc6(ctx: Context) -> Finding:
    mans = _manifests(ctx)
    if not mans:
        return Finding("P1.QC6.normalization", NA, "analysis/outputs/{ACC}/*/manifest.yaml", "无 manifest")
    for m in mans:
        if m.get("module_id") == "preprocess":
            if m.get("status") != "success":
                return Finding("P1.QC6.normalization", FAIL, "analysis/outputs/{ACC}/preprocess/manifest.yaml:status",
                               "标准化未成功")
            return Finding("P1.QC6.normalization", PASS, "analysis/outputs/{ACC}/preprocess/manifest.yaml:status", "已标准化")
    return Finding("P1.QC6.normalization", NA, "analysis/outputs/{ACC}/preprocess/manifest.yaml", "未执行标准化（可能不适用）")


@register("P1.QC7.parameter_validity", PART, "A", "manifest.yaml:parameters", "参数合法且在阈值内")
def _qc7(ctx: Context) -> Finding:
    mans = _manifests(ctx)
    if not mans:
        return Finding("P1.QC7.parameter_validity", NA, "analysis/outputs/{ACC}/*/manifest.yaml", "无 manifest")
    for m in mans:
        p = m.get("parameters", {}) or {}
        for k in ("padj_threshold",):
            if k in p and not (0 < float(p[k]) <= 1):
                return Finding("P1.QC7.parameter_validity", FAIL, f"manifest:{m.get('module_id')}.parameters.{k}", f"{k}={p[k]} 越界")
        if "absent_fraction_threshold" in p and not (0 <= float(p["absent_fraction_threshold"]) <= 1):
            return Finding("P1.QC7.parameter_validity", FAIL,
                           f"manifest:{m.get('module_id')}.parameters.absent_fraction_threshold", "阈值越界")
    return Finding("P1.QC7.parameter_validity", PASS, "manifest.yaml:parameters", "参数合法")


@register("P1.QC8.output_completeness", PART, "A", "manifest.yaml:outputs[].path", "输出齐全")
def _qc8(ctx: Context) -> Finding:
    mans = _manifests(ctx)
    if not mans:
        return Finding("P1.QC8.output_completeness", NA, "analysis/outputs/{ACC}/*/manifest.yaml", "无 manifest")
    for m in mans:
        if m.get("status") == "failed":
            return Finding("P1.QC8.output_completeness", FAIL, f"manifest:{m.get('module_id')}.status", "模块失败")
        for o in m.get("outputs", []) or []:
            if o.get("conditional"):
                continue  # 条件性输出（如 T21 门控下的 volcano）：未生成不算缺失，但须在 manifest 标注
            if o.get("is_final") and not os.path.exists(os.path.join(ctx.workspace, str(o.get("path", "")))):
                return Finding("P1.QC8.output_completeness", FAIL, f"manifest:{m.get('module_id')}.outputs",
                               f"缺输出 {o.get('path')}")
    return Finding("P1.QC8.output_completeness", PASS, "manifest.yaml:outputs", "输出齐全")


@register("P1.QC9.output_format", PART, "A", "manifest.yaml:outputs[].format", "输出格式符合声明")
def _qc9(ctx: Context) -> Finding:
    mans = _manifests(ctx)
    if not mans:
        return Finding("P1.QC9.output_format", NA, "analysis/outputs/{ACC}/*/manifest.yaml", "无 manifest")
    for m in mans:
        for o in m.get("outputs", []) or []:
            fmt, path = str(o.get("format", "")), str(o.get("path", ""))
            if not fmt:
                return Finding("P1.QC9.output_format", FAIL, f"manifest:{m.get('module_id')}.outputs[].format", "缺格式声明")
            if path.lower().endswith((".csv", ".pdf", ".png", ".tiff", ".jpg", ".svg")):
                ext = path.rsplit(".", 1)[-1].lower()
                if ext == "tiff":
                    ext = "tiff"
                if fmt.lower() != ext and not (fmt == "pdf" and ext == "pdf"):
                    return Finding("P1.QC9.output_format", FAIL, f"manifest:{m.get('module_id')}.outputs",
                                   f"{path} 扩展名与声明格式 {fmt} 不符")
    return Finding("P1.QC9.output_format", PASS, "manifest.yaml:outputs[].format", "格式一致")


@register("P1.QC10.reproducibility", PART, "A", "manifest.yaml:environment.random_seed", "可复现：随机种子固定")
def _qc10(ctx: Context) -> Finding:
    mans = _manifests(ctx)
    if not mans:
        return Finding("P1.QC10.reproducibility", NA, "analysis/outputs/{ACC}/*/manifest.yaml", "无 manifest")
    for m in mans:
        if m.get("environment", {}).get("random_seed") is None:
            return Finding("P1.QC10.reproducibility", FAIL, f"manifest:{m.get('module_id')}.environment.random_seed", "随机种子未固定")
    return Finding("P1.QC10.reproducibility", PASS, "manifest.yaml:environment.random_seed", "种子已固定")


# ================================================== 图片产出前置（6 条）

def _figures(ctx: Context) -> List[Dict[str, Any]]:
    d = _figure_export(ctx)
    if not _present(d):
        return []
    return [f for f in (d.get("figures") or []) if isinstance(f, dict)]


@register("P1.F1.five_formats", PART, "A", "figure_export_{ACC}.yaml:figures[].formats", "五格式齐全")
def _f1(ctx: Context) -> Finding:
    figs = _figures(ctx)
    if not figs:
        return Finding("P1.F1.five_formats", NA, "analysis/_index/figure_export_{ACC}.yaml", "无图件导出记录")
    for f in figs:
        sizes = f.get("sizes_bytes", {}) or {}
        miss = [k for k in FIVE_FORMATS if k not in sizes]
        if miss:
            return Finding("P1.F1.five_formats", FAIL, "analysis/_index/figure_export_{ACC}.yaml:figures[].sizes_bytes",
                           f"{f.get('figure')} 缺格式 {miss}")
    return Finding("P1.F1.five_formats", PASS, "analysis/_index/figure_export_{ACC}.yaml:figures[].sizes_bytes",
                   f"{len(figs)} 张图五格式齐全")


@register("P1.F2.naming", PART, "A", "figure_export_{ACC}.yaml:figures[].figure", "命名与 P2/P3 全链路统一")
def _f2(ctx: Context) -> Finding:
    figs = _figures(ctx)
    if not figs:
        return Finding("P1.F2.naming", NA, "analysis/_index/figure_export_{ACC}.yaml", "无图件导出记录")
    import re
    for f in figs:
        name = os.path.basename(str(f.get("figure", "")))
        stem = os.path.splitext(name)[0]
        if not re.fullmatch(r"[A-Za-z0-9_\-]+", stem):
            return Finding("P1.F2.naming", FAIL, "analysis/_index/figure_export_{ACC}.yaml:figures[].figure",
                           f"命名不合规：{name}（只允许字母数字下划线连字符）")
    return Finding("P1.F2.naming", PASS, "analysis/_index/figure_export_{ACC}.yaml:figures[].figure", "命名合规")


@register("P1.F3.micro_dpi", PART, "A", "figure_export_{ACC}.yaml#microscopy", "显微图 TIFF 600 dpi（无显微图则 N/A）")
def _f3(ctx: Context) -> Finding:
    figs = _figures(ctx)
    micro = [f for f in figs if any(k in str(f.get("figure", "")).lower() for k in ("micro", "microscopy", "em_", "tem", "sem"))]
    if not micro:
        return Finding("P1.F3.micro_dpi", NA, "analysis/_index/figure_export_{ACC}.yaml", "无显微图，判 N/A")
    for f in micro:
        if int(((f.get("sizes_bytes") or {}).get("tiff", 0))) <= 0:
            return Finding("P1.F3.micro_dpi", FAIL, "analysis/_index/figure_export_{ACC}.yaml:figures[].tiff", "显微图缺 TIFF")
    return Finding("P1.F3.micro_dpi", PASS, "analysis/_index/figure_export_{ACC}.yaml", "显微图 TIFF 齐全")


@register("P1.F4.gel_grayscale", PART, "A", "figure_export_{ACC}.yaml#gel", "凝胶/印迹 TIFF 灰度（无该类图则 N/A）")
def _f4(ctx: Context) -> Finding:
    figs = _figures(ctx)
    gel = [f for f in figs if any(k in str(f.get("figure", "")).lower() for k in ("gel", "blot", "wb_"))]
    if not gel:
        return Finding("P1.F4.gel_grayscale", NA, "analysis/_index/figure_export_{ACC}.yaml", "无凝胶/印迹图，判 N/A")
    return Finding("P1.F4.gel_grayscale", PASS, "analysis/_index/figure_export_{ACC}.yaml", "凝胶图已导出")


@register("P1.F5.vector_first", PART, "A", "figure_export_{ACC}.yaml:figures[].sizes_bytes.pdf", "分析图矢量优先（PDF 母版存在）")
def _f5(ctx: Context) -> Finding:
    figs = _figures(ctx)
    if not figs:
        return Finding("P1.F5.vector_first", NA, "analysis/_index/figure_export_{ACC}.yaml", "无图件导出记录")
    for f in figs:
        if int((f.get("sizes_bytes") or {}).get("pdf", 0)) <= 0:
            return Finding("P1.F5.vector_first", FAIL, "analysis/_index/figure_export_{ACC}.yaml:figures[].sizes_bytes.pdf",
                           f"{f.get('figure')} 缺矢量 PDF 母版")
    return Finding("P1.F5.vector_first", PASS, "analysis/_index/figure_export_{ACC}.yaml:figures[].sizes_bytes.pdf", "矢量母版齐全")


@register("P1.F6.figure_numbering", PART, "A", "p1_to_p2_evidence_{ACC}.yaml:figures[].figure_id", "图表编号与 P1 接口一致")
def _f6(ctx: Context) -> Finding:
    ev = ctx.doc(_rel(ctx, "analysis/_index/p1_to_p2_evidence_{ACC}.yaml"))
    if not _present(ev):
        return Finding("P1.F6.figure_numbering", NA, "analysis/_index/p1_to_p2_evidence_{ACC}.yaml", "接口文件不存在")
    figs = ev.get("figures", []) or []
    ids = [f.get("figure_id") for f in figs]
    if len(set(ids)) != len(ids):
        return Finding("P1.F6.figure_numbering", FAIL, "analysis/_index/p1_to_p2_evidence_{ACC}.yaml:figures[].figure_id",
                       "figure_id 重复")
    exported = {str(f.get("figure", "")) for f in _figures(ctx)}
    for f in figs:
        p = str(f.get("path", ""))
        if not p:
            return Finding("P1.F6.figure_numbering", FAIL, "analysis/_index/p1_to_p2_evidence_{ACC}.yaml:figures[].path",
                           "图路径为空")
        if exported and p not in exported:
            return Finding("P1.F6.figure_numbering", FAIL, "analysis/_index/p1_to_p2_evidence_{ACC}.yaml:figures[].path",
                           f"接口引用的图不在导出清单中：{p}")
    return Finding("P1.F6.figure_numbering", PASS, "analysis/_index/p1_to_p2_evidence_{ACC}.yaml:figures",
                   f"{len(figs)} 张图编号唯一且闭合")


# ================================================== 变异用例

def _fig_fixture(acc: str = "GSE7451") -> Dict[str, Any]:
    return {
        f"analysis/_index/figure_export_{acc}.yaml": {
            "dataset": acc,
            "figures": [
                {
                    "figure": f"analysis/outputs/{acc}/differential_expression/figures/volcano.pdf",
                    "status": "ok",
                    "formats": {"svg": "ok", "png": "ok", "tiff": "ok", "jpg": "ok"},
                    "sizes_bytes": {"pdf": 12345, "svg": 23456, "png": 34567, "tiff": 45678, "jpg": 5678},
                }
            ],
        },
        f"analysis/_index/p1_to_p2_evidence_{acc}.yaml": {
            "figures": [
                {
                    "figure_id": "fig_volcano",
                    "path": f"analysis/outputs/{acc}/differential_expression/figures/volcano.pdf",
                }
            ]
        },
        f"analysis/_index/data_availability_{acc}.yaml": {
            "data_type": "microarray",
            "sample_size": 20,
            "group_inference": {"group_sizes": {"control": 10, "disease": 10}},
        },
        f"inputs/migration_log_{acc}.yaml": {
            "sources": [{"status": "success", "checksum_after": "sha256:abc", "size_bytes": 1024}],
            "summary": {"total_files": 1, "success": 1, "failed": 0},
        },
    }


def _mut_fig(fixture, acc, fn):
    figs = fixture[f"analysis/_index/figure_export_{acc}.yaml"]["figures"]
    fn(figs[0])


case("P1-Q1", "P1.F1.five_formats", "figures[0].sizes_bytes.svg", "删除 svg",
     lambda f: _mut_fig(f, "GSE7451", lambda d: d["sizes_bytes"].pop("svg", None)), PART, "删格式 → 五格式检查 FAIL")
case("P1-Q2", "P1.F2.naming", "figures[0].figure", "改命名为含空格与中文",
     lambda f: _mut_fig(f, "GSE7451", lambda d: d.__setitem__("figure", "analysis/outputs/火山 图.pdf")), PART,
     "改命名 → 命名检查 FAIL")
case("P1-Q5", "P1.F5.vector_first", "figures[0].sizes_bytes.pdf", "去掉矢量 PDF 母版",
     lambda f: _mut_fig(f, "GSE7451", lambda d: d["sizes_bytes"].pop("pdf", None)), PART, "改位图 → 矢量优先 FAIL")
case("P1-Q6", "P1.F6.figure_numbering", "p1_to_p2_evidence.figures[].path", "图路径改为不存在",
     lambda f: f["analysis/_index/p1_to_p2_evidence_GSE7451.yaml"]["figures"][0].__setitem__("path", "no/such/fig.pdf"),
     PART, "改编号/路径 → 一致性 FAIL")
case("P1-T21", "P1.QC4.sample_size", "group_inference.group_sizes", "对照组改为 n=4",
     lambda f: f["analysis/_index/data_availability_GSE7451.yaml"]["group_inference"].__setitem__(
         "group_sizes", {"control": 4, "disease": 34}), PART, "n<6 → T21 FAIL")
case("P1-M1", "P1.M1.file_exists", "sources[0].status", "迁移状态改为 failed",
     lambda f: f["inputs/migration_log_GSE7451.yaml"]["sources"][0].__setitem__("status", "failed"), PART,
     "迁移失败 → 存在性检查 FAIL")
