"""补丁定义（字节级）。

三条独立补丁，各自幂等：
  sidebar  —— 侧栏会话数据源换成"应用已知全量 + 粘性快照"，开局即全量、不闪不倒退
  noise    —— 无标题且无消息的空会话（会渲染成 "Devin Local session"）不显示
  limits   —— 放开侧栏组件的"每组上限"和"总量上限"（默认只渲染 25 条的那道闸门）
另外提供 repair_residue()：修复历史补丁留下的语法残片（白屏根因）。
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------- 变体定义

_VARIANTS = {
    # key: (声明前缀, 累加数组, 判定函数, 上游遍历, 已打 P1 的遍历)
    #      遍历模板里 {n} 是循环变量、{r} 是元素名
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


def _wrapper(key: str) -> bytes:
    decl, arr, keep, _up, _sw = _VARIANTS[key]
    item = "r" if key == "chat" else "_e"
    loop = ("for(let %s of %s.values()){if(%s&&%s(%s)){%s.push(%s);L.add(%s.sessionId);Z.map.set(%s.sessionId,%s)}}"
            % (item, "e" if key == "chat" else "ae", item, keep, item, arr, item, item, item, item))
    body = (
        ',Z=(globalThis.__JB_STB||(globalThis.__JB_STB={snap:null,sig:"",ts:0,map:new Map()})),L=new Set();'
        + loop
        + 'if(!Z.ld){Z.ld=!0;try{const rw=localStorage.getItem("__JB_SESS");if(rw){const ar=JSON.parse(rw);'
          'for(const so of ar){so&&so.sessionId&&Z.map.set(so.sessionId,so)}}}catch(_){}}'
        + 'for(let[k_,v_]of Z.map){!L.has(k_)&&' + keep + '(v_)&&' + arr + '.push(v_)}'
        + 'try{if(!Z.pAt||Date.now()-Z.pAt>60000){Z.pAt=Date.now();const pa=[];let pc=0;'
          'for(const[,pv]of Z.map){pa.push(pv);if(++pc>=400)break}localStorage.setItem("__JB_SESS",JSON.stringify(pa))}}catch(_){}'
        + 'let sg_=' + arr + '.map(x=>x.sessionId).join("|"),now_=Date.now();'
        + 'if(!Z.snap||(sg_!==Z.sig&&now_-Z.ts>45000)){Z.snap=' + arr + ';Z.sig=sg_;Z.ts=now_}return Z.snap'
    )
    # decl 以分号结尾，拼接时必须去掉，否则会写成 "t=[];,Z=..." 这种语法错误
    return (decl.rstrip(";") + body).encode("utf-8")


def _sidebar_candidates(key: str) -> list[tuple[bytes, bytes]]:
    decl, arr, _keep, up, sw = _VARIANTS[key]
    suffix = "return " + arr
    new = _wrapper(key)
    return [
        ((decl + up + suffix).encode("utf-8"), new),
        ((decl + sw + suffix).encode("utf-8"), new),
    ]


# ---------------------------------------------------------------- 补丁 1：侧栏数据源

SIDEBAR_DETECT = b"__JB_STB"


def _mk_targets(detect_of, cands_of) -> list[dict]:
    out = []
    for key, bundles in _SIDEBAR_BUNDLES.items():
        for bundle in bundles:
            out.append({"bundle": bundle, "detect": detect_of(key), "cands": cands_of(key)})
    return out


SIDEBAR_TARGETS = _mk_targets(lambda k: SIDEBAR_DETECT, _sidebar_candidates)

# ---------------------------------------------------------------- 补丁 2：噪音行

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


def _noise_new(key: str) -> bytes:
    v = b"e" if key == "chat" else b"ae"
    return b'&&(' + v + b'.title||' + v + b'.summary||' + v + b'._meta?.["cognition.ai/userMessageCount"]>0)'


def _noise_candidates(key: str) -> list[tuple[bytes, bytes]]:
    keep = b"h(e.providerId)&&!(e.arenaId&&!0!==e.isArenaRep)" if key == "chat" \
        else b"j(ae.providerId)&&!(ae.arenaId&&ae.isArenaRep!==!0)"
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


PATCHES = [
    {"id": "sidebar", "title": "侧栏会话数据源：全量 + 粘性快照（开局即全量、不闪不倒退）",
     "targets": SIDEBAR_TARGETS},
    {"id": "noise", "title": "隐藏空会话噪音行（无标题且无消息 → 不渲染）",
     "targets": NOISE_TARGETS},
    {"id": "limits", "title": "放开侧栏渲染上限（每组上限 / 总量上限）",
     "targets": LIMITS_TARGETS},
]
