# 参考文献库（reference library）· 使用说明

> 定位：把自己要参考/模仿的论文丢进来，机器提取体裁结构，经人工确认后成为
> P2（结构序、声明块句式、D1 关键词表、R 系文献制式）、P3（R1 期刊核对、V1–V7）、
> P4-a（期刊方向实证）的**唯一真源**（元原则 8）。
> 这是纲要已有接口（p2_journal_matrix / V1–V7 / journal_database）的实例化数据源，不是新架构。

---

## 1. 丢一篇文章进库（两步）

```powershell
# ① 丢 PDF（整个目录里的 PDF 都会被处理）
python scripts/build_reference_library.py --add --src "你的PDF目录"

# ② 人工确认判读字段（机器只给事实，判读必须由人确认；确认过的才能被判据采信）
python scripts/build_reference_library.py --confirm <paper_id> --field structure_order --value S1
python scripts/build_reference_library.py --confirm <paper_id> --field reference_style --value numbered
python scripts/build_reference_library.py --confirm <paper_id> --field publisher --value BMC
```

查看库状态：`python scripts/build_reference_library.py --list`

## 2. 库内每篇论文有什么

| 文件 | 内容 | 谁生产 |
|---|---|---|
| `papers/<id>/<原PDF>` | 原件副本（溯源） | 复制 |
| `papers/<id>/<id>.txt` | 全文逐字留痕（可 grep 比对） | 机器 |
| `papers/<id>/<id>_structure.yaml` | 事实结构 + 判读字段 + status | 机器+人 |
| `reference_index.yaml` | 统一索引（唯一真源） | 脚本维护 |

## 3. 状态机（防幻觉的关键）

```text
draft ──人工确认（--confirm）──► confirmed
  │                                │
  └─ 仅供起草参考                  └─ 可被判据采信（D1 关键词表 / R1 核对 / V1–V7 取值）
```

- `facts`（节序、摘要形态、DOI 有无）是机器提取的**事实**，自动可信
- `structure_order` 等是**判读**，draft 时任何判据引用它 = FAIL（可构造：无留痕或未确认即采信）

## 4. 下游怎么消费（已接好的钩子）

| 消费方 | 用法 | 锚点 |
|---|---|---|
| P2 结构序判定 | 与 confirmed 样本比对节序 | `reference_index.yaml:papers[].confirmed_fields.structure_order` |
| P2 D1 声明扫描 | 用库内逐字子标题名 | `papers/<id>/<id>.txt`（grep 逐字） |
| P2 文献制式 R1/R2 | confirmed 的 reference_style | 同上 |
| P3 R1 期刊核对 / V1–V7 | 目标刊确定时，从库取该刊样例参数 | `confirmed_fields.publisher` |
| P4-a 方向预判 | likely_publishers 的实证支撑 | 同上 |

## 5. 库自身判据（进 P2 消融清单，X 系列）

| 判据 | 检查 | 变异用例 |
|---|---|---|
| X-R1 | 每条 structure.yaml 必须有同目录全文 txt 留痕 + extracted_at | 删 txt → FAIL |
| X-R2 | 判据采信 draft 条目 → FAIL | 引 draft → FAIL |
| X-R3 | confirmed 条目必须有 confirmed_by/confirmed_at | 缺 → FAIL |

## 6. 首批库存（5 篇，来自用户指定目录）

- `s12885-022-09296-8`（BMC Cancer）：**confirmed**，S1 / numbered / BMC —— S1 黄金样本
- `s10142-025-01598-x`（BMC 系）：**confirmed**，S2-a / author-year —— 含 generative AI 声明真实句式
- `fonc-11-711020` / `s13578-026-01590-3` / `s42003-025-08378-0`：draft，待人工确认
