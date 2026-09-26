"""字节级补丁引擎：备份 → 替换 → 语法校验 → 同步 product.json 校验值。

设计要点
- 幂等：每个补丁都有 detect 特征串，命中即视为已打，不重复改。
- 原子：写临时文件后 os.replace，绝不半途留下截断文件（踩过这个坑）。
- 可回滚：每次改动前把原文件 + manifest.json 存到 Backups/<label>-<时间戳>/。
- 可验证：用 node --check 以 ESM 方式解析 bundle；再核对 product.json 的 sha256。
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from . import config


class PatchError(RuntimeError):
    pass


def read(p: Path | str) -> bytes:
    return Path(p).read_bytes()


def atomic_write(p: Path | str, data: bytes) -> None:
    p = Path(p)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        shutil.copymode(p, tmp)
        os.replace(tmp, p)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def sha256_b64(data: bytes) -> str:
    return base64.b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")


def find_node() -> str:
    node = shutil.which("node")
    if not node:
        raise PatchError("找不到 node，无法做 bundle 语法校验")
    return node


def js_parse_ok(data: bytes, tag: str) -> tuple[bool, str]:
    """把内容当 ESM 解析一次；返回 (是否通过, 摘要)。"""
    node = find_node()
    tmp = Path(tempfile.gettempdir()) / f"patchkit_{tag}_{os.getpid()}.mjs"
    try:
        tmp.write_bytes(data)
        proc = subprocess.run([node, "--check", str(tmp)], capture_output=True, text=True, timeout=180)
        if proc.returncode == 0:
            return True, "PARSE_OK"
        msg = (proc.stderr or "").strip().splitlines()
        first = next((l for l in msg if "SyntaxError" in l), msg[0] if msg else "unknown")
        return False, first[:160]
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


def sync_product_checksum(key: str, data: bytes) -> str:
    """把 data 的 sha256 写回 product.json 的 checksums[key]。"""
    prod = config.PRODUCT_JSON
    raw = prod.read_text(encoding="utf-8")
    doc = json.loads(raw)
    checks = doc.get("checksums") or {}
    if key not in checks:
        return "key-absent"
    want = sha256_b64(data)
    if checks[key] == want:
        return "ok"
    checks[key] = want
    doc["checksums"] = checks
    prod.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return "updated"


def backup(paths: list[tuple[str, Path]], label: str) -> Path:
    """paths = [(key, 原始路径), ...]；返回备份目录。"""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest = config.BACKUP_ROOT / f"{label}-{stamp}"
    dest.mkdir(parents=True, exist_ok=True)
    manifest = {"created": stamp, "label": label, "files": {}}
    for key, path in paths:
        if not Path(path).exists():
            continue
        name = f"{key}__{Path(path).name}"
        shutil.copy2(path, dest / name)
        manifest["files"][key] = {"orig": str(path), "backup": name,
                                 "size": Path(path).stat().st_size}
    (dest / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return dest


def restore(backup_dir: Path) -> list[str]:
    """按 manifest 还原备份目录里的文件。"""
    manifest = json.loads((Path(backup_dir) / "manifest.json").read_text(encoding="utf-8"))
    done = []
    for key, info in manifest.get("files", {}).items():
        src = Path(backup_dir) / info["backup"]
        dst = Path(info["orig"])
        atomic_write(dst, src.read_bytes())
        done.append(f"{key} -> {dst}")
    return done


def latest_backup(label: str = "") -> Path | None:
    root = config.BACKUP_ROOT
    if not root.exists():
        return None
    cands = [d for d in root.iterdir() if d.is_dir() and (d / "manifest.json").exists()
             and (label in d.name if label else True)]
    if not cands:
        return None
    return max(cands, key=lambda d: d.stat().st_mtime)


def replace_once(data: bytes, old: bytes, new: bytes) -> tuple[bool, bytes, str]:
    n = data.count(old)
    if n == 0:
        return False, data, "not-found"
    if n > 1:
        return False, data, f"ambiguous({n})"
    return True, data.replace(old, new), "replaced"
