#!/usr/bin/env python3
"""把《工作安排提示词.txt》的数据集清单同步为《原始数据集输入选用选择.txt》的新口径。

只动数据集相关区间（§2 / §4 / §6 / §7 data_source / §8 datasets），其余（流程、workflow、纪律）不动。
所有替换区间以原文锚点定位，替换前备份原文件为 .bak-<ts>。
"""

from __future__ import annotations

import re
import shutil
import sys
import time

SRC = r"d:\00.AIagent\codebuddy_workspace\生信分析+SCI文章写作工作流搭建\第二版\06.原始输入材料\工作安排提示词.txt"

NEW_S2 = """## 2. 数据集清单

> **2026-09-17 更新**：数据源按《原始数据集输入选用选择.txt》重新筛选
>（筛选标准：数据量小、全链路覆盖、配套元数据齐全、格式标准）。
> 旧清单（GSE7451 / GSE2379 / GSE10036 / GSE251926 / GSE255370 / GSE292083）**废弃**，
> 原文见本文件 git 历史（.bak 备份）。
> 同步口径：判据编号采用 02 版修订合集 v3 的 P1 立号体系（`P1-QC-04` 等），
> 组别样本量下限为 **每组 ≥3**（旧 T21 的 n≥6 已废止）。

### 2.1 基础验证集（首次功能验证 · GEO 常规链路）

```yaml
basic_datasets:
  - id: GSE31210
    priority: 1
    title: Gene expression data for pathological stage I-II lung adenocarcinomas
    samples: 246（226 LUAD tumor + 20 normal）
    platform: GPL570 (Affymetrix HG-U133 Plus 2.0)
    file_size: series matrix ~80 MB；RAW.tar >2GB（超过 300MB 自动降载为表达矩阵）
    data_source: https://ftp.ncbi.nlm.nih.gov/geo/series/GSE31nnn/GSE31210/matrix/
    claim_verification: >
      2026-09-17 经 scripts/verify_dataset_claims.py 实测核验：246 样本 = 226 tumor + 20 normal，
      与材料描述完全一致；留痕 04_journal/snapshots/geo_meta/GSE31210_verify.txt
    paper:
      citation: 见 GEO series metadata（PubMed 关联随快照落盘）
      analysis_pipeline:
        - 数据下载：series matrix 表达矩阵（提交者已 RMA 处理，跳过 CEL/RMA/MAS5，如实记录）
        - QC：表达分布检查（箱线图/密度图），作为 QC-08 标准化检查证据
        - 差异表达：limma，tumor vs normal，BH 校正
        - 富集：GO/KEGG 超几何 + BH（探针注释 hgu133plus2.db）
        - 出图：火山图/富集条形图，五格式（pdf/svg/png/tiff/jpg）
    validation_focus:
      - P1 主干全链路：下载 → 可用性分析 → QC-04 → limma → 富集 → 五格式 → 接口文件
      - P1-QC-04：226 vs 20，每组 ≥3 → pass（统计效力充分的正样本）
      - 大数据集降载机制（RAW.tar >300MB 自动切 series matrix）
      - manifest / 四件套 / p1_to_p2 与 p1_to_p4 接口文件产出
    expected:
      - 差异基因数量级：数百至数千（226 vs 20 统计效力充分）
      - GO/KEGG 富集均有实质结果
      - 五格式图 ≥3 张，单文件 <10MB
```

### 2.2 进阶集（基础跑通后 · 单细胞 / 空间链路）

```yaml
advanced_datasets:
  - id: GSE299393
    priority: 2
    title: 单细胞链路（10X scRNA-seq，MDA-MB-231 异种移植 + 匹配转移灶）
    data_type: 10X scRNA-seq（barcodes/features/matrix 三件套，Read10X 原生输入）
    file_size: 典型 50-200 MB
    validation_focus:
      - single_cell 模块全流程：QC（线粒体比例/基因数）→ 标准化 → PCA → 聚类 → UMAP → Marker
      - sample_size / batch_effect 判据触发
    status: 待接入（需先核实 suppl 文件清单与 Read10X 集成）

  - id: GSE237308
    priority: 3
    title: 空间转录组链路（Visium S9 切片，Domain 5 = 397 spots）
    data_type: Visium（filtered_feature_bc_matrix.h5 + spatial.tar.gz）
    file_size: 5-15 MB（三条链路中最小）
    validation_focus:
      - 空间数据读入 → spot 级 QC → 聚类 → 空间域识别 → 空间可视化
    status: 待接入（需确认空间模块集成：Seurat Load10X_Spatial 或等价 parser）
```

---

## 3. 执行指令"""

NEW_S4 = """## 4. 数据集验证矩阵

```yaml
validation_matrix:
  GSE31210:
    stage: 基础（首次功能验证 · GEO 常规链路）
    verifies:
      - P1 主干全链路（质控/标准化检查/差异/富集/出图）
      - P1-QC-04（每组 ≥3）→ pass
      - 大数据集降载（series matrix 自动切换）
      - manifest / 四件套 / 接口文件产出
    expected:
      - 差异基因：数百至数千
      - GO/KEGG 富集有实质结果
      - 五格式图 ≥3 张
  GSE299393:
    stage: 进阶（单细胞链路）
    verifies: [single_cell 模块全流程, sample_size/batch_effect 判据]
    expected: 待接入后实测
  GSE237308:
    stage: 进阶（空间转录组链路）
    verifies: [spatial 模块全流程（Visium 全链路）]
    expected: 待接入后实测
```

---

## 5. GitHub Actions Workflow 模板"""

NEW_S6 = """## 6. 判据触发预期

```yaml
criteria_expectations:
  P1-QC-04（组别样本量 ≥3 · 02版修订合集 v3；旧 T21 n≥6 已废止）:
    - GSE31210: 226 vs 20 → pass
    - GSE174263（此前验证集）: 2 vs 2 → fail（门控生效）
    - GSE61444（此前验证集）: 每组 2 → fail（门控生效）
  QC-08（标准化检查）:
    - GSE31210: series matrix 直连（提交者已 RMA）→ 分布检查通过 + 如实备注，不伪造标准化步骤
  IMG 系列（五格式 / ≤10MB）:
    - GSE31210: 火山图 + 富集图 + QC 图，五格式齐全
```

---

## 7. 执行注意事项"""

NEW_DATA_SOURCE = """  data_source:
    - 所有数据集从 NCBI GEO 下载
    - 表达矩阵（大数据集降载）：https://ftp.ncbi.nlm.nih.gov/geo/series/{GSExxx}nnn/{GSExxx}/matrix/{GSExxx}_series_matrix.txt.gz
    - 原始文件（小数据集）：https://ftp.ncbi.nlm.nih.gov/geo/series/{GSExxx}nnn/{GSExxx}/suppl/
    - 基础集 GSE31210 先跑（主干验证），进阶集（单细胞/空间）按需"""

NEW_REFS = """```yaml
references:
  datasets:
    - GSE31210: Gene expression data for pathological stage I-II lung adenocarcinomas（246 样本，GPL570；实测核验 2026-09-17）
    - GSE299393: 单细胞链路验证集（10X，待接入）
    - GSE237308: 空间转录组链路验证集（Visium S9，待接入）
    - 历史验证集（已跑通防错门控）: GSE174263 / GSE61444（T21 时代，FAIL 案例留痕在 9-测试报告）
"""


def replace_between(text: str, start: str, end: str, new: str) -> tuple[str, bool]:
    i = text.find(start)
    j = text.find(end, i + len(start)) if i >= 0 else -1
    if i < 0 or j < 0:
        return text, False
    return text[:i] + new + text[j:], True


def main() -> int:
    ts = time.strftime("%Y%m%d_%H%M%S")
    shutil.copy2(SRC, SRC + f".bak-{ts}")

    with open(SRC, "r", encoding="utf-8") as f:
        text = f.read()

    done = []
    text, ok = replace_between(text, "## 2. 数据集清单", "## 3. 执行指令", NEW_S2 + "\n\n---\n\n")
    done.append(("§2 数据集清单", ok))
    text, ok = replace_between(text, "## 4. 数据集验证矩阵", "## 5. GitHub Actions Workflow 模板",
                               NEW_S4 + "\n\n---\n\n")
    done.append(("§4 验证矩阵", ok))
    text, ok = replace_between(text, "## 6. 判据触发预期", "## 7. 执行注意事项", NEW_S6 + "\n\n---\n\n")
    done.append(("§6 判据预期", ok))
    text, ok = replace_between(text, "  data_source:", "\n  timeout:", NEW_DATA_SOURCE + "\n")
    done.append(("§7 data_source", ok))
    text, ok = replace_between(text, "```yaml\nreferences:\n  datasets:", "  analysis_tools:",
                               NEW_REFS + "\n  analysis_tools:")
    done.append(("§8 datasets", ok))

    with open(SRC, "w", encoding="utf-8") as f:
        f.write(text)

    for name, ok in done:
        print(f"{'OK ' if ok else 'SKIP'} {name}")
    return 0 if all(ok for _, ok in done) else 1


if __name__ == "__main__":
    sys.exit(main())
