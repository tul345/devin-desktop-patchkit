#!/usr/bin/env python
"""入口：python devin-patchkit.py <status|apply|verify|rollback|repair|pyright|shim|doctor>"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:  # Windows 控制台默认 GBK，强制 UTF-8 避免中文乱码
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from patchkit.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
