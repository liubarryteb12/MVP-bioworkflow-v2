"""守卫框架基础层：三态判定 + 判据注册表 + 上下文。

纪律：
- 三态判定（pass / fail / N/A），没有第四态。
- 每条判据必须有唯一锚点（元原则 7：锚点必须唯一）。
- 只分档为 A 的判据才注册；B 档休眠、C 档不立（见 2-骨架与接口/判据分档表.md）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import yaml

PASS = "pass"
FAIL = "fail"
NA = "N/A"
VALID_STATUS = (PASS, FAIL, NA)

MISSING = object()


@dataclass
class Finding:
    check_id: str
    status: str
    anchor: str
    message: str = ""
    evidence: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "status": self.status,
            "anchor": self.anchor,
            "message": self.message,
            "evidence": self.evidence,
        }


@dataclass
class CheckMeta:
    check_id: str
    part: str  # P1 / P2 / P3 / P4
    tier: str  # A / B / C
    anchor: str
    description: str
    implemented: bool = False
    fn: Optional[Callable] = None


CHECKS: Dict[str, CheckMeta] = {}


def register(check_id: str, part: str, tier: str, anchor: str, description: str):
    """注册一条已实现的判据。"""

    def deco(fn):
        if check_id in CHECKS:
            raise ValueError(f"锚点/判据重复注册：{check_id}（元原则 7：锚点必须唯一）")
        CHECKS[check_id] = CheckMeta(check_id, part, tier, anchor, description, True, fn)
        return fn

    return deco


def declare(check_id: str, part: str, tier: str, anchor: str, description: str):
    """登记一条尚未实现的判据 —— 即空规。空规不得计入通过数。"""
    if check_id not in CHECKS:
        CHECKS[check_id] = CheckMeta(check_id, part, tier, anchor, description, False, None)


# ---------------------------------------------------------------- 上下文


@dataclass
class Context:
    workspace: str = "."
    docs: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)  # 运行参数（如 dataset），不参与字段检查

    def doc(self, relpath: str) -> Any:
        if relpath not in self.docs:
            self.docs[relpath] = load_yaml(os.path.join(self.workspace, relpath))
        return self.docs[relpath]

    def text(self, relpath: str) -> str:
        path = os.path.join(self.workspace, relpath)
        if not os.path.exists(path):
            return ""
        with open(path, "r", encoding="utf-8") as f:
            return f.read()


def load_yaml(path: str) -> Any:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def dump_yaml(path: str, doc: Any) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(doc, f, allow_unicode=True, sort_keys=False, default_flow_style=False)


def get_in(doc: Any, dotted: str, default: Any = MISSING) -> Any:
    cur = doc
    for key in dotted.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def missing_fields(doc: Any, paths: List[str]) -> List[str]:
    """返回 doc 中缺失的字段路径（值为 None 也算缺失）。"""
    out = []
    for p in paths:
        v = get_in(doc, p, MISSING)
        if v is MISSING or v is None:
            out.append(p)
    return out


# ---------------------------------------------------------------- 执行


def run_check(ctx: Context, check_id: str) -> Finding:
    meta = CHECKS.get(check_id)
    if meta is None:
        return Finding(check_id, NA, "-", "判据未登记")
    if not meta.implemented:
        return Finding(check_id, NA, meta.anchor, "空规（未实现），不计入通过数")
    try:
        finding = meta.fn(ctx)
    except Exception as exc:  # 判据自身崩溃：如实报告，不静默
        return Finding(check_id, FAIL, meta.anchor, f"判据执行异常：{exc}")
    if finding.status not in VALID_STATUS:
        return Finding(check_id, FAIL, meta.anchor, f"判据返回非法状态：{finding.status}")
    return finding


def run_part(ctx: Context, part: str) -> List[Finding]:
    return [
        run_check(ctx, cid)
        for cid, m in CHECKS.items()
        if m.part == part
    ]


def summarize(findings: List[Finding]) -> Dict[str, int]:
    s = {"pass": 0, "fail": 0, "N/A": 0}
    for f in findings:
        s[f.status] = s.get(f.status, 0) + 1
    return s
