# 配置指南——从零到你自己的及君

[English](SETUP.md)

这是一份点到哪、写到哪的手把手教程。核心路径完全不需要终端——一切都在 GitHub 网页里完成。任何一步卡住，直接跳到底部的[疑难排查表](#9-疑难排查)。

**选择你的节奏：**

- **快车道（10 分钟，零密钥）** → 做第 1–4 步。你会得到一个自动更新的新闻 + 论文仪表盘。
- **完整配置（再加约 10 分钟）** → 继续第 5–6 步：私密模式与学术论文包。
- **躺平车道** → 做完第 1–3 步，然后让 AI 替你完成剩下的步骤（[第 7 步](#7-让-ai-替你配置)）。

---

## 0. 你需要什么

- 一个 **GitHub 账号**（免费版即可）。
- 第一遍大约 **10 分钟**。
- **不需要任何 API Key。** 默认新闻包与学术包全程免密钥。只有当你想接入私密模式或 AI 功能时，密钥才会登场。

---

## 1. 创建你的副本

1. 在本仓库页面点绿色的 **Use this template** 按钮 → **Create a new repository**。
2. 随便起名（比如 `relevance`）。
3. **保持 Public（公开）。** 这一点重要，原因如下：
   - GitHub Pages **只对公开仓库免费**——私有仓库的 Pages 需要付费套餐。
   - 公开仓库的 Actions 分钟数**不限量**；私有仓库每月只有 2000 分钟。
   - 担心隐私？你的隐私**不**来自仓库可见性，而来自**加密**（[第 5 步](#5-私密模式与口令)）。私密栏目在提交之前就已加密，公开仓库不会暴露它们。
4. 点 **Create repository**。

## 2. 第一次构建

1. 打开新仓库的 **Actions** 标签页。如果看到「工作流已禁用」的提示条，点 **"I understand my workflows, go ahead and enable them"**。
2. 左侧列表点 **Update Relevance**。
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

> 如果页面显示 **「等待首次构建」**，说明流水线还没产出数据——回到第 2 步确认 "Update Relevance" 跑绿了。

## 4. 用配置 Issue 个性化

你不需要手改任何 JSON。仓库自带一张 Issue 表单，机器人读取并自动应用。

1. 打开 **Issues → New issue**，选 **「Set up my Relevance · 配置我的及君」**。
2. 填表：

   | 字段 | 改变什么 |
   |---|---|
   | **Interface language 界面语言** | 默认界面语言（中或英）。读者在页面上仍可随时切换。 |
   | **Site visibility 站点可见性** | **Public 公开** = 新闻/论文任何人可读，私人栏目仍加密。**Private 私密** = *全站*加密，打开即口令门——需要 `NEWSDASH_PASSPHRASE`（[第 5 步](#5-私密模式与口令)）。 |
   | **Theme 主题** | `the-type`（字砌）、`nyt`（报纸）、`bear`（小熊极简、紧凑）。三套主题均配有专门设计的深色版本。 |
   | **Site title 站点标题** | 报头文字（可选）。 |
   | **Timezone 时区** | IANA 名称，如 `Asia/Shanghai`、`America/Chicago`——用于日界（可选）。 |
   | **Open news packs 公开新闻包** | 勾选 **AI news** 和/或 **General news**。全不勾则保留两个默认包。 |
   | **Academic packs 学术论文包** | 勾选**数据可视化**和/或**技术传播**——免密钥学术信源（[第 6 步](#6-学术论文包)）。 |
   | **Extra RSS feeds 自定义 RSS** | 每行一个订阅地址，都会进入你的新闻栏目。 |
   | **Interest keywords 兴趣关键词** | 逗号分隔；命中关键词的内容排序更靠前。 |
   | **Acknowledgement 确认** | 必勾：密钥绝不写进 Issue。 |

3. **提交。** 机器人随后：
   - 更新 `config/site.json` 与 `config/sources.json` 并提交，
   - 触发重建，
   - **回帖**告诉你后续步骤（你的 Pages 地址、带直达链接的 Secrets 清单、AI 启动提示词），
   - 全部应用成功后**自动关闭该 Issue**。
4. 填错了或改主意了？**直接编辑 Issue 正文**——每次编辑机器人都会重跑，已关闭的也一样。

> ⚠️ **绝不要把密钥粘进 Issue**——口令、Token 都不行。机器人会主动扫描疑似凭据的字符串，发现即拒绝应用。密钥只去 **Settings → Secrets and variables → Actions**（下一步）。另外：只有**仓库所有者**开的 Issue 会被应用——别人在你仓库开的配置 Issue 会被直接忽略。

## 5. 私密模式与口令

一个 Secret 就能打开一切私人内容的加密：

1. 进入 **Settings → Secrets and variables → Actions → New repository secret**。
2. 名称：`NEWSDASH_PASSPHRASE`
3. 值：**至少 4 个随机单词**，例如 `maple lantern crater bicycle`。加密文件是公开可下载的，弱口令可能被离线爆破——长度胜过小聪明。
4. 点 **Add secret**，然后到 Actions 重跑一次 **Update Relevance** 让新口令生效。

要点：

- **口令就是你的登录。** 打开站点后，在浏览器里输入这个口令即可解锁加密栏目。没有单独的账号体系。
- `visibility: public` 时新闻/论文对所有人可读，任何私密栏目永远加密；`visibility: private` 时*所有*栏目加密，页面直接进入口令门。
- **更换口令**：改 Secret 的值并重跑工作流——下次构建会用新口令重新加密。但 git 有记忆：**旧密文仍留在仓库历史里**，只受*旧*口令保护。若旧口令可能已泄露，请把历史视为暴露（或压缩历史——见维护文档）。

完整加密设计（AES-256-GCM、PBKDF2、信封格式）见 [DATA_CONTRACT.md](DATA_CONTRACT.md)。

## 6. 学术论文包

在配置 Issue（[第 4 步](#4-用配置-issue-个性化)）里勾选**数据可视化**和/或**技术传播**即可——不用改任何代码。它们走免密钥学术 API，可靠性各有差异：

| 信源 | 免密钥可靠性 |
|---|---|
| **arXiv** | ✅ 可靠 |
| **CrossRef** | ✅ 可靠 |
| **OpenAlex** | ⚠️ 无 Key 尽力而为——2026 年 OpenAlex 改为积分制后，免密钥请求经常被拒。添加 **`OPENALEX_API_KEY`** Secret 可恢复稳定。 |
| **Semantic Scholar** | ⚠️ 尽力而为——共享免密钥池经常限流。 |

一个礼貌的小动作：把 **`CONTACT_MAILTO`** *变量*（注意是 **Variables 标签页**，不是 Secrets——Settings → Secrets and variables → Actions → **Variables** → New repository variable）设成你的邮箱。CrossRef 和 OpenAlex 会把带联系邮箱的请求放进更快更稳的「礼貌池」。它不是密钥，只是自报家门。

### 6a. AI 每日简报 + 今日一图 + 无关一则（可选）

默认关闭——不加 Key 就什么都不会变。加了之后，今日页面会出现 AI 撰写的每日简报，「头条」「优选论文」栏目各附一行摘要；页末还会出现「无关一则」卡片：一条刻意偏离当前信息流的公开新闻，附短 AI 摘要与来源链接。再加第二个 Key，还会出现「今日一图」栏目：一张与当日内容有松散关联的公共领域图片，附一句 AI 生成的说明。

**获取一个 LLM Key。** `LLM_API_KEY` 兼容任何 OpenAI Chat Completions 格式的服务商——用你已有账号的那个即可：

| 服务商 | `LLM_BASE_URL` | `LLM_MODEL` 示例 |
|---|---|---|
| OpenAI | `https://api.openai.com/v1`（默认值，可不填此变量） | `gpt-4o-mini`（默认值） |
| DeepSeek | `https://api.deepseek.com` | `deepseek-v4-flash` |
| OpenRouter | `https://openrouter.ai/api/v1` | 它列出的任意模型标识 |
| Groq | `https://api.groq.com/openai/v1` | 它列出的任意模型 |

1. 在你选定的服务商自己的后台申请一个 API Key。
2. 添加为仓库 Secret：**Settings → Secrets and variables → Actions → New repository secret**，名称 **`LLM_API_KEY`**。
3. 如果不是用 OpenAI，还需添加两个仓库**变量**（Variables 标签页，不是 Secrets）——**`LLM_BASE_URL`** 与 **`LLM_MODEL`**，取上表对应的值。
4. 重跑 **Update Relevance**。一次构建之后，今日页面就应该出现简报。

**加上今日一图（可选，同样需要上面的 LLM Key）。** 图片来自 [Smithsonian Open Access API](https://www.si.edu/openaccess)——官方、有文档，且只会展示明确标注 CC0（真正无版权限制）的图片。

1. 打开 <https://api.data.gov/signup/>，填姓名和邮箱即可——不需要机构隶属或审批，就是普通的免费 API 申请，Key 几秒内就会发到邮箱。
2. 添加为仓库 Secret，名称 **`SMITHSONIAN_API_KEY`**。
3. 重跑 **Update Relevance**。

这些功能只会读取你的 `news`/`papers` 条目的标题与短摘要——绝不涉及口令或全文正文——且在端点暂时不可达时会静默跳过（不报错、不产生费用）。你站点的 `Settings` 页面会显示是否「已配置」。完整说明、急停开关（`LLM_SUMMARY_ENABLED=0` / `TODAYS_IMAGE_ENABLED=0` / `APROPOS_OF_NOTHING_ENABLED=0`）与数据流出模型：见 [CONFIG_REFERENCE.zh.md §4a](CONFIG_REFERENCE.zh.md#4a-可选-ai-增强功能每日简报--今日一图--无关一则) 与 [SECURITY_MODEL.zh.md §3a](SECURITY_MODEL.zh.md#3a-可选-ai-增强功能的数据流出默认关闭)。

## 7. 让 AI 替你配置

如果你用 Claude Code、Codex 或类似编码智能体，仓库自带维护技能 **Page Skill｜书童Skill**，可以自动完成第 4–6 步。在智能体里打开你的仓库并粘贴：

> Use the Page Skill (书童Skill) in this repo. Interview me about my news sources and academic fields; update config/ for me; then guide me through adding each GitHub Secret myself. Never ask me to paste secret values into chat, and never commit URLs that contain tokens.

（也可以用中文和它交流。）它会：

- **访谈你**——读什么、什么领域。
- **替你修改 `config/`** 并校验结果。
- 每个 Secret 都**带着你自己去 GitHub 界面添加**：告诉你确切的名称和取值方法，但**绝不要求你把值粘进对话**，也绝不写进文件。如果某个智能体索要你的口令或 Token 原文——拒绝它，这个技能不是这么用的。

## 8. 使用你的仪表盘

- **解锁**——存在加密栏目时会出现解锁按钮，输入 `NEWSDASH_PASSPHRASE` 里的口令。口令错误会即时提示，无需下载任何数据。
- **「在此设备上记住」**——解锁时的可选项，把派生密钥存在浏览器里，下次免输。只在真正属于你的设备上使用：能打开这个浏览器配置的人就能读你的私密栏目。点「锁定」即抹除。
- **批注**——在条目卡片里选中文字，选择**高亮**、**摘录**或**笔记**。所有保存的内容都进入**摘录**视图，可一键导出 **Obsidian 友好的 Markdown**。批注只存在你的浏览器本地（绝不上传），且**只在解锁后可见**。
- **主题与语言**——语言开关随时切换中英文；主题（`the-type` / `nyt` / `bear`）可在页面里切换，或通过配置 Issue 永久设定。
- **打印简报**——打印视图会把当前页面排成一份干净的纸质简报，直接用浏览器打印（⌘P / Ctrl+P）。

## 9. 疑难排查

| 症状 | 可能原因 → 解法 |
|---|---|
| Actions 里**构建红了** | 打开失败运行的日志——报错行会指出哪个信源或密钥出了问题。`private` 站点缺 `NEWSDASH_PASSPHRASE` 时会**故意**拒绝发布：补上 Secret（[第 5 步](#5-私密模式与口令)）再重跑。 |
| **页面内容陈旧** | Pages CDN 缓存约 10 分钟——等一等、强刷。还旧？去 Actions 确认 "Update Relevance" 最近确实跑绿了。 |
| **「等待首次构建」屏** | 流水线从没跑过。Actions → Update Relevance → Run workflow（[第 2 步](#2-第一次构建)）。 |
| **更新悄悄停了** | 仓库 **60 天无活动后 GitHub 自动停用定时工作流**。Actions 标签页会显示提示条 → 点 **Enable**。任何一次提交也会重置计时。 |
| **「口令错误」** | 检查拼写、空格、大小写——必须与 Secret 完全一致。刚改过 Secret？要等下一次 "Update Relevance" 跑完重新加密后，站点才认*新*口令。 |
| **私密栏目显示「未配置」** | 构建时缺该栏目的密钥。私密栏目需要它自己的 Secret **加** `NEWSDASH_PASSPHRASE`。补齐后重跑。 |
| **AI 简报 / 今日一图 / 无关一则没出现** | 先看你站点的 `Settings` 页面——它会显示 `LLM_API_KEY` 是否已配置。如果显示已配置但仍不出现：确认 `LLM_BASE_URL`/`LLM_MODEL` 确实对应你的服务商（[第 6a 步](#6a-ai-每日简报--今日一图--无关一则可选)）；查看最近一次 Actions 运行日志里是否有 `[llm-summary] error: …` 或 `[apropos-of-nothing:*] error: …`。今日一图与无关一则都可能在某次运行中正常缺席——公开检索没有找到合适来源时就会跳过。 |

---

下一篇：数据文件与加密到底如何工作 → [DATA_CONTRACT.md](DATA_CONTRACT.md)
