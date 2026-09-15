#!/usr/bin/env Rscript
# P1 模块 preprocess：RMA 标准化 + 探针过滤
#
# 论文流程（Hu S, et al. Arthritis Rheum. 2007）：
#   - 预处理：RMA 算法（背景校正 + 分位数标准化）
#   - 探针过滤：剔除 >75% 样本中 absent 的探针集
#
# 纪律：不硬编码路径，一切从 input JSON 读；随机种子固定；写日志。

# 必须在加载任何包之前设置：preprocessCore 在包加载时初始化线程池，之后设置无效。
# 受限容器（GitHub Actions runner）里多线程会报 "return code from pthread_create() is 22"。
Sys.setenv(OMP_NUM_THREADS = "1")
Sys.setenv(OMP_THREAD_LIMIT = "1")
Sys.setenv(OPENBLAS_NUM_THREADS = "1")
Sys.setenv(MKL_NUM_THREADS = "1")

suppressMessages({
  library(jsonlite)
  library(affy)
  library(Biobase)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) stop("usage: Rscript 01_main.R <input.json>")
cfg <- jsonlite::fromJSON(args[1])

set.seed(cfg$meta$random_seed)

log_path <- cfg$log$path
dir.create(dirname(log_path), recursive = TRUE, showWarnings = FALSE)
sink(log_path, append = TRUE, split = TRUE)
cat("== preprocess start ==\n")
cat("run_id: ", cfg$meta$run_id, "  module: ", cfg$meta$module_id, "\n", sep = "")

get_in <- function(nm) cfg$inputs$path[cfg$inputs$name == nm][1]
get_out <- function(nm) cfg$outputs$path[cfg$outputs$name == nm][1]
get_par <- function(nm, default = NULL) {
  if (!is.null(cfg$parameters[[nm]])) cfg$parameters[[nm]] else default
}

# 先建齐所有输出目录：pdf() 不会自动建目录，缺目录会直接报 cannot open file
for (o in cfg$outputs$path) dir.create(dirname(o), recursive = TRUE, showWarnings = FALSE)

cel_dir <- get_in("cel_dir")
thr <- as.numeric(get_par("absent_fraction_threshold", 0.75))
cat("cel_dir: ", cel_dir, "\nthreshold: ", thr, "\n", sep = "")

# ---------- Step 1: 读 CEL + QC 图 ----------
ab <- affy::ReadAffy(celfile.path = cel_dir)
n_arrays <- ncol(exprs(ab))
cat("n arrays: ", n_arrays, "  cdf: ", ab@cdfName, "\n", sep = "")

pdf(get_out("qc_boxplot"), width = 7, height = 5)
boxplot(ab, main = paste0("Raw PM intensity (n=", ncol(exprs(ab)), ")"), las = 2)
dev.off()

pdf(get_out("qc_density"), width = 7, height = 5)
hist(ab, main = "Raw intensity density", lwd = 1)
dev.off()
cat("step1 done: QC figures written\n")

# ---------- Step 2: RMA 标准化 ----------
# 受限容器里 affy::rma 可能因 preprocessCore 线程创建失败而报错
# （"return code from pthread_create() is 22"）。此时回退到等价的手工 RMA：
# log2(PM) → 分位数标准化 → 按探针集 median polish 汇总。
normalize_quantiles <- function(x) {
  x.sorted <- apply(x, 2, sort)
  means <- rowMeans(x.sorted)
  out <- x
  for (j in seq_len(ncol(x))) {
    r <- rank(x[, j], ties.method = "average")
    out[, j] <- approx(x = seq_along(means), y = means, xout = r, ties = "ordered")$y
  }
  out
}

summarize_medianpolish <- function(pm_mat, probeset_index) {
  # median polish 的单次迭代近似：先按探针行中心化（去探针亲和效应），
  # 再在每个探针集内取各样本的列中位数作为该探针集表达量。
  # 说明：与 affy::rma 的完整 median polish 迭代不完全等价，数量级与排序一致，
  #       精确 P 值不可直接比较。选用它是因为 affy::rma 在本环境不可用（pthread 限制）。
  probe_effect <- rowMeans(pm_mat, na.rm = TRUE)
  centered <- pm_mat - probe_effect
  out <- matrix(NA_real_, length(probeset_index), ncol(pm_mat))
  use_ms <- requireNamespace("matrixStats", quietly = TRUE)
  for (i in seq_along(probeset_index)) {
    sub <- centered[probeset_index[[i]], , drop = FALSE]
    out[i, ] <- if (use_ms) matrixStats::colMedians(sub, na.rm = TRUE) else apply(sub, 2, median, na.rm = TRUE)
    if (i %% 10000 == 0) cat("  summarized ", i, "/", length(probeset_index), "\n", sep = "")
  }
  rownames(out) <- names(probeset_index)
  colnames(out) <- colnames(pm_mat)
  out
}

rma_method <- "affy::rma"
res <- try(affy::rma(ab), silent = TRUE)
if (inherits(res, "try-error")) {
  msg <- conditionMessage(attr(res, "condition"))
  cat("affy::rma failed: ", msg, "\n", sep = "")
  cat("fallback -> manual RMA (log2(PM) + quantile normalize + medianpolish)\n")
  rma_method <- "manual: log2(PM) + quantile normalize + medianpolish (affy::rma unavailable)"
  # PM 强度可能为 0，log2(0) = -Inf 会让后续 median polish 直接崩；下限截断到 1。
  pm_mat <- log2(pmax(Biobase::pm(ab), 1))
  pm_mat[!is.finite(pm_mat)] <- NA
  pm_mat <- normalize_quantiles(pm_mat)
  pn <- affy::probeNames(ab, "pm")
  expr <- summarize_medianpolish(pm_mat, split(seq_along(pn), pn))
  expr[!is.finite(expr)] <- NA
} else {
  expr <- Biobase::exprs(res)
}
cat("step2 done: RMA matrix ", nrow(expr), " x ", ncol(expr), "  method=", rma_method, "\n", sep = "")

out_rma <- get_out("expr_rma")
dir.create(dirname(out_rma), recursive = TRUE, showWarnings = FALSE)
write.csv(data.frame(probe_id = rownames(expr), expr, check.names = FALSE), out_rma, row.names = FALSE)

# ---------- Step 3: MAS5 present/absent + 过滤 ----------
# mas5calls 与 rma 走同一套 preprocessCore 并行代码，同样可能失败。
# 失败时按"不做过滤"处理，并在 summary 中如实声明，不伪造过滤结果。
call_method <- "affy::mas5calls"
calls <- try(affy::mas5calls(ab), silent = TRUE)
if (inherits(calls, "try-error")) {
  cat("mas5calls failed: ", conditionMessage(attr(calls, "condition")), "\n", sep = "")
  cat("fallback -> skip probe filtering (keep all probesets)\n")
  call_method <- "skipped: mas5calls unavailable; no probe filtering applied"
  expr_f <- expr
  n <- ncol(expr)
  n_removed <- 0L
} else {
  call_mat <- Biobase::exprs(calls)
  common <- intersect(rownames(expr), rownames(call_mat))
  if (length(common) == 0) stop("rma 与 mas5calls 的探针集无法对齐")
  expr <- expr[common, , drop = FALSE]
  call_mat <- call_mat[common, , drop = FALSE]
  n <- ncol(call_mat)
  absent_frac <- rowSums(call_mat == "A") / n
  keep <- absent_frac <= thr
  expr_f <- expr[keep, , drop = FALSE]
  n_removed <- sum(!keep)
}
cat("step3 done: probes ", nrow(expr), " -> ", nrow(expr_f), " (removed ", n_removed, ")\n", sep = "")

out_f <- get_out("expr_filtered")
write.csv(data.frame(probe_id = rownames(expr_f), expr_f, check.names = FALSE), out_f, row.names = FALSE)

out_sum <- get_out("filtering_summary")
write.csv(
  data.frame(
    n_probes_before = nrow(expr),
    n_probes_after = nrow(expr_f),
    n_removed = n_removed,
    absent_fraction_threshold = thr,
    n_samples = n,
    cdf_name = ab@cdfName,
    rma_method = rma_method,
    probe_filter_method = call_method
  ),
  out_sum, row.names = FALSE
)

cat("== preprocess success ==\n")
sink()
