"""纯单元测试（不依赖真实安装）：验证补丁锚点匹配与生成文本形状。

运行： python -m pytest tests -q   或   python tests/test_patches.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from patchkit import patches as PT           # noqa: E402
from patchkit.patcher import replace_once    # noqa: E402


def test_sidebar_applies_on_pristine():
    """干净上游文本 → 应能被替换，且生成物是合法形状。"""
    for key in ("chat", "main"):
        decl, arr, _keep, up, _sw = PT._VARIANTS[key]
        pristine = (decl + up + "return " + arr).encode()
        hit = None
        for old, new in PT._sidebar_candidates(key):
            ok, out, _why = replace_once(pristine, old, new)
            if ok:
                hit = out
                break
        assert hit, f"{key}: 未命中锚点"
        assert b"__JB_STB" in hit
        assert b"=[];," not in hit, "声明前缀多余分号（会写出语法错误）"
        assert hit.endswith(("return " + arr).encode())
        assert PT._wrapper(key) in hit
        # 关键回归 1：不得引入"会让归档/删除复活的"粘性缓存
        assert b"Z.map" not in hit, "不得缓存会话对象（会导致归档/删除无效）"
        # 关键回归 2：不得引入"会返回过期列表的"节流快照
        assert b"Z.snap" not in hit, "不得节流返回旧快照（首帧空列表会被永久缓存 → 侧栏空白）"
        assert b"45000" not in hit, "不得按时间节流（memo 依赖不变时永不重算）"
        assert b"removeItem" in hit, "必须清理旧版本的持久化快照"


def test_sidebar_migrates_v110_throttle_wrapper():
    """v1.1.0（节流快照，会导致侧栏空白）必须能被迁移。"""
    for key, legacy in PT.LEGACY_V110.items():
        blob = b"x;" + legacy + b";y"
        hit = None
        for old, new in PT._sidebar_candidates(key):
            ok, out, _why = replace_once(blob, old, new)
            if ok:
                hit = out
                break
        assert hit, f"{key}: v1.1.0 未命中"
        assert b"Z.snap" not in hit
        assert PT.SIDEBAR_DETECT in hit


def test_sidebar_returns_live_store_values():
    """语义回归：store 变化必须立刻反映到返回值（不缓存、不节流）。"""
    import re as _re
    w = PT._wrapper("chat").decode()
    assert "for(let r of e.values())" in w, "必须每帧遍历当前 store"
    assert "return t" in w
    assert "if(" not in w.split("return t")[0].split("e.values()){")[1][:200].replace("if(r&&C(r))", ""), \
        "遍历后不应再有条件缓存分支"


def test_sidebar_migrates_legacy_sticky_wrapper():
    """v1.0.0（粘性缓存，会导致归档/删除失效）必须能被迁移。"""
    for key, legacy in PT.LEGACY_V100.items():
        blob = b"x;" + legacy + b";y"
        hit = None
        for old, new in PT._sidebar_candidates(key):
            ok, out, _why = replace_once(blob, old, new)
            if ok:
                hit = out
                break
        assert hit, f"{key}: legacy 未命中"
        assert b"Z.map" not in hit
        assert PT.SIDEBAR_DETECT in hit
        assert PT._wrapper(key) in hit


def test_sidebar_applies_on_store_wide_variant():
    """中间态（已改成整库遍历）也应能命中。"""
    for key in ("chat", "main"):
        decl, arr, _keep, _up, sw = PT._VARIANTS[key]
        mid = (decl + sw + "return " + arr).encode()
        assert any(replace_once(mid, o, n)[0] for o, n in PT._sidebar_candidates(key))


def test_noise_applies_on_pristine_predicate():
    for key in ("chat", "main"):
        pristine = PT.NOISE_OLD_PRISTINE[key]
        blob = b"x=" + pristine + b";"
        assert any(replace_once(blob, o, n)[0] for o, n in PT._noise_candidates(key))
        hit = None
        for o, n in PT._noise_candidates(key):
            ok, out, _ = replace_once(blob, o, n)
            if ok:
                hit = out
                break
        assert hit and PT._noise_detect(key) in hit


def test_noise_test_then_revert():
    """已打 → detect 命中（幂等）。"""
    for key in ("chat", "main"):
        applied = PT.NOISE_OLD_PRISTINE[key] + PT._noise_new(key)
        assert PT._noise_detect(key) in applied


def test_limits_anchors_present_in_current_build():
    """limits 的两个锚点必须在同一文件里各出现一次（针对当前版本 bundle）。"""
    for bundle, cands in ((t["bundle"], t["cands"]) for t in PT.LIMITS_TARGETS):
        assert bundle in ("chat", "exa")
        olds = [o for o, _ in cands]
        assert b"rzq(x,p,m,{groupSessionLimits:I" in olds
        assert b"J=S+R,H=" in olds


def test_residue_repair():
    """人为构造 "}&&<残片>," → repair 应收敛成 "}," 并保持可解析。"""
    residue = (b'&&ae._meta?.["cognition.ai/isArchived"]!==!0'
               b'&&(0,Yt.getProposedByDevinId)(ae._meta)===void 0'
               b'&&ae.title!=="Devin Local session"')
    broken = b'[JB_DBG]x;y=()=>{}' + residue + b',z=1;'
    ok, out, why = PT.repair_residue(broken)
    assert ok, why
    assert residue not in out
    assert out.endswith(b",z=1;")


if __name__ == "__main__":
    import traceback
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception:
                fails += 1
                print(f"FAIL {name}")
                traceback.print_exc()
    print("失败" if fails else "全部通过")
    sys.exit(1 if fails else 0)
