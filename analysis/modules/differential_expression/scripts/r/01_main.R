#!/usr/bin/env Rscript
# P1 模块 differential_expression：limma 两组比较 + BH 校正
#
# 论文流程：limma 包，两组间比较，BH 校正 FDR。
# 纪律：不硬编码路径，一切从 input JSON 读；随机种子固定；写日志。
# 说明：样本量是否足以支撑统计推断由 P1 质控（T21）在调用前判定，本模块只计算。

suppressMessages({
  library(jsonlite)
  library(limma)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) stop("usage: Rscript 01_main.R <input.json>")
cfg <- jsonlite::fromJSON(args[1])
set.seed(cfg$meta$random_seed)

log_path <- cfg$log$path
dir.create(dirname(log_path), recursive = TRUE, showWarnings = FALSE)
sink(log_path, append = TRUE, split = TRUE)
cat("== differential_expression start ==\n")
cat("run_id: ", cfg$meta$run_id, "\n", sep = "")

get_in <- function(nm) cfg$inputs$path[cfg$inputs$name == nm][1]
get_out <- function(nm) cfg$outputs$path[cfg$outputs$name == nm][1]
get_par <- function(nm, default = NULL) if (!is.null(cfg$parameters[[nm]])) cfg$parameters[[nm]] else default

padj_thr <- as.numeric(get_par("padj_threshold", 0.05))
lfc_thr <- as.numeric(get_par("log2fc_threshold", 1.0))
adjust_method <- as.character(get_par("adjust_method", "BH"))

# 先建齐所有输出目录（pdf() 不会自动建目录）
for (o in cfg$outputs$path) dir.create(dirname(o), recursive = TRUE, showWarnings = FALSE)

# ---------- Step 1: 对齐 ----------
expr <- read.csv(get_in("expr_filtered"), check.names = FALSE, row.names = 1)
ss <- read.csv(get_in("sample_sheet"), stringsAsFactors = FALSE)
colnames(expr) <- sub("\\.(CEL|cel|gz)$", "", colnames(expr))

common <- intersect(colnames(expr), ss$gsm)
if (length(common) < 2) stop("表达矩阵列名与 sample_sheet 的 gsm 无法对齐")
expr <- expr[, common, drop = FALSE]
ss <- ss[match(common, ss$gsm), ]
grp <- factor(ss$group)

tab <- table(grp)
cat("group sizes:\n"); print(tab)

ref <- if ("control" %in% levels(grp)) "control" else levels(grp)[1]
test <- setdiff(levels(grp), ref)[1]
cat("contrast: ", test, " vs ", ref, "\n", sep = "")

# ---------- Step 2: limma ----------
design <- model.matrix(~ 0 + grp)
colnames(design) <- levels(grp)
fit <- lmFit(expr, design)
cm <- makeContrasts(contrasts = paste0(test, "-", ref), levels = design)
fit2 <- contrasts.fit(fit, cm)
fit2 <- eBayes(fit2)
tt <- topTable(fit2, coef = 1, number = Inf, adjust.method = adjust_method)
tt$probe_id <- rownames(tt)
tt <- tt[, c("probe_id", "logFC", "AveExpr", "t", "P.Value", "adj.P.Val", "B")]

out_deg <- get_out("deg_table")
dir.create(dirname(out_deg), recursive = TRUE, showWarnings = FALSE)
write.csv(tt, out_deg, row.names = FALSE)

n_sig <- sum(!is.na(tt$adj.P.Val) & tt$adj.P.Val < padj_thr & abs(tt$logFC) > lfc_thr, na.rm = TRUE)
write.csv(
  data.frame(
    n_probes_tested = nrow(tt),
    n_significant = n_sig,
    padj_threshold = padj_thr,
    log2fc_threshold = lfc_thr,
    adjust_method = adjust_method,
    group_ref = ref,
    group_test = test,
    n_ref = as.integer(tab[[ref]]),
    n_test = as.integer(tab[[test]])
  ),
  get_out("de_summary"), row.names = FALSE
)
cat("step2 done: tested=", nrow(tt), " significant=", n_sig, "\n", sep = "")

# ---------- Step 3: 火山图 ----------
pdf(get_out("volcano"), width = 6, height = 5.2)
plot(tt$logFC, -log10(pmax(tt$P.Value, 1e-300)),
     pch = 16, cex = 0.4, col = ifelse(!is.na(tt$adj.P.Val) & tt$adj.P.Val < padj_thr & abs(tt$logFC) > lfc_thr, "#D55E00", "#999999"),
     xlab = "log2 fold change", ylab = "-log10 P value",
     main = paste0("Volcano: ", test, " vs ", ref, " (n=", tab[[test]], " vs ", tab[[ref]], ")"))
abline(v = c(-lfc_thr, lfc_thr), lty = 2, col = "grey40")
abline(h = -log10(padj_thr), lty = 2, col = "grey40")
dev.off()
cat("step3 done: volcano written\n")

cat("== differential_expression success ==\n")
sink()
