#!/usr/bin/env Rscript
# P1 模块 preprocess：RMA 标准化 + 探针过滤
#
# 论文流程（Hu S, et al. Arthritis Rheum. 2007）：
#   - 预处理：RMA 算法（背景校正 + 分位数标准化）
#   - 探针过滤：剔除 >75% 样本中 absent 的探针集
#
# 纪律：不硬编码路径，一切从 input JSON 读；随机种子固定；写日志。

suppressMessages({
  library(jsonlite)
  library(affy)
  library(Biobase)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) stop("usage: Rscript 01_main.R <input.json>")
cfg <- jsonlite::fromJSON(args[1])

# rma()/mas5calls() 经 preprocessCore 走 OpenMP 多线程；在受限容器（GitHub Actions runner）里
# 会出现 "return code from pthread_create() is 22"，强制单线程可规避。
Sys.setenv(OMP_NUM_THREADS = "1")

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
eset <- affy::rma(ab)
expr <- Biobase::exprs(eset)
cat("step2 done: RMA matrix ", nrow(expr), " x ", ncol(expr), "\n", sep = "")

out_rma <- get_out("expr_rma")
dir.create(dirname(out_rma), recursive = TRUE, showWarnings = FALSE)
write.csv(data.frame(probe_id = rownames(expr), expr, check.names = FALSE), out_rma, row.names = FALSE)

# ---------- Step 3: MAS5 present/absent + 过滤 ----------
calls <- affy::mas5calls(ab)
call_mat <- Biobase::exprs(calls)
n <- ncol(call_mat)
absent_frac <- rowSums(call_mat == "A") / n
keep <- absent_frac <= thr

expr_f <- expr[keep, , drop = FALSE]
cat("step3 done: probes ", nrow(expr), " -> ", nrow(expr_f), " (removed ", sum(!keep), ")\n", sep = "")

out_f <- get_out("expr_filtered")
write.csv(data.frame(probe_id = rownames(expr_f), expr_f, check.names = FALSE), out_f, row.names = FALSE)

out_sum <- get_out("filtering_summary")
write.csv(
  data.frame(
    n_probes_before = nrow(expr),
    n_probes_after = nrow(expr_f),
    n_removed = sum(!keep),
    absent_fraction_threshold = thr,
    n_samples = n,
    cdf_name = ab@cdfName
  ),
  out_sum, row.names = FALSE
)

cat("== preprocess success ==\n")
sink()
