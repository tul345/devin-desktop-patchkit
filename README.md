# devin-desktop-patchkit

给 **Devin Desktop**（Windsurf 内核的 Electron 应用）打本地补丁的小工具包。用来修四类实际踩过的问题，全部可校验、可回滚。

## 修什么

| 症状 | 根因 | 补丁 |
| --- | --- | --- |
| 打开就是白屏 | 历史补丁在 `isRenderable` 处重复插入判定链，留下 `}&&…` 语法残片，整个 UI bundle 解析失败 | `repair` |
| 侧栏出现很多 "Devin Local session" 行 | 该文案是**界面兜底**，数据里 `title` 其实是 `undefined`；补丁却拿它做字符串比较，过滤条件永不成立 | `noise` |
| 会话数量一直变、慢慢才补齐 | 补丁把数据源换成"整库遍历"，而库会随同步进/出；侧栏组件又有"每组上限 + 总量上限（默认 25）" | `sidebar` + `limits` |
| 归档/删除点了没反应 | v1.0.0 的 `sidebar` 用了跨帧粘性缓存，会把已归档/已删除的旧会话对象重新加回列表并持久化 | `sidebar`（v1.1.0 移除缓存） |
| 侧栏空白、加载圈停转 | v1.1.0 的 45 秒节流把首帧空列表存成快照并一直返回，`useMemo` 依赖不变也就不再重算 | `sidebar`（v1.2.0 移除节流） |
| python 语言服务告警 `Enumeration of workspace source files is taking longer than 10 seconds` | 工作区里存在十几万文件的工具库目录，未被 `pyrightconfig.json` 排除 | `pyright` |
| 侧栏先显示几十条、几分钟后才补全 | ACP shim 冷启动读库失败时把**未展开的短列表**交给了 IDE | `shim` |

## 快速开始

```powershell
cd D:\AI\projects\devin-desktop-patchkit

python devin-patchkit.py doctor                 # 环境自检（路径 / node / gh）
python devin-patchkit.py status                 # bundle 语法 + 校验值 + 补丁是否已打
python devin-patchkit.py apply --dry-run        # 先看要改什么
python devin-patchkit.py apply                  # 打补丁（自动备份 + 语法校验 + 失败回滚）
python devin-patchkit.py verify                 # 复核
python devin-patchkit.py rollback               # 从最近一次备份回滚
```

单独使用：

```powershell
python devin-patchkit.py repair --dry-run                      # 只修白屏残片
python devin-patchkit.py pyright --workspace "D:\path\to\workspace" --extra 工具库/源码 工具库/external
python devin-patchkit.py shim                                  # 给 ACP shim 打预热 + 重试
```

改完 JS bundle 后**必须重启 Devin** 才生效。

## 补丁清单

- `sidebar`：侧栏会话数据源改为"只用 store 现值"。效果：开局即全量；每帧从 store 重建（**不缓存、不节流**），所以归档/删除立即生效，也不会出现"空白卡住"。
- `noise`：无标题且无消息的空会话不渲染（判定 `title || summary || userMessageCount > 0`）。
- `limits`：放开侧栏组件的"每组上限 `p`"与"总量上限 `J=S+R`"。
- `repair`：清除语法残片（白屏），修复前先做一次语法校验，不通过就拒绝写入。
- `pyright`：向工作区 `pyrightconfig.json` 注入 `exclude`（含 `.git`、`node_modules`、`site-packages` 等，可 `--extra` 追加）。
- `shim`：给 `acp_expand_shim.py` 加"进程启动即读库"的预热线程，以及"首次读库失败必须重试"的循环——避免把短列表交给 IDE。

细节见 [`docs/PATCHES.md`](docs/PATCHES.md) 与 [`docs/ANALYSIS.md`](docs/ANALYSIS.md)。

## 安全设计

- **幂等**：每条补丁有 `detect` 特征串，命中即跳过，重复执行无副作用。
- **原子写**：写临时文件 → 校验 → `os.replace`，不会留下截断文件（这个坑真踩过：一次脚本把 8KB 的 shim 写成了 0 字节）。
- **先备份后改**：每次改动写 `Backups/patchkit-<动作>-<时间戳>/`，含 `manifest.json`，`rollback` 按 manifest 精确还原。
- **语法门禁**：改完用 `node --check` 以 ESM 方式解析整个 bundle（40MB+ 也就几秒），不通过立刻回滚。
- **校验值同步**：改动 `product.json` 里登记的 bundle 后，同步写入 sha256（base64 去 padding），否则应用会报安装损坏。
- 不联网、不上传、不读取任何凭据。

## 环境变量

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `DEVIN_APPDIR` | `D:\Windsurf` | 应用安装目录（含 `resources\app`） |
| `DEVIN_USERDATA` | `D:\Roaming\devin` | 用户数据目录（含 `Backups`、`acp_expand_shim.py`） |

## 风险与边界

- 改的是应用自身 bundle：**Devin/Windsurf 自动更新会覆盖它们**，更新后重跑 `apply` 即可（`status` 会告诉你哪些没打）。
  只有 `pyright` 写在工作区文件里，不受应用更新影响。
- 侧栏数据源补丁会显示应用 store 里的**全部**会话（可能多于磁盘库 `hidden=0` 的条数），这是有意为之；不想要就 `rollback`。
- 本项目只针对 Windows + Devin Desktop（Windsurf 内核）；函数名/锚点随版本变化，锚点找不到时工具会**跳过并报告**，不会瞎改。

## 已知未处理

- `Environment discovery is taking longer than expected`：ms-python 扩展找解释器的告警，与 pyright 枚举无关。
- `CodeWindow: failed to load (reason: ERR_BLOCKED_BY_RESPONSE)`：Devin Cloud 内嵌页（app.devin.ai）加载被拦，出现早于本项目改动。

## 目录结构

```
devin-patchkit.py          入口
patchkit/
  config.py                路径配置（支持环境变量覆盖）
  patcher.py               引擎：备份/原子写/语法校验/校验值同步/回滚
  patches.py               三条补丁的字节级定义 + 残片修复
  cli.py                   子命令
docs/
  ANALYSIS.md              机制分析（含变量与函数名）
  PATCHES.md               每条补丁的锚点与验证
  CHANGELOG.md             处理时间线
```

## License

未附带许可证文件；如需开源发布，自行添加（例如 MIT）。

## 发布到 GitHub

```powershell
winget install --id GitHub.cli -e     # 装 gh（一次性）
gh auth login                         # 交互登录（一次性）
.\scripts\publish.ps1                 # 建仓并推送
.\scripts\publish.ps1 -Private        # 私有仓库
```

若不想装 gh：在 GitHub 网页新建空仓库，然后

```powershell
git remote add origin https://github.com/<你的账号>/devin-desktop-patchkit.git
git push -u origin master
```

（HTTPS 首次推送会弹出 Git Credential Manager 登录；SSH 需要先把公钥加到 GitHub。）
