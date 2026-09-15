#!/usr/bin/env Rscript
# P1 模块 rnaseq_de：RNA-seq 计数矩阵 QC（+ 可选 DESeq2 差异表达）
#
# 纪律：
# - 不硬编码路径，一切从 input json 读；随机种子固定；写日志。
# - 是否做差异表达由 run_deseq2 参数决定：该开关由 P1 质控（T21）在调用前判定，
#   本模块不自行决定能不能做统计推断。
# - DESeq2 不可用时如实写出原因，不伪造结果。

Sys.setenv(OMP_NUM_THREADS = "1")

suppressMessages({
  library(jsonlite)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) stop("usage: Rscript 01_main.R <input.json>")
cfg <- jsonlite::fromJSON(args[1])
set.seed(cfg$meta$random_seed)

log_path <- cfg$log$path
dir.create(dirname(log_path), recursive = TRUE, showWarnings = FALSE)
sink(log_path, append = TRUE, split = TRUE)
cat("== rnaseq_de start ==\n")
cat("run_id: ", cfg$meta$run_id, "\n", sep = "")

get_in <- function(nm) cfg$inputs$path[cfg$inputs$name == nm][1]
get_out <- function(nm) cfg$outputs$path[cfg$outputs$name == nm][1]
get_par <- function(nm, default = NULL) if (!is.null(cfg$parameters[[nm]])) cfg$parameters[[nm]] else default

for (o in cfg$outputs$path) dir.create(dirname(o), recursive = TRUE, showWarnings = FALSE)

count_file <- get_in("count_matrix")
sheet_file <- get_in("sample_sheet")
run_de <- isTRUE(as.logical(get_par("run_deseq2", FALSE)))
padj_thr <- as.numeric(get_par("padj_threshold", 0.05))
lfc_thr <- as.numeric(get_par("log2fc_threshold", 1.0))
cat("count_file: ", count_file, "\nrun_deseq2: ", run_de, "\n", sep = "")

read_matrix <- function(path) {
  head5 <- readLines(path, n = 5, warn = FALSE)
  sep <- if (any(grepl("\t", head5))) "\t" else ","
  cat("detected sep: ", if (sep == "\t") "TAB" else "COMMA", "\n", sep = "")
  d <- utils::read.delim(path, sep = sep, header = TRUE, row.names = 1,
                         check.names = FALSE, comment.char = "", quote = "")
  d <- d[, vapply(d, is.numeric, logical(1)), drop = FALSE]
  as.matrix(d)
}

cnt <- read_matrix(count_file)
cat("count matrix: ", nrow(cnt), " genes x ", ncol(cnt), " samples\n", sep = "")
cat("colnames: ", paste(colnames(cnt), collapse = ", "), "\n", sep = "")

# ---------- 样本表对齐 ----------
ss <- NULL
if (!is.na(sheet_file) && file.exists(sheet_file)) {
  ss <- utils::read.csv(sheet_file, stringsAsFactors = FALSE)
  cat("sample_sheet groups:\n"); print(table(ss$group))
}

# ---------- QC ----------
lib_size <- colSums(cnt, na.rm = TRUE)
write.csv(data.frame(sample = colnames(cnt), library_size = as.integer(lib_size),
                     detected_genes = as.integer(colSums(cnt > 0, na.rm = TRUE))),
          get_out("qc_summary"), row.names = FALSE)

pdf(get_out("qc_libsize"), width = 7, height = 4.5)
barplot(lib_size / 1e6, names.arg = colnames(cnt), las = 2, col = "#4C72B0",
        ylab = "Library size (millions)", main = "Library size per sample")
dev.off()

keep <- rowSums(cnt > 0) >= max(2, floor(ncol(cnt) / 2))
lcpm <- log2(cnt[keep, , drop = FALSE] / (lib_size[col(cnt[keep, , drop = FALSE])] / 1e6) + 1)
lcpm <- lcpm[!apply(lcpm, 1, function(r) any(!is.finite(r))), , drop = FALSE]
cat("genes kept for QC: ", nrow(lcpm), "\n", sep = "")

pdf(get_out("qc_correlation"), width = 6, height = 5)
if (ncol(lcpm) > 1 && nrow(lcpm) > 1) {
  cm <- cor(lcpm[, ], method = "spearman")
  cm[!is.finite(cm)] <- 0
  # heatmap.2 在样本数过少（<3）且相关矩阵取值退化时会崩在 seq.default(min.raw, max.raw)
  if (ncol(lcpm) >= 3 && requireNamespace("gplots", quietly = TRUE)) {
    gplots::heatmap.2(cm, trace = "none", main = "Sample correlation (Spearman)",
                      col = colorRampPalette(c("#2166AC", "white", "#B2182B"))(50))
  } else {
    image(cm, main = "Sample correlation (Spearman)", axes = FALSE)
    axis(1, at = seq(0, 1, length.out = ncol(cm)), labels = colnames(cm), las = 2)
    axis(2, at = seq(0, 1, length.out = nrow(cm)), labels = rownames(cm), las = 2)
  }
} else {
  plot.new(); text(0.5, 0.5, "not enough data for correlation")
}
dev.off()

pdf(get_out("qc_pca"), width = 6, height = 5)
if (ncol(lcpm) >= 2 && nrow(lcpm) > 2) {
  pcs <- prcomp(t(lcpm), center = TRUE, scale. = FALSE)
  varexp <- summary(pcs)$importance[2, 1:2] * 100
  plot(pcs$x[, 1], pcs$x[, 2], pch = 19, col = "#4C72B0",
       xlab = paste0("PC1 (", round(varexp[1], 1), "%)"),
       ylab = paste0("PC2 (", round(varexp[2], 1), "%)"),
       main = "PCA of samples (log2 CPM)")
  text(pcs$x[, 1], pcs$x[, 2], colnames(lcpm), pos = 3, cex = 0.6)
} else {
  plot.new(); text(0.5, 0.5, "not enough samples for PCA")
}
dev.off()
cat("QC done\n"); flush.console()

# ---------- DESeq2（可选） ----------
de_status <- "skipped: run_deseq2=false (T21 gating)"
n_sig <- 0L
de_res <- NULL

if (run_de && !is.null(ss)) {
  if (!requireNamespace("DESeq2", quietly = TRUE)) {
    de_status <- "failed: DESeq2 not available"
    cat(de_status, "\n")
  } else {
    suppressMessages(library(DESeq2))
    common <- intersect(colnames(cnt), ss$gsm)
    cat("samples matched: ", length(common), "\n", sep = "")
    if (length(common) >= 4) {
      cnt_m <- cnt[, common, drop = FALSE]
      ss_m <- ss[match(common, ss$gsm), ]
      grp <- factor(ss_m$group)
      cat("group sizes:\n"); print(table(grp))
      if (nlevels(grp) >= 2 && min(table(grp)) >= 2) {
        coldata <- data.frame(row.names = common, group = grp)
        dds <- DESeq2::DESeqDataSetFromMatrix(
          countData = round(as.matrix(cnt_m)), colData = coldata, design = ~ group)
        dds <- DESeq2::DESeq(dds)
        res <- DESeq2::results(dds, contrast = c("group", levels(grp)[2], levels(grp)[1]))
        res <- res[order(res$padj, na.last = TRUE), ]
        de_res <- data.frame(gene_id = rownames(res), baseMean = res$baseMean,
                             log2FoldChange = res$log2FoldChange,
                             lfcSE = res$lfcSE, stat = res$stat,
                             pvalue = res$pvalue, padj = res$padj)
        n_sig <- sum(!is.na(de_res$padj) & de_res$padj < padj_thr &
                       abs(de_res$log2FoldChange) > lfc_thr)
        de_status <- "success"
        cat("DEG: n=", nrow(de_res), " significant=", n_sig, "\n", sep = "")
      } else {
        de_status <- "blocked: need >=2 groups with n>=2 each"
        cat(de_status, "\n")
      }
    } else {
      de_status <- "blocked: fewer than 4 samples matched"
      cat(de_status, "\n")
    }
  }
}

if (is.null(de_res)) {
  write.csv(data.frame(message = de_status), get_out("deg_table"), row.names = FALSE)
} else {
  write.csv(de_res, get_out("deg_table"), row.names = FALSE)

  pdf(get_out("volcano"), width = 6, height = 5.2)
  plot(de_res$log2FoldChange, -log10(pmax(de_res$pvalue, 1e-300)),
       pch = 16, cex = 0.35,
       col = ifelse(!is.na(de_res$padj) & de_res$padj < padj_thr &
                      abs(de_res$log2FoldChange) > lfc_thr, "#D55E00", "#999999"),
       xlab = "log2 fold change", ylab = "-log10 P value", main = "Volcano (DESeq2)")
  abline(v = c(-lfc_thr, lfc_thr), lty = 2, col = "grey40")
  abline(h = -log10(padj_thr), lty = 2, col = "grey40")
  dev.off()
}

write.csv(
  data.frame(
    n_genes = nrow(cnt),
    n_samples = ncol(cnt),
    n_genes_qc = nrow(lcpm),
    run_deseq2 = run_de,
    deseq2_status = de_status,
    n_significant = n_sig,
    padj_threshold = padj_thr,
    log2fc_threshold = lfc_thr
  ),
  get_out("de_summary"), row.names = FALSE
)

cat("== rnaseq_de success (de=", de_status, ") ==\n", sep = "")
sink()
