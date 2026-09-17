#!/usr/bin/env Rscript
# P1 模块 pathway_enrichment：GO / KEGG 通路富集（超几何检验 + BH 校正）
#
# 论文原文用 MAPPFinder 做通路富集；MAPPFinder 为商业/遗留工具，云端不可安装。
# clusterProfiler 在云端安装失败（依赖 treeio 加载异常，见 env_probe 探测结论）。
# 因此这里用 org.*.eg.db（由参数 org_db 指定，默认 org.Hs.eg.db；Drosophila 用 org.Dm.eg.db）
# 的 GO / KEGG 映射 + 超几何检验 + BH 校正实现等价的富集分析。
# 基因 ID → ENTREZ 映射按 PROBEID/ENSEMBL/FLYBASE/SYMBOL 顺序尝试，兼容微阵列与 RNA-seq。
# 该替换必须在 handoff 与 Methods 中显式声明，不得隐瞒。
#
# 纪律：不硬编码路径，一切从 input JSON 读；随机种子固定；写日志。

suppressMessages({
  library(jsonlite)
  library(AnnotationDbi)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) stop("usage: Rscript 01_main.R <input.json>")
cfg <- jsonlite::fromJSON(args[1])
set.seed(cfg$meta$random_seed)

log_path <- cfg$log$path
dir.create(dirname(log_path), recursive = TRUE, showWarnings = FALSE)
sink(log_path, append = TRUE, split = TRUE)
cat("== pathway_enrichment start ==\n")

get_in <- function(nm) cfg$inputs$path[cfg$inputs$name == nm][1]
get_out <- function(nm) cfg$outputs$path[cfg$outputs$name == nm][1]
get_par <- function(nm, default = NULL) if (!is.null(cfg$parameters[[nm]])) cfg$parameters[[nm]] else default

padj_thr <- as.numeric(get_par("padj_threshold", 0.05))
lfc_thr <- as.numeric(get_par("log2fc_threshold", 1.0))
annot_db <- as.character(get_par("annotation_db", "hgu133plus2.db"))
org_db <- as.character(get_par("org_db", "org.Hs.eg.db"))
min_size <- as.numeric(get_par("min_term_size", 5))
max_size <- as.numeric(get_par("max_term_size", 500))

for (o in unique(c(get_out("enrich_go"), get_out("enrich_kegg"), get_out("enrich_summary"), get_out("enrich_plot")))) {
  dir.create(dirname(o), recursive = TRUE, showWarnings = FALSE)
}

write_empty <- function(msg) {
  write.csv(data.frame(message = msg), get_out("enrich_go"), row.names = FALSE)
  write.csv(data.frame(message = msg), get_out("enrich_kegg"), row.names = FALSE)
  write.csv(data.frame(n_input = 0L, note = msg), get_out("enrich_summary"), row.names = FALSE)
  pdf(get_out("enrich_plot"), width = 7, height = 5)
  plot.new(); text(0.5, 0.5, msg, cex = 0.9)
  dev.off()
  cat("== pathway_enrichment success (empty: ", msg, ") ==\n", sep = "")
  sink(); quit(status = 0)
}

deg <- read.csv(get_in("deg_table"), stringsAsFactors = FALSE)
# 基因 ID 列：DESeq2 为 gene_id；limma 多为行名或 id
# 注意：else 必须与 } 同行。Rscript 按块解析，换行写 else 会直接报
# "unexpected 'else' in \"else\"" 并 Execution halted（本模块此前即因此静默失败）。
if ("gene_id" %in% names(deg)) {
  deg$probe_id <- deg$gene_id
} else if ("id" %in% names(deg)) {
  deg$probe_id <- deg$id
} else {
  deg$probe_id <- rownames(deg)
}
# 显著性列：兼容 DESeq2(padj / log2FoldChange) 与 limma(adj.P.Val / logFC)
padj_col <- if ("padj" %in% names(deg)) "padj" else if ("adj.P.Val" %in% names(deg)) "adj.P.Val" else NULL
lfc_col  <- if ("log2FoldChange" %in% names(deg)) "log2FoldChange" else if ("logFC" %in% names(deg)) "logFC" else NULL
if (is.null(padj_col) || is.null(lfc_col)) {
  write_empty("deg_table 缺少显著性列(padj/adj.P.Val 与 log2FoldChange/logFC)")
}
sig <- deg[!is.na(deg[[padj_col]]) & deg[[padj_col]] < padj_thr & abs(deg[[lfc_col]]) > lfc_thr, ]
cat("significant probes: ", nrow(sig), "\n", sep = "")

if (nrow(sig) == 0) {
  write_empty("no significant genes")
}

for (pkg in unique(c(annot_db, org_db))) {
  if (!requireNamespace(pkg, quietly = TRUE)) {
    write_empty(paste0("annotation package missing: ", pkg))
  }
}
# 必须 attach：requireNamespace 只让命名空间可用，不把注释对象放进搜索路径，
# 直接 get(annot_db) 会报 object not found（同理 org_*GO2ALLEGS / org_*PATH 也取不到）。
for (pkg in unique(c(annot_db, org_db))) {
  suppressPackageStartupMessages(library(pkg, character.only = TRUE))
}

db <- get(annot_db)

# 基因 ID → ENTREZ 映射：微阵列用 PROBEID；RNA-seq（如 GSE174263 / Drosophila）的
# deg_table 多为 FlyBase / Ensembl / 基因符号，需按可用 keytype 逐一尝试。
# 注意：keytype 列表里**不含** "ENTREZID"。曾把探针 ID 当 ENTREZID 去查，
# 结果得到 1:1 恒等映射（47320 探针 -> 47320 "基因"，universe 等于探针总数），
# 富集因此产出看似合理的 GO 条目——那是伪造成果，比直接失败更危险。
map_ids_to_entrez <- function(db, ids) {
  empty <- data.frame(PROBEID = character(0), ENTREZID = character(0))
  if (length(ids) == 0) return(empty)
  avail <- tryCatch(AnnotationDbi::columns(db), error = function(e) character(0))
  for (kt in c("PROBEID", "ENSEMBL", "FLYBASE", "SYMBOL")) {
    if (!(kt %in% avail)) next
    res <- tryCatch(
      AnnotationDbi::select(db, keys = as.character(ids), columns = "ENTREZID", keytype = kt),
      error = function(e) NULL)
    # 必须逐项防御：select 可能返回 NULL / 非 data.frame / 缺列，
    # 直接 nrow(res) 会在 res 为 NULL 时报 "argument is of length zero" 并中止整个模块。
    if (is.null(res) || !is.data.frame(res) || !"ENTREZID" %in% names(res)) {
      cat("  keytype ", kt, ": unusable\n", sep = "")
      next
    }
    res <- res[!is.na(res$ENTREZID) & res$ENTREZID != "", , drop = FALSE]
    cat("  keytype ", kt, ": ", nrow(res), " mapped rows\n", sep = "")
    if (nrow(res) > 0) return(res)
  }
  empty
}

# 芯片注释库的标准入口是 `{prefix}ENTREZID` 这个 Bimap 对象（如 illuminaHumanv4ENTREZID、
# hgu133plus2ENTREZID），键为探针 ID、值为 ENTREZ。比 select(keytype=) 更可靠：
# select 在多键映射下可能返回非预期结构，而 Bimap 是设计用途。
map_by_bimap <- function(pkg, ids) {
  empty <- data.frame(PROBEID = character(0), ENTREZID = character(0))
  if (length(ids) == 0) return(empty)
  obj_nm <- paste0(sub("\\.db$", "", pkg), "ENTREZID")
  if (!exists(obj_nm, inherits = TRUE)) {
    cat("  bimap ", obj_nm, ": absent\n", sep = "")
    return(empty)
  }
  bm <- get(obj_nm)
  lst <- tryCatch(AnnotationDbi::as.list(bm[as.character(ids)]), error = function(e) NULL)
  if (is.null(lst) || length(lst) == 0) {
    cat("  bimap ", obj_nm, ": no entries\n", sep = "")
    return(empty)
  }
  ent <- vapply(lst, function(x) {
    x <- x[!is.na(x)]
    if (length(x) == 0) NA_character_ else as.character(x[1])
  }, character(1))
  ok <- !is.na(ent) & ent != ""
  if (!any(ok)) {
    cat("  bimap ", obj_nm, ": all NA\n", sep = "")
    return(empty)
  }
  cat("  bimap ", obj_nm, ": ", sum(ok), " / ", length(ids), " probes -> ENTREZ\n", sep = "")
  data.frame(PROBEID = names(lst)[ok], ENTREZID = ent[ok], stringsAsFactors = FALSE)
}

# 兜底：探针 -> SYMBOL -> ENTREZ 中转。
# 部分芯片库（如 illuminaHumanv4.db）直连 PROBEID->ENTREZID 可能为空，
# 此时先取 SYMBOL 再用物种库 org.*.eg.db 转 ENTREZ，避免富集因映射为空而作罢。
map_via_symbol <- function(probe_db, org_pkg, ids) {
  empty <- data.frame(PROBEID = character(0), ENTREZID = character(0))
  if (length(ids) == 0) return(empty)
  avail <- tryCatch(AnnotationDbi::columns(probe_db), error = function(e) character(0))
  if (!("PROBEID" %in% avail) || !("SYMBOL" %in% avail)) return(empty)
  s <- tryCatch(AnnotationDbi::select(probe_db, keys = as.character(ids),
                                      columns = "SYMBOL", keytype = "PROBEID"),
                error = function(e) NULL)
  if (is.null(s) || !is.data.frame(s) || !all(c("PROBEID", "SYMBOL") %in% names(s))) return(empty)
  s <- s[!is.na(s$SYMBOL) & s$SYMBOL != "", , drop = FALSE]
  if (nrow(s) == 0) return(empty)
  cat("  symbol pivot: ", nrow(s), " probes -> symbols\n", sep = "")
  e <- tryCatch(AnnotationDbi::select(get(org_pkg), keys = unique(s$SYMBOL),
                                      columns = "ENTREZID", keytype = "SYMBOL"),
                error = function(e) NULL)
  if (is.null(e) || !is.data.frame(e) || !all(c("SYMBOL", "ENTREZID") %in% names(e))) return(empty)
  e <- e[!is.na(e$ENTREZID) & e$ENTREZID != "", , drop = FALSE]
  m <- match(s$SYMBOL, e$SYMBOL)
  out <- data.frame(PROBEID = s$PROBEID, ENTREZID = e$ENTREZID[m], stringsAsFactors = FALSE)
  out <- out[!is.na(out$ENTREZID) & out$ENTREZID != "", , drop = FALSE]
  cat("  symbol pivot: ", nrow(out), " probes -> ENTREZ\n", sep = "")
  out
}

# 三级兜底：① 芯片库 Bimap（探针→ENTREZ 的设计入口）② select 多 keytype ③ SYMBOL 中转
map_ids <- function(ids) {
  m <- map_by_bimap(annot_db, ids)
  if (nrow(m) == 0) m <- map_ids_to_entrez(db, ids)
  if (nrow(m) == 0) {
    cat("direct mapping empty -> SYMBOL pivot via ", org_db, "\n", sep = "")
    m <- map_via_symbol(db, org_db, ids)
  }
  m
}
map_all <- map_ids(deg$probe_id)
map_sig <- map_ids(sig$probe_id)

# 恒等映射防护：真实注释库不可能把每一个探针都映射到 ENTREZ。
# 一旦 universe 覆盖全部探针、显著基因又等于全部显著探针，那就是"输入原样回传"，
# 据此跑出的富集是伪造成果——宁可判空，也不产出。
if (length(unique(map_all$ENTREZID)) >= nrow(deg) && nrow(sig) > 0 &&
    length(unique(map_sig$ENTREZID)) >= nrow(sig)) {
  write_empty("mapping rejected: 100% coverage = identity passthrough, not real annotation")
}
universe <- unique(na.omit(map_all$ENTREZID))
gene <- unique(na.omit(map_sig$ENTREZID))
cat("universe genes: ", length(universe), "  significant genes: ", length(gene), "\n", sep = "")

if (length(gene) < 5 || length(universe) < 20) {
  write_empty("too few mapped genes for enrichment")
}

enrich_hyper <- function(gene, universe, term2gene, min_size, max_size) {
  K <- length(gene)
  N <- length(universe)
  terms <- names(term2gene)
  out <- vector("list", length(terms))
  j <- 0L
  for (i in seq_along(terms)) {
    tg <- term2gene[[i]]
    if (length(tg) == 0) next
    tg <- intersect(universe, tg)
    M <- length(tg)
    if (M < min_size || M > max_size) next
    k <- length(intersect(gene, tg))
    if (k == 0) next
    p <- stats::phyper(k - 1, M, N - M, K, lower.tail = FALSE)
    j <- j + 1L
    out[[j]] <- data.frame(term = terms[i], term_size = M, n_sig_in_term = k,
                           n_sig = K, n_universe = N, pvalue = p, stringsAsFactors = FALSE)
  }
  if (j == 0L) return(NULL)
  df <- do.call(rbind, out[seq_len(j)])
  df$p.adjust <- stats::p.adjust(df$pvalue, method = "BH")
  df$fold_enrichment <- (df$n_sig_in_term / df$term_size) / (df$n_sig / df$n_universe)
  df[order(df$pvalue), , drop = FALSE]
}

add_term_name <- function(df, keytype) {
  if (is.null(df) || nrow(df) == 0) return(df)
  if (!requireNamespace("GO.db", quietly = TRUE)) return(df)
  tn <- try(AnnotationDbi::select(GO.db::GO.db, keys = df$term, columns = "TERM", keytype = keytype),
            silent = TRUE)
  if (inherits(tn, "try-error")) return(df)
  tn <- tn[!duplicated(tn[[keytype]]), ]
  m <- match(df$term, tn[[keytype]])
  df$term_name <- tn$TERM[m]
  df
}

# ---------- GO ----------
# org.Hs.eg.db 的注释对象名为 org.Hs.egGO2ALLEGS / org.Hs.egPATH
org_prefix <- sub("\\.db$", "", org_db)
go_map <- try(AnnotationDbi::as.list(AnnotationDbi::get(paste0(org_prefix, "GO2ALLEGS"))), silent = TRUE)
go_res <- if (inherits(go_map, "try-error") || is.null(go_map)) NULL else enrich_hyper(gene, universe, go_map, min_size, max_size)
go_res <- add_term_name(go_res, "GOID")
if (is.null(go_res) || nrow(go_res) == 0) {
  write.csv(data.frame(message = "no enriched GO terms"), get_out("enrich_go"), row.names = FALSE)
  cat("GO: 0 terms\n")
} else {
  write.csv(go_res, get_out("enrich_go"), row.names = FALSE)
  cat("GO: ", nrow(go_res), " terms\n", sep = "")
}

# ---------- KEGG ----------
kegg_map <- try(AnnotationDbi::as.list(AnnotationDbi::get(paste0(org_prefix, "PATH"))), silent = TRUE)
kegg_res <- if (inherits(kegg_map, "try-error") || is.null(kegg_map)) NULL else enrich_hyper(gene, universe, kegg_map, min_size, max_size)
if (is.null(kegg_res) || nrow(kegg_res) == 0) {
  write.csv(data.frame(message = "no enriched KEGG pathways"), get_out("enrich_kegg"), row.names = FALSE)
  cat("KEGG: 0 pathways\n")
} else {
  write.csv(kegg_res, get_out("enrich_kegg"), row.names = FALSE)
  cat("KEGG: ", nrow(kegg_res), " pathways\n", sep = "")
}

write.csv(
  data.frame(
    n_input_probes = nrow(sig),
    n_mapped_genes = length(gene),
    n_universe = length(universe),
    annotation_db = annot_db,
    org_db = org_db,
    method = "hypergeometric test + BH (paper used MAPPFinder; clusterProfiler unavailable in cloud)",
    padj_threshold = padj_thr,
    min_term_size = min_size,
    max_term_size = max_size
  ),
  get_out("enrich_summary"), row.names = FALSE
)

# ---------- 图 ----------
pdf(get_out("enrich_plot"), width = 7.5, height = 5.5)
if (!is.null(go_res) && nrow(go_res) > 0) {
  top <- head(go_res[order(go_res$pvalue), ], min(20, nrow(go_res)))
  lab <- if (!is.null(top$term_name) && any(!is.na(top$term_name))) top$term_name else top$term
  lab <- substr(ifelse(is.na(lab), top$term, lab), 1, 45)
  par(mar = c(9, 12, 3, 2))
  bp <- barplot(-log10(top$p.adjust), names.arg = lab, horiz = TRUE, las = 1,
                col = "#4C72B0", border = NA,
                main = "GO enrichment (top 20 by p.adjust)",
                xlab = "-log10 adjusted P")
} else {
  plot.new(); text(0.5, 0.5, "No enriched GO terms")
}
dev.off()

cat("== pathway_enrichment success ==\n")
sink()
