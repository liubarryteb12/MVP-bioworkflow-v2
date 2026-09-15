"""P1-P4 守卫包。

用法：
    python scripts/guard_selftest.py --part P4 --fixture     # 骨架自测（内置基线）
    python scripts/guard_selftest.py --part P4               # 真实运行（读工作空间文件）
"""

__all__ = ["base", "mutation", "checks_p4", "fixtures_p4"]
