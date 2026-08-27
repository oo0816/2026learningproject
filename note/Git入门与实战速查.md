# 06-Git 入门与实战速查

1
vscode左侧第三个 
commit上传 
回退箭头 回退discart

左下角报错按钮边上 选择master回到主线
哈希码 更准确 就是每次修改的目标代码
2
discard 放弃还没有提交的
reset 强制退回仓库到某个历史状态 单人
revert 生成反向commit
3
branch分支
main feature 多分支不影响 合并回主干 master
图表里 右键checkout回退查看代码 detached 最好不要编辑 分离头指针完成
4 worktreemain 
上正在跑测试/构建，突然要紧急修 bug → 开个新 worktree 检出新分支去修，互不干扰
不想打断当前手上没写完的代码，另开一个目录并行做另一个 feature
同一台机器同时处理多个任务
5 merge conflict
6 分区

┌─────────────┐   git add   ┌─────────────┐   
git commit   ┌─────────────┐
│  工作区      │ ──────────> │  暂存区      │ ─────────────> │  本地仓库    │ ── git push ──> GitHub
│ (你看到的文件)│             │ (Index/Staged)   │               │ (HEAD 指向)  │
└─────────────┘             └─────────────┘                └─────────────┘
                gitpull=fetch+merge

- **工作区**：磁盘上真实存在的文件
- **暂存区**：`git add` 后的"待提交清单" 检查点
- **本地仓库**：`git commit` 后永久保存的历史（.git 目录）
- **远程仓库**：GitHub 上的副本，`git push` 上传 / `git pull` 下载

> 💡 提交（commit）不是"保存文件"，而是**给整个仓库拍一张快照**，并写下一句说明。

---

## 2. 日常三连（90% 的时间只用到这个）

```bash
git status          # 先看：谁改了、谁暂存了
git add -A          # 把工作区所有改动加入暂存区（-A = 全部；也可 add 指定文件）
git commit -m "L2: 完成 memory 重构，测试通过"   # 拍快照 + 写说明
git push            # 推送到远程（首次推送用 git push -u origin main）
```

**提交信息规范**（面试官会看你的 commit 历史！）：

| 前缀 | 含义 | 例子 |
|---|---|---|
| `feat:` | 新功能 | `feat: 添加工具调用循环` |
| `fix:` | 修 bug | `fix: 修复 token 计数溢出` |
| `docs:` | 文档 | `docs: 更新 README 架构图` |
| `refactor:` | 重构不改行为 | `refactor: 拆分 memory.py` |
| `test:` | 测试 | `test: 补工具报错用例` |
| `chore:` | 杂项 | `chore: 升级依赖版本` |

✅ 好：`feat: RAG 支持多文档切分` 　❌ 差：`update`、`fix bug`、`111`

---

## 3. 查看状态

```bash
git status          # 当前改动一览（最常用）
git log --oneline   # 提交历史（一行一条）
git log --oneline --graph   # 带分支图的历史
git diff            # 工作区 vs 暂存区 的差异
git diff --staged   # 暂存区 vs 上次提交 的差异（add 之后看）
git show <commit>   # 看某次提交改了什么
```

---

## 4. 分支：并行世界

```bash
git branch                # 列出分支（* 表示当前所在）
git branch -m master main # 分支改名（我这次就把 master 改成了 main）
git switch -c feature-rag # 新建并切换到新分支
git switch main           # 切换分支
git merge feature-rag     # 把 feature 分支合并进当前分支
git branch -d feature-rag # 删除已合并的分支
```

**黄金法则**：main 永远保持可用（绿格子上跑的都能跑），新功能在分支上做，稳定后合并。

---

## 5. 后悔药大全（重点！）

| 场景 | 命令 | 效果 |
|---|---|---|
| 改错了，想放弃工作区改动 | `git restore <文件>` | 回到上次提交的样子 |
| add 多了，想撤出暂存区 | `git restore --staged <文件>` | 文件保留，只是不暂存 |
| 提交信息写错了 | `git commit --amend -m "新信息"` | 修改最近一次提交的说明 |
| 提交完发现漏了文件 | `git add 漏的文件 && git commit --amend` | 补进同一次提交 |
| 想撤销最近一次提交（保留改动） | `git reset --soft HEAD~1` | 提交撤销，改动回到暂存区 |
| 想撤销最近一次提交（不留改动） | `git reset --hard HEAD~1` | ⚠️ 改动直接丢弃 |
| 临时放下手上的活 | `git stash` / `git stash pop` | 存起来 / 取回来 |
| 提交已推送，想撤销 | `git revert <commit>` | 生成一个"反向提交"（安全，推荐） |
| 本地和远程分叉 | `git pull --rebase` | 把我的提交"垫"到远程最新之上 |

> ⚠️ 红线：**`reset --hard` 会丢东西**，动之前先 `git stash` 或备份。
> ⚠️ 红线：**已推送的提交不要 reset**，要用 revert，否则别人拉取会乱。

---

## 6. 远程仓库

```bash
git remote -v                        # 查看远程
git remote add origin <URL>          # 关联远程（origin 是默认名字）
git remote remove origin             # 断开远程（防止误推！）
git clone <URL>                      # 克隆到本地（自带 remote）
git push -u origin main              # 首次推送并记住 upstream
git push                             # 之后直接 push
git pull                             # 拉取远程更新（= fetch + merge）
```

**⚠️ 我的实战教训**：
- `agent-learning` 曾把 remote 指到计划仓库 `2026learningproject`，差点把 L0-L6 内容推上去覆盖计划文档 → **一个仓库只对一个 remote，推之前 `git remote -v` 确认目标**
- `git push --force` 会**覆盖**远程历史（我用它把推错的 agent-learning 内容从计划仓库清掉）→ 只在确定远程内容没价值时用，平时禁用

---

## 7. GitHub 协作：Fork + Pull Request

```
别人仓库 → Fork（复制到我的账号）→ git clone 到本地
→ 新建分支改代码 → push 到我的 Fork → GitHub 上发起 Pull Request
→ 原作者 review 后 Merge
```

- PR 是开源贡献的标准姿势，面试官看 GitHub 主页时很加分
- 面试前可以把给开源项目提过 PR 写进简历（哪怕只是修文档）

---

## 8. WSL + Windows 实战细节（踩坑记录）

### 8.1 凭据：push 不用每次输密码
```bash
gh auth login        # GitHub CLI 登录（device flow：浏览器输一次性码）
gh auth setup-git    # 配置 git 使用 gh 的凭据
```
之后 `git push` 自动带 token，不再问密码。

### 8.2 网络：GitHub 连不上的排查顺序
```bash
curl -4 -o /dev/null -w "%{http_code}" https://github.com   # 先测连通性（-4 强制 IPv4）
getent hosts github.com    # 看解析到哪（WSL 里可能是 127.0.0.1 ← hosts 污染）
```
- 我的环境：Windows hosts 被加速器劫持 → WSL 把 github.com 解析到 127.0.0.1
- 修复：把真实 IP 写进 WSL `/etc/hosts`，并关掉 WSL 的 hosts 自动覆盖（`/etc/wsl.conf` 里 `generateHosts=false`）
- 国内直连 GitHub 慢是常态，push 超时就重试 / 换稳定 IP

### 8.3 换行符：CRLF vs LF
```bash
git config --global core.autocrlf input   # Windows 下推荐，避免"整个文件都算改动"
```

### 8.4 文件权限（WSL 下常见）
```bash
git config --global core.fileMode false   # 忽略权限位变化，防止"莫名其妙的改动"
```

---

## 9. .gitignore：别把垃圾传上去

```gitignore
# Python
__pycache__/
*.pyc
.venv/
venv/

# 编辑器 / 系统
.vscode/
.idea/
.DS_Store

# 敏感信息（永远不要提交！）
*.env
*.key
config.local.json
```

- ⚠️ 我的教训：`l1-mini-agent/__pycache__/*.pyc` 被误跟踪推上了 GitHub——编译产物不该入库
- **已跟踪的文件**加 .gitignore 不会生效，要先 `git rm -r --cached <路径>` 取消跟踪

**敏感信息红线**：API Key、密码、token **永远不要提交**。已经推上去了 → 立即去对应平台**吊销**那个 key（不是删文件就完事，历史里还能翻到），再删。

---

## 10. 我的工作流（日常学习日）

```bash
# 每天结束时（10 分钟）：
cd <仓库>
git status                    # 1. 看今天改了什么
git add -A                    # 2. 全加
git commit -m "feat: ..."     # 3. 写清干了啥
git push                      # 4. 上云（绿格子 + 防丢）
```

好习惯清单：
- [ ] 每天至少 1 次 commit，**小步提交**（一次提交只干一件事）
- [ ] 提交信息用前缀规范，写清"为什么"
- [ ] 不提交 `.pyc` / 环境文件 / 密钥
- [ ] push 前 `git remote -v` 确认目标仓库
- [ ] 每周日把进度更新到 progress.json 并 push（面试时绿格子和提交历史就是证据）

---

## 11. 常见报错速查

| 报错 | 原因 | 解决 |
|---|---|---|
| `fatal: not a git repository` | 不在仓库里 | `cd` 到仓库根目录 |
| `Please tell me who you are` | 没配用户名邮箱 | `git config --global user.name/user.email` |
| `rejected: non-fast-forward` | 远程有新提交，本地落后 | `git pull --rebase` 再 push |
| `failed to push some refs` | 同上 | 同上 |
| `Permission denied (publickey)` | SSH 密钥没配 | 改用 HTTPS + gh 凭据 |
| `connection timed out` | 网络问题 | 见 8.2 排查 |
| `OpenSSL SSL_read: Connection reset` | 网络被重置 | 重试 / 换稳定 IP |
| `The file will have its original line endings` | CRLF 警告 | 配置 `core.autocrlf input` |
| `warning: LF will be replaced by CRLF` | 同上 | 同上 |
| 误推了不该推的东西 | 手滑 | 吊销密钥 + `git rm --cached` + 重写历史（必要时） |

---

## 12. 命令速查总表

```bash
# 配置
git config --global user.name "oo0816"
git config --global user.email "xxx@qq.com"
git config --global core.autocrlf input

# 日常
git status / add / commit -m / push / pull / log --oneline

# 分支
git branch / switch -c / merge / branch -d

# 撤销
git restore / restore --staged / reset --soft HEAD~1 / revert / stash

# 远程
git remote -v / remote add origin <URL> / clone <URL>

# 其他
git diff / git show / git rm --cached <文件> / git tag
```

---

## 13. 面试官可能问的 Git 问题（提前想好答案）

1. `merge` 和 `rebase` 的区别？
2. 怎么撤销一个已推送的提交？（`git revert`）
3. 冲突（conflict）怎么解决？
4. 你的 GitHub 主页上绿格子为什么这么密？（因为每天提交 😄）
