#!/usr/bin/env Rscript
# P1 模块 pathway_enrichment：GO / KEGG 通路富集
#
# 论文原文用 MAPPFinder 做通路富集。MAPPFinder 为商业/遗留工具，云端不可安装，
# 这里以 clusterProfiler（GO + KEGG，BH 校正）实现等价的通路富集功能。
# 该替换必须在 handoff 中显式声明，不得隐瞒。
#
# 纪律：不硬编码路径，一切从 input JSON 读；随机种子固定；写日志。

suppressMessages({
  library(jsonlite)
  library(clusterProfiler)
  library(org.Hs.eg.db)
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
kegg_org <- as.character(get_par("kegg_organism", "hsa"))

deg <- read.csv(get_in("deg_table"), stringsAsFactors = FALSE)
sig <- deg[!is.na(deg$adj.P.Val) & deg$adj.P.Val < padj_thr & abs(deg$logFC) > lfc_thr, ]
cat("significant probes: ", nrow(sig), "\n", sep = "")

write_enrich <- function(res, path, kind) {
  if (is.null(res) || nrow(as.data.frame(res)) == 0) {
    write.csv(data.frame(message = paste0("no enriched ", kind, " terms")), path, row.names = FALSE)
    cat(kind, ": 0 terms\n", sep = "")
    return(invisible(NULL))
  }
  write.csv(as.data.frame(res), path, row.names = FALSE)
  cat(kind, ": ", nrow(as.data.frame(res)), " terms\n", sep = "")
}

if (nrow(sig) == 0) {
  write_enrich(NULL, get_out("enrich_go"), "GO")
  write_enrich(NULL, get_out("enrich_kegg"), "KEGG")
  write.csv(data.frame(n_input = 0L, note = "no significant genes; enrichment skipped"),
            get_out("enrich_summary"), row.names = FALSE)
  pdf(get_out("enrich_plot"), width = 6, height = 4)
  plot.new(); text(0.5, 0.5, "No significant genes\n(limma adj.P.Val threshold not met)")
  dev.off()
  cat("== pathway_enrichment success (empty) ==\n")
  sink()
  quit(status = 0)
}

# probe_id -> ENTREZID
if (!requireNamespace(annot_db, quietly = TRUE)) {
  stop(paste0("annotation package not available: ", annot_db))
}
ent <- AnnotationDbi::select(get(annot_db), keys = as.character(sig$probe_id),
                             columns = "ENTREZID", keytype = "PROBEID")
gene <- unique(na.omit(ent$ENTREZID))
cat("mapped ENTREZ genes: ", length(gene), "\n", sep = "")

if (length(gene) < 5) {
  write_enrich(NULL, get_out("enrich_go"), "GO")
  write_enrich(NULL, get_out("enrich_kegg"), "KEGG")
  write.csv(data.frame(n_input = length(gene), note = "too few genes for enrichment"),
            get_out("enrich_summary"), row.names = FALSE)
  pdf(get_out("enrich_plot"), width = 6, height = 4)
  plot.new(); text(0.5, 0.5, paste0("Too few mapped genes (n=", length(gene), ")"))
  dev.off()
  cat("== pathway_enrichment success (too few) ==\n")
  sink()
  quit(status = 0)
}

ego <- try(enrichGO(gene = gene, OrgDb = org.Hs.eg.db, ont = "ALL",
                    pAdjustMethod = "BH", qvalueCutoff = 0.05, readable = FALSE), silent = TRUE)
if (inherits(ego, "try-error")) ego <- NULL
write_enrich(ego, get_out("enrich_go"), "GO")

ek <- try(enrichKEGG(gene = gene, organism = kegg_org, pAdjustMethod = "BH",
                     qvalueCutoff = 0.05), silent = TRUE)
if (inherits(ek, "try-error")) ek <- NULL
write_enrich(ek, get_out("enrich_kegg"), "KEGG")

write.csv(
  data.frame(
    n_input_probes = nrow(sig),
    n_mapped_genes = length(gene),
    annotation_db = annot_db,
    tool = "clusterProfiler (paper used MAPPFinder; substituted, see handoff)"
  ),
  get_out("enrich_summary"), row.names = FALSE
)

pdf(get_out("enrich_plot"), width = 7, height = 5)
if (!is.null(ego) && nrow(as.data.frame(ego)) > 0) {
  print(barplot(ego, showCategory = min(20, nrow(as.data.frame(ego))), title = "GO enrichment (top terms)"))
} else {
  plot.new(); text(0.5, 0.5, "No enriched GO terms")
}
dev.off()

cat("== pathway_enrichment success ==\n")
sink()
