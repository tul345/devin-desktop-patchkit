"""补丁定义（字节级）。

三条独立补丁，各自幂等：

  sidebar  —— 侧栏会话数据源：只用当前 store 现值构造列表
  noise    —— 无标题且无消息的空会话（会渲染成 "Devin Local session"）不显示
  limits   —— 放开侧栏组件的"每组上限"和"总量上限"（默认只渲染 25 条的那道闸门）

另外提供 repair_residue()：修复历史补丁留下的语法残片（白屏根因）。

sidebar 的三个版本（重要，别再踩）：

  v1.0.0  用 globalThis.__JB_STB.map 记住"见过的会话"，下一帧把不在列表里的旧对象
          重新加回列表并持久化到 localStorage。后果：归档/删除的会话被复活，
          用户感觉"归档、删除点了没反应"。
  v1.1.0  加了 45 秒节流并返回旧快照 Z.snap。后果：首帧 store 为空时把 [] 存进快照，
          之后真实数据到达也被节流拦下；而 useMemo 依赖不变就不会重算，
          于是侧栏永久空白、"加载圈不转"。
  v1.2.0  只用当前 store 现值构造列表：不缓存、不节流、不落盘。
          归档/删除立即生效；store 一变列表就跟着变。

迁移：首次运行 v1.2.0 时会清掉旧版本遗留的内存缓存与 localStorage 快照。
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------- 变体定义

_VARIANTS = {
    # key: (声明前缀, 累加数组, 可见性判定函数, 上游遍历(按分页 id 取), 整库遍历)
    "chat": ("let e=tfe(f),t=[];", "t", "C",
             "for(let n of s){let r=e.get(n);r&&C(r)&&t.push(r)}",
             "for(let r of e.values()){r&&C(r)&&t.push(r)}"),
    "main": ("let ae=QYn(X),he=[];", "he", "ee",
             "for(let Se of y){let _e=ae.get(Se);_e&&ee(_e)&&he.push(_e)}",
             "for(let _e of ae.values()){_e&&ee(_e)&&he.push(_e)}"),
}

_SIDEBAR_BUNDLES = {
    "chat": ["chat", "exa"],
    "main": ["main"],
}

# 生成代码里的迁移版本号：只有 v1.2.0 会写它
_MIGRATION_KEY = "__zs.v=2"
SIDEBAR_DETECT = _MIGRATION_KEY.encode()


def _wrapper(key: str) -> bytes:
    """生成侧栏数据源包装代码（v1.2.0）：只用 store 现值，不缓存不节流。"""
    decl, arr, keep, _up, _sw = _VARIANTS[key]
    item = "r" if key == "chat" else "_e"
    src = "e" if key == "chat" else "ae"
    return (
        decl.rstrip(";")
        + ",__zs=(globalThis.__JB_STB||(globalThis.__JB_STB={})),__z1=__zs.v;"
          # 一次性迁移：清理旧版本的内存缓存与本地快照（它们会复活已删除的会话）
          "if(__z1!==2){__zs.v=2;try{const __ph=__zs.map,__ps=localStorage.getItem(\"__JB_SESS\");"
          "if(__ph&&__ph.clear)__ph.clear();if(__ps)localStorage.removeItem(\"__JB_SESS\")}catch(_){}}"
          "for(let " + item + " of " + src + ".values()){if(" + item + "&&" + keep + "(" + item + "))"
          + arr + ".push(" + item + ")}"
          "return " + arr
    ).encode("utf-8")


# 历史版本生成过的包装文本（仅用于迁移识别）
LEGACY_V110 = {
    "chat": b'let e=tfe(f),t=[],Z=(globalThis.__JB_STB||(globalThis.__JB_STB={snap:null,sig:"",ts:0}));for(let r of e.values()){if(r&&C(r))t.push(r)}try{const __ph=(globalThis.__JB_STB||{}).map,__ps=localStorage.getItem("__JB_SESS");if(__ph&&__ph.clear)__ph.clear();if(__ps)localStorage.removeItem("__JB_SESS")}catch(_){}let sg_=t.map(x=>x.sessionId).join("|"),now_=Date.now();if(!Z.snap||(sg_!==Z.sig&&now_-Z.ts>45000)){Z.snap=t;Z.sig=sg_;Z.ts=now_}return Z.snap',
    "main": b'let ae=QYn(X),he=[],Z=(globalThis.__JB_STB||(globalThis.__JB_STB={snap:null,sig:"",ts:0}));for(let _e of ae.values()){if(_e&&ee(_e))he.push(_e)}try{const __ph=(globalThis.__JB_STB||{}).map,__ps=localStorage.getItem("__JB_SESS");if(__ph&&__ph.clear)__ph.clear();if(__ps)localStorage.removeItem("__JB_SESS")}catch(_){}let sg_=he.map(x=>x.sessionId).join("|"),now_=Date.now();if(!Z.snap||(sg_!==Z.sig&&now_-Z.ts>45000)){Z.snap=he;Z.sig=sg_;Z.ts=now_}return Z.snap',
}
LEGACY_V100 = {
    "chat": b'let e=tfe(f),t=[],Z=(globalThis.__JB_STB||(globalThis.__JB_STB={snap:null,sig:"",ts:0,map:new Map()})),L=new Set();for(let r of e.values()){if(r&&C(r)){t.push(r);L.add(r.sessionId);Z.map.set(r.sessionId,r)}}if(!Z.ld){Z.ld=!0;try{const rw=localStorage.getItem("__JB_SESS");if(rw){const ar=JSON.parse(rw);for(const so of ar){so&&so.sessionId&&Z.map.set(so.sessionId,so)}}}catch(_){}}for(let[k_,v_]of Z.map){!L.has(k_)&&C(v_)&&t.push(v_)}try{if(!Z.pAt||Date.now()-Z.pAt>60000){Z.pAt=Date.now();const pa=[];let pc=0;for(const[,pv]of Z.map){pa.push(pv);if(++pc>=400)break}localStorage.setItem("__JB_SESS",JSON.stringify(pa))}}catch(_){}let sg_=t.map(x=>x.sessionId).join("|"),now_=Date.now();if(!Z.snap||(sg_!==Z.sig&&now_-Z.ts>45000)){Z.snap=t;Z.sig=sg_;Z.ts=now_}return Z.snap',
    "main": b'let ae=QYn(X),he=[],Z=(globalThis.__JB_STB||(globalThis.__JB_STB={snap:null,sig:"",ts:0,map:new Map()})),L=new Set();for(let _e of ae.values()){if(_e&&ee(_e)){he.push(_e);L.add(_e.sessionId);Z.map.set(_e.sessionId,_e)}}if(!Z.ld){Z.ld=!0;try{const rw=localStorage.getItem("__JB_SESS");if(rw){const ar=JSON.parse(rw);for(const so of ar){so&&so.sessionId&&Z.map.set(so.sessionId,so)}}}catch(_){}}for(let[k_,v_]of Z.map){!L.has(k_)&&ee(v_)&&he.push(v_)}try{if(!Z.pAt||Date.now()-Z.pAt>60000){Z.pAt=Date.now();const pa=[];let pc=0;for(const[,pv]of Z.map){pa.push(pv);if(++pc>=400)break}localStorage.setItem("__JB_SESS",JSON.stringify(pa))}}catch(_){}let sg_=he.map(x=>x.sessionId).join("|"),now_=Date.now();if(!Z.snap||(sg_!==Z.sig&&now_-Z.ts>45000)){Z.snap=he;Z.sig=sg_;Z.ts=now_}return Z.snap',
}


def _sidebar_candidates(key: str) -> list[tuple[bytes, bytes]]:
    """(锚点, 新文本) 候选，按特异性从高到低。"""
    decl, arr, _keep, up, sw = _VARIANTS[key]
    suffix = "return " + arr
    new = _wrapper(key)
    cands = []
    for legacy in (LEGACY_V110.get(key), LEGACY_V100.get(key)):
        if legacy and legacy != new:
            cands.append((legacy, new))
    cands.append(((decl + sw + suffix).encode("utf-8"), new))   # 中间态：整库遍历
    cands.append(((decl + up + suffix).encode("utf-8"), new))   # 上游实现
    return cands


def _mk_targets(detect_of, cands_of) -> list[dict]:
    out = []
    for key, bundles in _SIDEBAR_BUNDLES.items():
        for bundle in bundles:
            out.append({"bundle": bundle, "detect": detect_of(key), "cands": cands_of(key)})
    return out


SIDEBAR_TARGETS = _mk_targets(lambda k: SIDEBAR_DETECT, _sidebar_candidates)

# ---------------------------------------------------------------- 补丁 2：噪音行

def _noise_new(key: str) -> bytes:
    v = b"e" if key == "chat" else b"ae"
    return b'&&(' + v + b'.title||' + v + b'.summary||' + v + b'._meta?.["cognition.ai/userMessageCount"]>0)'


def _noise_detect(key: str) -> bytes:
    """detect 必须精确到"追加的判定后缀"，否则应用自身代码里的同名字段会造成误判。"""
    return _noise_new(key)[1:]          # 去掉开头的 '&'


NOISE_OLD_CHAIN = {
    "chat": (b'&&e._meta?.["cognition.ai/isArchived"]!==!0&&(0,eo9.getProposedByDevinId)(e._meta)===void 0'
             b'&&e.title!=="Devin Local session"'),
    "main": (b'&&ae._meta?.["cognition.ai/isArchived"]!==!0&&(0,Yt.getProposedByDevinId)(ae._meta)===void 0'
             b'&&ae.title!=="Devin Local session"'),
}
NOISE_OLD_LABEL = {"chat": b'&&e.title!=="Devin Local session"',
                   "main": b'&&ae.title!=="Devin Local session"'}
NOISE_OLD_PRISTINE = {"chat": b'h(e.providerId)&&!(e.arenaId&&!0!==e.isArenaRep)',
                      "main": b'j(ae.providerId)&&!(ae.arenaId&&ae.isArenaRep!==!0)'}


def _noise_candidates(key: str) -> list[tuple[bytes, bytes]]:
    keep = NOISE_OLD_PRISTINE[key]
    return [
        (NOISE_OLD_CHAIN[key], _noise_new(key)),
        (NOISE_OLD_LABEL[key], _noise_new(key)),
        (keep, keep + _noise_new(key)),
    ]


NOISE_TARGETS = _mk_targets(_noise_detect, _noise_candidates)

# ---------------------------------------------------------------- 补丁 3：放开上限

LIMITS_DETECT = b"rzq(x,1e9"
LIMITS_TARGETS = [
    {"bundle": b,
     "detect": LIMITS_DETECT,
     "cands": [(b"rzq(x,p,m,{groupSessionLimits:I", b"rzq(x,1e9,m,{groupSessionLimits:I"),
               (b"J=S+R,H=", b"J=1e9,H=")]}
    for b in ("chat", "exa")
]

# ---------------------------------------------------------------- 残片修复

# 历史补丁在 isRenderable 处重复插入判定链，留下 "}&&…" 残片导致 bundle 语法错误（白屏）
_RESIDUE = re.compile(
    rb'(?:\&\&(?:[\w$]+\._meta\?\.\["cognition\.ai/isArchived"\]!==!0'
    rb'|\(0,[\w$]+\.getProposedByDevinId\)\([\w$]+\._meta\)===void 0'
    rb'|[\w$]+\.title!=="Devin Local session"))+'
)


def repair_residue(data: bytes) -> tuple[bool, bytes, str]:
    """把 "}<残片>," 收敛成 "},"；返回 (是否改动, 新内容, 说明)。"""
    i = data.find(b"[JB_DBG]")
    if i < 0:
        return False, data, "no-jb-dbg-marker"
    bound = data.find(b"}&&", i)
    if bound < 0:
        return False, data, "no-residue-boundary"
    m = _RESIDUE.match(data, bound + 1)
    if not m or data[bound + 1 + (m.end() - m.start()):bound + 2 + (m.end() - m.start())] != b",":
        return False, data, "residue-not-matched"
    removed = m.end() - m.start()
    return True, data[:bound + 1] + data[m.end():], f"removed {removed} bytes"


# 兼容旧引用
LEGACY_WRAPPERS = dict(LEGACY_V110)
LEGACY_WRAPPERS.update(LEGACY_V100)

PATCHES = [
    {"id": "sidebar", "title": "侧栏会话数据源：只用 store 现值（归档/删除立即生效）",
     "targets": SIDEBAR_TARGETS},
    {"id": "noise", "title": "隐藏空会话噪音行（无标题且无消息 → 不渲染）",
     "targets": NOISE_TARGETS},
    {"id": "limits", "title": "放开侧栏渲染上限（每组上限 / 总量上限）",
     "targets": LIMITS_TARGETS},
]
