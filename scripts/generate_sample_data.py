"""
【已迁移】示例数据生成脚本
===========================
此脚本已迁移至 tests/fixtures/generate_sample_data.py
生产 data/ 目录不应包含模拟数据。

如需测试，请运行：
    python tests/fixtures/generate_sample_data.py

模拟 CSV 输出到 tests/fixtures/，不会污染生产 data/。
"""

import os
import sys

FIXTURE_SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tests", "fixtures", "generate_sample_data.py"
)

if __name__ == "__main__":
    print("=" * 60)
    print("此脚本已迁移至 tests/fixtures/generate_sample_data.py")
    print(f"运行: python {FIXTURE_SCRIPT}")
    print("=" * 60)
    if os.path.exists(FIXTURE_SCRIPT):
        sys.exit(0)
    else:
        print("错误：找不到迁移后的脚本")
        sys.exit(1)
