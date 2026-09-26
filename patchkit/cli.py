"""命令行入口：status / apply / verify / rollback / repair / pyright / shim / doctor。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import config
from . import patcher as P
from .patches import PATCHES, repair_residue

IFACE = "interface"


# ------------------------------------------------------------------ 工具

def load_bundles() -> dict:
    """一次读取三个 bundle：{key: {"path":Path, "ck":str|None, "data":bytes|None}}"""
    out = {}
    for key, path, ck in config.BUNDLES:
        out[key] = {"path": path, "ck": ck, "data": P.read(path) if path.exists() else None}
    return out


def _detect(data: bytes, detect: bytes) -> str:
    if data is None:
        return "NO-FILE"
    return "APPLIED" if detect in data else "not-applied"


def _checksum_state(key: str, data: bytes) -> str:
    ck = config.BUNDLE_MAP[key][1]
    if not ck:
        return "n/a"
    try:
        doc = json.loads(config.PRODUCT_JSON.read_text(encoding="utf-8"))
        want = (doc.get("checksums") or {}).get(ck)
    except Exception as exc:  # noqa: BLE001
        return f"product.json 读取失败: {exc}"
    return "match" if want == P.sha256_b64(data) else "MISMATCH"


# ------------------------------------------------------------------ status

def cmd_status(args) -> int:
    print("== 目标环境 ==")
    print(f"  app   : {config.APP_DIR}")
    print(f"  user  : {config.USERDATA}")
    print("\n== bundle 状态 ==")
    rows = []
    for key, info in load_bundles().items():
        data = info["data"]
        if data is None:
            rows.append((key, "NO-FILE", "-", "-"))
            continue
        ok, msg = P.js_parse_ok(data, key)
        rows.append((key, f"{len(data):,}", "PARSE_OK" if ok else msg, _checksum_state(key, data)))
    for key, size, parse, ck in rows:
        print(f"  {key:<5} size={size:<14} parse={parse:<28} checksum={ck}")
    print("\n== 补丁状态 ==")
    bundles = load_bundles()
    for patch in PATCHES:
        states = {}
        for t in patch["targets"]:
            b = t["bundle"]
            data = bundles[b]["data"]
            states[b] = _detect(data, t["detect"])
        print(f"  {patch['id']:<8} {patch['title']}")
        print("           " + "  ".join(f"{k}={v}" for k, v in states.items()))
    return 0


# ------------------------------------------------------------------ apply

def cmd_apply(args) -> int:
    only = set(args.only.split(",")) if args.only else {p["id"] for p in PATCHES}
    selected = [p for p in PATCHES if p["id"] in only]

    # 计划
    plan: dict[str, list[tuple[bytes, bytes, str]]] = {}
    notes: list[str] = []
    for patch in selected:
        for t in patch["targets"]:
            bundle, candidates = t["bundle"], t["cands"]
            data = config.BUNDLE_MAP[bundle][0]
            if not data.exists():
                notes.append(f"{bundle}: 文件不存在，跳过")
                continue
            blob = P.read(data)
            if t["detect"] in blob:
                notes.append(f"{patch['id']}/{bundle}: 已打，跳过")
                continue
            hit = None
            for old, new in candidates:
                ok, out, why = P.replace_once(blob, old, new)
                if ok:
                    hit = (old, new)
                    break
            if not hit:
                notes.append(f"{patch['id']}/{bundle}: 未找到匹配锚点（跳过）")
                continue
            plan.setdefault(bundle, []).append((hit[0], hit[1], patch["id"]))

    if not plan:
        print("无需改动：" + ("；".join(notes) if notes else "全部补丁已应用"))
        return 0

    print("== 计划改动 ==")
    for bundle, items in plan.items():
        print(f"  {bundle}: " + ", ".join(i[2] for i in items))

    if args.dry_run:
        print("\n(dry-run，未写入)")
        return 0

    bak = P.backup([(k, config.BUNDLE_MAP[k][0]) for k in plan], "patchkit-apply")
    print(f"\n备份目录: {bak}")

    failed = []
    for bundle, items in plan.items():
        path = config.BUNDLE_MAP[bundle][0]
        blob = P.read(path)
        for old, new, pid in items:
            ok, blob, why = P.replace_once(blob, old, new)
            if not ok:
                print(f"  ! {bundle}/{pid}: {why}")
                failed.append((bundle, pid))
        ok, msg = P.js_parse_ok(blob, bundle)
        if not ok:
            P.atomic_write(path, (bak / f"{bundle}__{path.name}").read_bytes())
            print(f"  ! {bundle}: 语法校验失败（{msg}）→ 已从备份回滚")
            failed.append((bundle, "parse"))
            continue
        P.atomic_write(path, blob)
        ck = config.BUNDLE_MAP[bundle][1]
        state = P.sync_product_checksum(ck, blob) if ck else "n/a"
        print(f"  ✓ {bundle}: 已写入，{msg}，checksum={state}")

    if notes:
        print("\n备注: " + "；".join(notes))
    return 1 if failed else 0


# ------------------------------------------------------------------ verify

def cmd_verify(args) -> int:
    bad = 0
    bundles = load_bundles()
    print("== 校验 ==")
    for key, info in bundles.items():
        data = info["data"]
        if data is None:
            print(f"  {key:<5} NO-FILE"); bad += 1; continue
        ok, msg = P.js_parse_ok(data, key)
        cks = _checksum_state(key, data)
        flag = "OK" if (ok and cks in ("match", "n/a")) else "FAIL"
        if flag == "FAIL":
            bad += 1
        print(f"  {key:<5} {flag:<5} parse={msg:<26} checksum={cks}")
    for patch in PATCHES:
        for t in patch["targets"]:
            bundle, data = t["bundle"], bundles[t["bundle"]]["data"]
            if data is not None and t["detect"] not in data:
                print(f"  {patch['id']}/{bundle}: 未应用"); bad += 1
    print("全部通过" if not bad else f"存在 {bad} 项问题")
    return 1 if bad else 0


# ------------------------------------------------------------------ rollback

def cmd_rollback(args) -> int:
    target = Path(args.dir) if args.dir else P.latest_backup(args.label or "")
    if not target or not Path(target).exists():
        print("找不到备份目录"); return 1
    if not (Path(target) / "manifest.json").exists():
        print(f"{target} 没有 manifest.json（多为手工备份），无法自动还原；请手动拷回原路径。")
        return 1
    print(f"从备份还原: {target}")
    for line in P.restore(Path(target)):
        print("  " + line)
    return cmd_verify(args)


# ------------------------------------------------------------------ repair

def cmd_repair(args) -> int:
    changed_any = False
    for key, info in load_bundles().items():
        path, ck, data = info["path"], info["ck"], info["data"]
        if data is None:
            continue
        ok, out, why = repair_residue(data)
        if not ok:
            print(f"  {key}: {why}")
            continue
        blob_ok, msg = P.js_parse_ok(out, key)
        if not blob_ok:
            print(f"  {key}: 修复后仍无法解析（{msg}），未写入"); continue
        print(f"  {key}: {why}；{msg}" + ("（dry-run）" if args.dry_run else ""))
        if not args.dry_run:
            P.backup([(key, path)], "patchkit-repair")
            P.atomic_write(path, out)
            if ck:
                print(f"           checksum={P.sync_product_checksum(ck, out)}")
        changed_any = True
    if not changed_any:
        print("未发现残片")
    return 0


# ------------------------------------------------------------------ pyright

PYRIGHT_EXCLUDES = [
    "**/node_modules", "**/node_modules/**", "**/__pycache__", "**/.git", "**/.venv", "**/venv",
    "**/site-packages", "**/*.egg-info",
]


def cmd_pyright(args) -> int:
    cfg_path = config.workspace_pyrightconfig(args.workspace)
    extra = list(args.extra or [])
    if not args.workspace:
        print("需要 --workspace <工作区目录>"); return 1
    doc = {}
    if cfg_path.exists():
        doc = json.loads(cfg_path.read_text(encoding="utf-8"))
    excludes = list(doc.get("exclude") or [])
    add = PYRIGHT_EXCLUDES + extra
    added = [e for e in add if e not in excludes]
    if not added:
        print(f"{cfg_path}: 已是最新（{len(excludes)} 条 exclude）")
        return 0
    excludes.extend(added)
    doc["exclude"] = excludes
    print(f"{cfg_path}: 新增 {len(added)} 条 exclude" + ("（dry-run）" if args.dry_run else ""))
    for e in added:
        print("   + " + e)
    if not args.dry_run:
        import shutil, time
        if cfg_path.exists():
            shutil.copy2(cfg_path, cfg_path.with_suffix(f".json.bak-{time.strftime('%Y%m%d-%H%M%S')}"))
        cfg_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


# ------------------------------------------------------------------ shim

SHIM_MARK = "# [patchkit]"


def cmd_shim(args) -> int:
    path = config.SHIM_PATH
    if not path.exists():
        print(f"找不到 {path}"); return 1
    src = path.read_text(encoding="utf-8")
    if SHIM_MARK in src:
        print("shim 已打过预热补丁"); return 0

    old_threads = ("    threading.Thread(target=_pump_in, daemon=True).start()\n"
                   "    threading.Thread(target=_expander, daemon=True).start()")
    new_threads = (f"    {SHIM_MARK} 预热：进程启动即读库，避免首个 session/list 拿到未展开的短列表\n"
                   "    threading.Thread(target=_db_dirs_and_order, daemon=True).start()\n" + old_threads)
    old_fb = ("    dirs, order = _db_dirs_and_order()\n    if not dirs:\n"
              "        if _merge_cache[\"sessions\"] is not None:")
    new_fb = ("    dirs, order = _db_dirs_and_order()\n"
              f"    {SHIM_MARK} 冷启动读库失败时必须重试，不能把短列表交给 IDE\n"
              "    for _ in range(20):\n        time.sleep(0.75)\n"
              "        dirs, order = _db_dirs_and_order()\n        if dirs:\n            break\n"
              "    if not dirs:\n        if _merge_cache[\"sessions\"] is not None:")

    if src.count(old_threads) != 1 or src.count(old_fb) != 1:
        print("shim 结构与预期不符，未改动（可能已被其它工具改过）"); return 1
    out = src.replace(old_threads, new_threads).replace(old_fb, new_fb)
    if args.dry_run:
        print("（dry-run）将写入预热与重试逻辑"); return 0
    import py_compile, shutil, time
    bak = path.with_name(path.name + ".bak-" + time.strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(path, bak)
    tmp = path.with_suffix(".py.new")
    tmp.write_text(out, encoding="utf-8")
    py_compile.compile(str(tmp), doraise=True)
    tmp.replace(path)
    print(f"已打补丁；备份 {bak}")
    return 0


# ------------------------------------------------------------------ doctor

def cmd_doctor(args) -> int:
    import shutil
    print("== 环境 ==")
    print(f"  python      : {sys.version.split()[0]}")
    print(f"  node        : {shutil.which('node') or '未找到（bundle 语法校验需要）'}")
    print(f"  gh          : {shutil.which('gh') or '未安装（推 GitHub 需要）'}")
    print(f"  app dir     : {config.APP_DIR} {'OK' if config.APP_DIR.exists() else '缺失'}")
    print(f"  product.json: {'OK' if config.PRODUCT_JSON.exists() else '缺失'}")
    print(f"  userdata    : {config.USERDATA} {'OK' if config.USERDATA.exists() else '缺失'}")
    print(f"  shim        : {config.SHIM_PATH} {'OK' if config.SHIM_PATH.exists() else '不存在'}")
    for key, path, _ck in config.BUNDLES:
        print(f"  bundle {key:<5}: {'OK' if path.exists() else '缺失'}  {path}")
    if config.BACKUP_ROOT.exists():
        dirs = [d for d in config.BACKUP_ROOT.iterdir() if d.is_dir()]
        usable = [d for d in dirs if (d / "manifest.json").exists()]
        print(f"  backups     : {len(dirs)} 个目录（{len(usable)} 个可一键回滚）@ {config.BACKUP_ROOT}")
    return 0


# ------------------------------------------------------------------ main

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="devin-patchkit",
                                 description="Devin Desktop(Windsurf 内核) 本地补丁工具包")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="查看 bundle 与补丁状态").set_defaults(func=cmd_status)
    sub.add_parser("verify", help="语法 + product.json 校验值 + 补丁齐全性").set_defaults(func=cmd_verify)
    sub.add_parser("doctor", help="环境自检").set_defaults(func=cmd_doctor)

    a = sub.add_parser("apply", help="打补丁（幂等，自动备份与回滚）")
    a.add_argument("--dry-run", action="store_true")
    a.add_argument("--only", help="只打指定补丁，逗号分隔：sidebar,noise,limits")
    a.set_defaults(func=cmd_apply)

    r = sub.add_parser("rollback", help="从备份还原")
    r.add_argument("--dir", help="指定备份目录；缺省用最新")
    r.add_argument("--label", help="按标签筛选最新备份，如 apply/repair")
    r.set_defaults(func=cmd_rollback)

    p = sub.add_parser("repair", help="修复历史补丁留下的语法残片（白屏）")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_repair)

    y = sub.add_parser("pyright", help="给工作区 pyrightconfig.json 注入 exclude（治枚举超时告警）")
    y.add_argument("--workspace", required=True)
    y.add_argument("--extra", nargs="*", help="额外排除目录，例如 工具库/源码")
    y.add_argument("--dry-run", action="store_true")
    y.set_defaults(func=cmd_pyright)

    s = sub.add_parser("shim", help="给 ACP shim 打预热+重试补丁")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_shim)
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
