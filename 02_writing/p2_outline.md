> 输出级别：L1
> 待定制项：目标期刊、故事线偏好、证据边界、图数上限、篇幅与截止
> 下一步：用户填完 8 项定制需求后升 L2
> T21 状态：fail（GSE174263 每组样本量 < 6，差异表达与富集已被 P1 质控门控阻断）

# 分级大纲（GSE174263）

## 一句话卖点
在 果蝇卵巢转录组对生殖系 Snr1 / mod(mdg4) 敲低的响应 主题下，
本轮 P1 仅产出描述性证据（n=4，组间样本量不足），**不构成可发表的统计主张**；
升 L2 的前置条件是补样本至每组 n>=6 后重跑 P1。

## 链条顺序（P0–P4 逻辑链）
- P0 背景问题：染质重塑与生殖细胞基因表达 的表达调控尚不清楚
- P1 主发现：**暂缺**（T21 FAIL，不允许提出统计主张）
- P2 支撑证据：描述性 QC 3 张（library size / 相关性 / PCA）
- P3 局限：样本量不足（每组 n<6）；无独立验证
- P4 展望：补样本后走 DESeq2 + 富集完整链路

## 各节要点（骨架，不铺陈）
- Introduction：背景 2-3 要点；gap statement 1 条（然而/尚未）
- Materials and Methods：数据来源（GEO GSE174263，登录号见数据可用性）、QC 步骤、软件版本
- Results：仅描述性图表呈现；**不写"显著"字样**（无统计支撑）
- Discussion：以局限为主；不得引入结果中未出现的机制词
- Declarations：8 项齐全（不适用写 Not applicable）

## 图序占位
- Figure 1 [占位：library size] -> 源：analysis/outputs/GSE174263/rnaseq_de/figures/qc_libsize.pdf
- Figure 2 [占位：sample correlation] -> 源：qc_correlation.pdf
- Figure 3 [占位：PCA] -> 源：qc_pca.pdf

## 主张-锚对应（主张强度 <= 证据上限 = 探索性）
- （本轮无统计证据条目：T21 门控生效，仅描述性）
