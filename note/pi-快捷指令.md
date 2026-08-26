# 🚀 Pi 快捷指令速查表

---

## 📖 目录

1. [斜杠命令](#-斜杠命令)
2. [常用快捷键](#-常用快捷键)
3. [编辑框小技巧](#-编辑框小技巧)
4. [消息队列](#-消息队列)
5. [命令行启动](#-命令行启动)
6. [会话管理](#-会话管理)
7. [与 Claude Code 对比](#-与-claude-code-对比)
8. [省钱指南](#-省钱指南)
9. [自定义配置](#-自定义配置)
10. [我的笔记](#-我的笔记)

---

## 🎯 斜杠命令

| 命令 | 作用 | 使用频率 |
|------|------|:---:|
| `/model` | 切换模型（也可按 **Ctrl+L**） | ⭐⭐⭐ |
| `/settings` | 设置：思考级别、主题等 | ⭐⭐⭐ |
| `/compact` | 手动压缩对话，省 token | ⭐⭐⭐ |
| `/tree` | 会话树导航，跳到任意节点 | ⭐⭐ |
| `/resume` | 恢复之前的会话 | ⭐⭐ |
| `/new` | 开启新会话 | ⭐⭐ |
| `/fork` | 从之前某条消息分叉出新会话 | ⭐ |
| `/clone` | 复制当前分支为新会话 | ⭐ |
| `/copy` | 复制最后一条助手回复 | ⭐⭐ |
| `/export` | 导出会话（HTML / JSONL） | ⭐ |
| `/share` | 上传为 GitHub gist 分享链接 | ⭐ |
| `/session` | 查看会话文件、token、花费 | ⭐ |
| `/name <名字>` | 给会话起名 | ⭐ |
| `/reload` | 重载配置（改完配置用它生效） | ⭐⭐ |
| `/hotkeys` | 显示所有快捷键 | ⭐ |
| `/login` `/logout` | 管理 API key 凭据 | ⭐ |
| `/quit` | 退出 pi | ⭐⭐⭐ |

---

## ⌨️ 常用快捷键

### 模型与思考

| 快捷键 | 作用 |
|--------|------|
| **Ctrl+L** | 打开模型选择器 |
| **Shift+Tab** | 循环切换思考级别（省思用 low） |
| **Ctrl+T** | 展开 / 折叠思考块 |

### 消息与显示

| 快捷键 | 作用 |
|--------|------|
| **Ctrl+X** | 复制最后一条助手消息 |
| **Ctrl+O** | 折叠 / 展开工具输出 |
| **Ctrl+G** | 打开外部编辑器 |
| **Esc** | 中断当前操作 |

### 编辑操作

| 快捷键 | 作用 |
|--------|------|
| **Shift+Enter** | 多行输入 |
| **Ctrl+Z** | 撤销（WSL 里是 **Alt+Z**） |
| **Ctrl+Y** | 粘贴最近删除的内容 |

### 应用控制

| 快捷键 | 作用 |
|--------|------|
| **Esc** | 取消 / 中止 |
| **Ctrl+D** | 退出（编辑框为空时） |
| **Ctrl+C** | 第一次清空编辑框，第二次退出 |

---

## 📎 编辑框小技巧

| 输入 | 作用 |
|------|------|
| `@` | 模糊搜索引用项目文件 |
| `!命令` | 运行 shell 命令并把输出发给模型 |
| `!!命令` | 运行命令但结果不发给模型 看不到
| **Ctrl+V** | 粘贴图片（Windows 上是 **Alt+V**） |
| **Tab** | 路径补全 |
| **Ctrl+P** | 浏览输入历史 |

---

## 📨 消息队列（agent 干活时）

| 按键 | 作用 |
|------|------|
| **Enter** | 排队转向消息（当前工具跑完就处理） |
| **Alt+Enter** | 排队后续消息（全部干完再处理） |
| **Alt+Up** | 把排队的消息撤回编辑框 |
| **Esc** | 中止并恢复消息到编辑框 |


---

## 💻 命令行启动

```bash
pi                          # 启动（默认 DeepSeek flash）
pi -c                       # 继续最近会话
pi -r                       # 浏览选择历史会话
pi --model deepseek-v4-pro  # 指定模型
pi -p "帮我写个脚本"         # 非交互模式
pi --name "我的任务"         # 启动时设置会话名
pi --no-session             # 临时模式，不保存会话
```

---

## 📂 会话管理 tree系统

| 操作 | 方法 |
|------|------|
| 查看当前会话 | `/session` |
| 继续最近会话 | `pi -c` |
| 浏览历史会话 | `pi -r` 或 `/resume` |
| 回到对话的某个节点 | `/tree` |
| 从旧消息分叉新会话 | `/fork` | 携带分叉点之前的
| 复制当前分支 | `/clone` |
| 压缩长对话 | `/compact` |

会话自动保存在 `~/.pi/agent/sessions/`，按工作目录分类。

---

## 🔀 与 Claude Code 对比

> 两者都是终端 AI 编程助手，概念高度相似，但**具体按键和命令名不一样**。

### 概念重合的（学了通用）

- **压缩对话**：pi `/compact` ↔ CC `/compact`
- **切换模型**：pi `/model`、Ctrl+L ↔ CC `/model`
- **恢复会话**：pi `/resume`、`pi -r` ↔ CC `/resume`、Ctrl+R
- **中断操作**：两者都是 **Esc**
- **多行输入**：两者都是 Shift+Enter
- **粘贴图片**：两者都是 Ctrl+V
- **查看花费**：pi `/session` ↔ CC `/cost`、`/usage`
- **登录管理**：两者都是 `/login`

### 不一样的地方（⚠️ 容易按错）

- **新会话**：pi `/new` ↔ CC `/clear`、Ctrl+N
- **撤销**：pi Ctrl+Z / Alt+Z ↔ CC Ctrl+Y
- **清屏**：pi 无 ↔ CC Ctrl+L
- **输入历史**：pi Ctrl+P ⚠️切模型 ↔ CC Ctrl+P ⚠️光标前移
- **会话回溯**：pi `/tree`、`/fork` ↔ CC `/rewind`

> ⚠️ **最坑的是 Ctrl+P**：在 pi 里按它是"切换下一个模型"，在 Claude Code 里是"光标前移"——同一个按键，两个软件含义完全不同，切换使用时最容易按错！

---

## 💰 省钱指南（DeepSeek 版）

- **用 flash 模型**：`deepseek-v4-flash` 比 pro 便宜 3 倍（已设为默认）
- **调低思考级别**：`/settings` 里把 `defaultThinkingLevel` 设为 `low` 或 `off`
- **勤用 `/compact`**：长对话会重复计费，压缩后每次请求更便宜
- **多复用 prompt 缓存**：同一会话反复提及的内容走缓存价（$0.0028/M）
- **上下文别塞太大**：只 @ 需要的文件，别让模型读整个项目

---

## 🔧 自定义配置

### 修改快捷键

创建 / 编辑 `~/.pi/agent/keybindings.json`：

```json
{
  "app.model.cycleForward": "ctrl+p",
  "app.thinking.cycle": "shift+tab",
  "tui.input.newLine": "shift+enter"
}
```

改完在 pi 里执行 `/reload` 生效，不用重启。

### 默认模型（已配置）

`~/.pi/agent/settings.json`：

```json
{
  "lastChangelogVersion": "0.84.3",
  "theme": "dark",
  "defaultProvider": "deepseek",
  "defaultModel": "deepseek-v4-flash"
}
```

### 压缩参数

```json
{
  "compaction": {
    "enabled": true,
    "reserveTokens": 16384,
    "keepRecentTokens": 20000
  }
}
```

---

## 📝 我的笔记

> 下面是我的私人笔记区

### 💡 常用技巧

> 💡
 1.插件在pi官网里找 如果只想部分使用那在npm后加一个-l
如果想卸载就变成unstall
2.pi install npm:pi-mcp-adapter
mcp要取得具体的key 可以调用不同的功能去做事情 插接口
3.btw bytheway 同时并行 不打断ai的工作
/btw control c 退出子对话
3.planmode 先做计划再执行
/planmode 在输入一次关闭模式 会写入plan.md文件里
4.goal 固定目标执行工作 迭代
/goal
5.动态工作流 分出好几个子代理做事情
/dynamic workflow
6.连微信wechat 做chatbot 目前感觉没意义 必须电脑开机 可能远程操控有用


- [ ] 待补充...

### ⚠️ 踩坑记录

> ⚠️
1.在13077下的agent-skill才是全局 项目文件下的skill仅在项目里有用


### 📌 待整理

1.npx @agegr/pi-web@latest  可以用图形界面
2.agents.md文件是全局记忆 ai率先读取



