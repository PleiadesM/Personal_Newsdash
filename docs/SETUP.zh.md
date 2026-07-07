# 配置指南——从零到你自己的新闻台

[English](SETUP.md)

这是一份点到哪、写到哪的手把手教程。核心路径完全不需要终端——一切都在 GitHub 网页里完成。任何一步卡住，直接跳到底部的[疑难排查表](#11-疑难排查)。

**选择你的节奏：**

- **快车道（10 分钟，零密钥）** → 做第 1–4 步。你会得到一个自动更新的新闻 + 论文仪表盘。
- **完整配置（再加约 15 分钟）** → 继续第 5–8 步：私密模式、你的日历、Canvas 课程。
- **躺平车道** → 做完第 1–3 步，然后让 AI 替你完成 4–8 步（[第 9 步](#9-让-ai-替你配置)）。

---

## 0. 你需要什么

- 一个 **GitHub 账号**（免费版即可）。
- 第一遍大约 **10 分钟**。
- **不需要任何 API Key。** 默认新闻包与学术包全程免密钥。只有当你想接入私密栏目时，密钥和日历地址才会登场。

---

## 1. 创建你的副本

1. 在本仓库页面点绿色的 **Use this template** 按钮 → **Create a new repository**。
2. 随便起名（比如 `newsdash`）。
3. **保持 Public（公开）。** 这一点重要，原因如下：
   - GitHub Pages **只对公开仓库免费**——私有仓库的 Pages 需要付费套餐。
   - 公开仓库的 Actions 分钟数**不限量**；私有仓库每月只有 2000 分钟。
   - 担心隐私？你的隐私**不**来自仓库可见性，而来自**加密**（[第 5 步](#5-私密模式与口令)）。私密栏目在提交之前就已加密，公开仓库不会暴露你的日程或课程。
4. 点 **Create repository**。

## 2. 第一次构建

1. 打开新仓库的 **Actions** 标签页。如果看到「工作流已禁用」的提示条，点 **"I understand my workflows, go ahead and enable them"**。
2. 左侧列表点 **Update Newsdash**。
3. 点 **Run workflow** → **Run workflow**（绿色按钮，保持 `main` 分支）。
4. 等运行变**绿**（通常 1–3 分钟）。这次构建会抓取默认新闻包并把结果提交进 `data/` 目录。

此后构建每 2 小时自动运行——不再需要任何点击。

## 3. 启用 Pages

1. 进入 **Settings → Pages**。
2. 在 **Build and deployment** 下把 **Source** 设为 **Deploy from a branch**。
3. 选分支 **`main`**、目录 **`/ (root)`**，点 **Save**。
4. 你的站点地址是：

   ```
   https://<你的用户名>.github.io/<你的仓库名>/
   ```

首次部署需要 **1–5 分钟**。之后每次数据更新可能比构建晚 **约 10 分钟**——那是 GitHub Pages 的 CDN 缓存，不是故障；页面下次加载时会自动破缓存。

> 如果页面显示 **「等待首次构建」**，说明流水线还没产出数据——回到第 2 步确认 "Update Newsdash" 跑绿了。

## 4. 用配置 Issue 个性化

你不需要手改任何 JSON。仓库自带一张 Issue 表单，机器人读取并自动应用。

1. 打开 **Issues → New issue**，选 **「Set up my Newsdash · 配置我的新闻台」**。
2. 填表：

   | 字段 | 改变什么 |
   |---|---|
   | **Interface language 界面语言** | 默认界面语言（中或英）。读者在页面上仍可随时切换。 |
   | **Site visibility 站点可见性** | **Public 公开** = 新闻/论文任何人可读，私人栏目仍加密。**Private 私密** = *全站*加密，打开即口令门——需要 `NEWSDASH_PASSPHRASE`（[第 5 步](#5-私密模式与口令)）。 |
   | **Theme 主题** | `the-type`（字砌）、`nyt`（报纸）、`bear`（小熊极简、自动深色）。 |
   | **Site title 站点标题** | 报头文字（可选）。 |
   | **Timezone 时区** | IANA 名称，如 `Asia/Shanghai`、`America/Chicago`——用于日程显示与日界（可选）。 |
   | **Open news packs 公开新闻包** | 勾选 **AI news** 和/或 **General news**。全不勾则保留两个默认包。 |
   | **Academic packs 学术论文包** | 勾选**数据可视化**和/或**技术传播**——免密钥学术信源（[第 8 步](#8-学术论文包)）。 |
   | **Extra RSS feeds 自定义 RSS** | 每行一个订阅地址，都会进入你的新闻栏目。 |
   | **Interest keywords 兴趣关键词** | 逗号分隔；命中关键词的内容排序更靠前。 |
   | **Acknowledgement 确认** | 必勾：密钥绝不写进 Issue。 |

3. **提交。** 机器人随后：
   - 更新 `config/site.json` 与 `config/sources.json` 并提交，
   - 触发重建，
   - **回帖**告诉你后续步骤（你的 Pages 地址、带直达链接的 Secrets 清单、AI 启动提示词），
   - 全部应用成功后**自动关闭该 Issue**。
4. 填错了或改主意了？**直接编辑 Issue 正文**——每次编辑机器人都会重跑，已关闭的也一样。

> ⚠️ **绝不要把密钥粘进 Issue**——口令、日历地址、Canvas Token 都不行。机器人会主动扫描疑似凭据的字符串，发现即拒绝应用。密钥只去 **Settings → Secrets and variables → Actions**（下一步）。另外：只有**仓库所有者**开的 Issue 会被应用——别人在你仓库开的配置 Issue 会被直接忽略。

## 5. 私密模式与口令

一个 Secret 就能打开一切私人内容的加密：

1. 进入 **Settings → Secrets and variables → Actions → New repository secret**。
2. 名称：`NEWSDASH_PASSPHRASE`
3. 值：**至少 4 个随机单词**，例如 `maple lantern crater bicycle`。加密文件是公开可下载的，弱口令可能被离线爆破——长度胜过小聪明。
4. 点 **Add secret**，然后到 Actions 重跑一次 **Update Newsdash** 让新口令生效。

要点：

- **口令就是你的登录。** 打开站点后，在浏览器里输入这个口令即可解锁加密栏目。没有单独的账号体系。
- `visibility: public` 时新闻/论文对所有人可读，日程与课程永远加密；`visibility: private` 时*所有*栏目加密，页面直接进入口令门。
- **更换口令**：改 Secret 的值并重跑工作流——下次构建会用新口令重新加密。但 git 有记忆：**旧密文仍留在仓库历史里**，只受*旧*口令保护。若旧口令可能已泄露，请把历史视为暴露（或压缩历史——见维护文档）。

完整加密设计（AES-256-GCM、PBKDF2、信封格式）见 [DATA_CONTRACT.md](DATA_CONTRACT.md)。

## 6. 个人日程（ICS 日历）

日程栏目读取标准 ICS 日历源。你收集各日历的 URL，装进一个小 JSON 文件，base64 编码后存为一个 Secret。页面上任何内容都要等你输入口令后才会解密。

### 6a. 获取日历地址

**Google 日历**

1. 桌面端打开 [Google 日历](https://calendar.google.com) → 齿轮 → **设置**。
2. 左栏 **我的日历的设置** 下点你的日历。
3. 滚动到 **整合日历** → 复制 **「iCal 格式的私密地址」**。
4. 🔴 **把这个 URL 当密码对待。** 拿到它的人能读你的全部日程——这正是它只进 Secret、绝不进仓库或 Issue 的原因。

**Outlook / Office 365**

1. 网页版 Outlook → **设置 → 日历 → 共享日历**。
2. 在 **发布日历** 下选择日历与权限级别，点 **发布**。
3. 复制 **ICS** 链接。

**Canvas 日历**（把截止日期当日历事件）

1. 在 Canvas 里打开左侧全局导航的 **Calendar**。
2. 日历侧栏右下角点 **Calendar feed**。
3. 复制 ICS 地址。

### 6b. 组装 JSON 文件

把 [`examples/ics-sources.example.json`](../examples/ics-sources.example.json) 复制到**仓库之外**的地方（比如桌面），命名为 `ics-sources.json`，填入你的日历：

```json
[
  { "id": "gcal_personal", "name": "个人", "url": "https://calendar.google.com/calendar/ical/…/private-…/basic.ics" },
  { "id": "canvas", "name": "Canvas 截止日", "url": "https://canvas.example.edu/feeds/calendars/user_….ics" }
]
```

> 🔴 **绝不要提交这个文件。** 它包含私密 URL；它只应在你的电脑上存活到编码完成那一刻。

### 6c. 编码并添加 Secret

在文件所在目录打开终端：

- **macOS**：
  ```bash
  base64 -i ics-sources.json | tr -d "\n"
  ```
- **Linux**：
  ```bash
  base64 -w0 ics-sources.json
  ```
- **Windows（PowerShell）**：
  ```powershell
  [Convert]::ToBase64String([IO.File]::ReadAllBytes("ics-sources.json"))
  ```

复制输出的一整行，新建仓库 Secret，名称 **`ICS_SOURCES_B64`**（Settings → Secrets and variables → Actions → New repository secret）。

最后：日程是**私密栏目，因此还需要 `NEWSDASH_PASSPHRASE`**（[第 5 步](#5-私密模式与口令)）——没有它构建就没有加密密钥，栏目会显示未配置。重跑 **Update Newsdash**，你的日程就会出现在解锁之后。

## 7. Canvas 课程

除了日历事件，新闻台还能显示 Canvas 的**公告和待交作业**（含是否已提交）。这用到 Canvas REST API：

1. 在 Canvas：**Account → Settings** → 滚动到 **Approved Integrations** → 点 **+ New Access Token**。用途写 "newsdash" 之类，生成。
2. 立刻复制 Token（Canvas 只显示这一次）。
3. 添加两个仓库 Secret：
   - `CANVAS_BASE_URL` —— 你学校的 Canvas 根地址，如 `https://canvas.iastate.edu`
   - `CANVAS_TOKEN` —— 刚生成的 Token

> ⚠️ **Canvas Token 拥有你账户的全部权限**——成绩、私信、一切，而不只是新闻台读取的部分。每学期轮换一次（在 Canvas 删除旧 Token、生成新的、更新 Secret）。有些学校会强制 Token 过期；如果课程栏目突然报错，先查 Token 是否过期。

和日程一样，课程是私密栏目：需要 `NEWSDASH_PASSPHRASE`。

## 8. 学术论文包

在配置 Issue（[第 4 步](#4-用配置-issue-个性化)）里勾选**数据可视化**和/或**技术传播**即可——不用改任何代码。它们走免密钥学术 API，可靠性各有差异：

| 信源 | 免密钥可靠性 |
|---|---|
| **arXiv** | ✅ 可靠 |
| **CrossRef** | ✅ 可靠 |
| **OpenAlex** | ⚠️ 无 Key 尽力而为——2026 年 OpenAlex 改为积分制后，免密钥请求经常被拒。添加 **`OPENALEX_API_KEY`** Secret 可恢复稳定。 |
| **Semantic Scholar** | ⚠️ 尽力而为——共享免密钥池经常限流。 |

一个礼貌的小动作：把 **`CONTACT_MAILTO`** *变量*（注意是 **Variables 标签页**，不是 Secrets——Settings → Secrets and variables → Actions → **Variables** → New repository variable）设成你的邮箱。CrossRef 和 OpenAlex 会把带联系邮箱的请求放进更快更稳的「礼貌池」。它不是密钥，只是自报家门。

## 9. 让 AI 替你配置

如果你用 Claude Code、Codex 或类似编码智能体，仓库自带维护技能 **Page Skill｜书童Skill**，可以自动完成第 4–8 步。在智能体里打开你的仓库并粘贴：

> Use the Page Skill (书童Skill) in this repo. Interview me about my news sources, academic fields, calendars, and Canvas; update config/ for me; then guide me through adding each GitHub Secret myself. Never ask me to paste secret values into chat, and never commit URLs that contain tokens.

（也可以用中文和它交流。）它会：

- **访谈你**——读什么、什么领域、用哪些日历和 LMS。
- **替你修改 `config/`** 并校验结果。
- 每个 Secret 都**带着你自己去 GitHub 界面添加**：告诉你确切的名称和取值方法，但**绝不要求你把值粘进对话**，也绝不写进文件。如果某个智能体索要你的口令或 Token 原文——拒绝它，这个技能不是这么用的。

## 10. 使用你的仪表盘

- **解锁**——存在加密栏目时会出现解锁按钮，输入 `NEWSDASH_PASSPHRASE` 里的口令。口令错误会即时提示，无需下载任何数据。
- **「在此设备上记住」**——解锁时的可选项，把派生密钥存在浏览器里，下次免输。只在真正属于你的设备上使用：能打开这个浏览器配置的人就能读你的私密栏目。点「锁定」即抹除。
- **批注**——在条目卡片里选中文字，选择**高亮**、**摘录**或**笔记**。所有保存的内容都进入**摘录**视图，可一键导出 **Obsidian 友好的 Markdown**。批注只存在你的浏览器本地（绝不上传），且**只在解锁后可见**。
- **主题与语言**——语言开关随时切换中英文；主题（`the-type` / `nyt` / `bear`）可在页面里切换，或通过配置 Issue 永久设定。
- **打印简报**——打印视图会把当前页面排成一份干净的纸质简报，直接用浏览器打印（⌘P / Ctrl+P）。

## 11. 疑难排查

| 症状 | 可能原因 → 解法 |
|---|---|
| Actions 里**构建红了** | 打开失败运行的日志——报错行会指出哪个信源或密钥出了问题。`private` 站点缺 `NEWSDASH_PASSPHRASE` 时会**故意**拒绝发布：补上 Secret（[第 5 步](#5-私密模式与口令)）再重跑。 |
| **页面内容陈旧** | Pages CDN 缓存约 10 分钟——等一等、强刷。还旧？去 Actions 确认 "Update Newsdash" 最近确实跑绿了。 |
| **日程空了 / 报错** | 你在 Google 点过 *重置* 私密地址（或 Google 替你重置了），Secret 里的旧 URL 就失效了。复制新地址、重建 `ics-sources.json`、重新编码（[6c](#6c-编码并添加-secret)）、更新 `ICS_SOURCES_B64`、重跑工作流。 |
| **「等待首次构建」屏** | 流水线从没跑过。Actions → Update Newsdash → Run workflow（[第 2 步](#2-第一次构建)）。 |
| **更新悄悄停了** | 仓库 **60 天无活动后 GitHub 自动停用定时工作流**。Actions 标签页会显示提示条 → 点 **Enable**。任何一次提交也会重置计时。 |
| **「口令错误」** | 检查拼写、空格、大小写——必须与 Secret 完全一致。刚改过 Secret？要等下一次 "Update Newsdash" 跑完重新加密后，站点才认*新*口令。 |
| **私密栏目显示「未配置」** | 构建时缺该栏目的密钥。日程需要 `ICS_SOURCES_B64` **加** `NEWSDASH_PASSPHRASE`；课程需要 `CANVAS_BASE_URL` + `CANVAS_TOKEN` **加** `NEWSDASH_PASSPHRASE`。补齐后重跑。 |

---

下一篇：数据文件与加密到底如何工作 → [DATA_CONTRACT.md](DATA_CONTRACT.md)
