# P3 排版检查报告（check_report）

- dataset: GSE174263
- timestamp: 2026-09-16T11:55:02+0800
- P2 输出级别：L1（骨架，无正文实体）

## 判定汇总

| 判据组 | 计划 A 档 | 本轮已实现 | 判定 |
|---|---|---|---|
| 排版守卫 T1–T69 | 85（分档表） | 0（守卫代码未实现，空规） | N/A |
| 出图守卫 F1–F29 | （与参数卡重合） | 部分（五格式由 P1 figure_export 承担） | 见下 |
| 降级守卫 D1–D14 | — | 0 | N/A |

## 本轮可机检项（来自 P1 figure_export）

- qc_libsize.pdf：pdf=ok svg=ok png=ok tiff=ok jpg=ok
- qc_correlation.pdf：pdf=ok svg=ok png=ok tiff=ok jpg=ok
- qc_pca.pdf：pdf=ok svg=ok png=ok tiff=ok jpg=ok

## 纪律声明

- 未生成投稿包：P2 无正文实体，生成投稿包属伪造交付，不做。
- 排版守卫为空规状态：已按《判据分档表》登记，不计入通过。
- 五格式导出在 P1 侧完成（pdftocairo 矢量优先，见 figure_export_*.yaml）。
