# handoff · rnaseq_de · GSE174263

生成时间：2026-09-15T18:47:51+0000  
run_id：run_20260915_184751  
状态：success

## 1. 这一步是什么
RNA-seq 计数矩阵质控（T21 未通过，只做描述性 QC）

## 2. 这一步做了什么
读取计数矩阵 → library size/检出基因/样本相关/PCA

## 3. 输入是什么
- inputs/metadata/GSE174263_count_matrix.csv
- inputs/metadata/GSE174263_sample_sheet.csv

## 4. 输出是什么
- qc_summary: analysis/outputs/GSE174263/rnaseq_de/results/qc_summary.csv
- qc_libsize: analysis/outputs/GSE174263/rnaseq_de/figures/qc_libsize.pdf
- qc_correlation: analysis/outputs/GSE174263/rnaseq_de/figures/qc_correlation.pdf
- qc_pca: analysis/outputs/GSE174263/rnaseq_de/figures/qc_pca.pdf
- deg_table: analysis/outputs/GSE174263/rnaseq_de/results/deg_table.csv
- volcano: analysis/outputs/GSE174263/rnaseq_de/figures/volcano.pdf
- de_summary: analysis/outputs/GSE174263/rnaseq_de/results/de_summary.csv

## 5. 结果怎么样
见 qc_summary.csv / de_summary.csv

## 6. 能不能用
可用（描述性）

## 7. 下一步建议
T21 未通过：需补样本至每组 n≥6 才能做统计推断
