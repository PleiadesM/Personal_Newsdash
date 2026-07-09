# 配置手册——「想改 X → 编辑 Y」

[English](CONFIG_REFERENCE.md) · 适用于 `config/*.json`、`config/presets/*.json`、`.github/workflows/update.yml`。

**核心方针**（承自 ai-news-radar）：密钥进 **Secrets**；调参进**配置文件**；GitHub Variables 只当**急停开关**。以下一切都是纯 JSON，由 `config/schema/` 里的 Schema 校验——`python scripts/validate_config.py` 会准确告诉你哪里不对。

## 1. 一分钟总览（出厂默认）

| 维度 | 默认值 | 位置 |
|---|---|---|
| 更新频率 | 每 2 小时（`17 */2 * * *`） | `update.yml` 的 cron 行 |
| 新闻窗口 | 24 小时 | `site.json → windows.news_hours` |
| 论文窗口 | 7 天 | `windows.papers_days` |
| 日程窗口 | −1 天 … +14 天 | `windows.schedule_past_days` / `schedule_horizon_days` |
| 课程视野 | 30 天 | `windows.courses_horizon_days` |
| 归档保留 | 14 天（上限 3000 条） | `windows.archive_days` |
| 启用的信源包 | `ai-news`、`general-news` | `sources.json → presets` |
| 主题 / 语言 | `the-type` / `en` | `site.json` |
| 可见性 | `public` | `site.json → visibility` |

## 2. `config/site.json`

| 键 | 取值 | 作用 |
|---|---|---|
| `title`、`subtitle` | 字符串 | 报头文字与 `<title>` |
| `visibility` | `"public"` \| `"private"` | **public**：新闻/论文明文，日程/课程永远加密。**private**：*所有*文件加密、站点直接进口令门；缺 `NEWSDASH_PASSPHRASE` 时构建**直接失败** |
| `languages` | `["en","zh"]` 的子集 | 提供哪些界面语言 |
| `default_language` | `"en"` \| `"zh"` | 访客切换之前的默认界面语言与内容语言 |
| `theme` | `"the-type"` \| `"nyt"` \| `"bear"` | 默认主题（访客可切换，按浏览器记忆） |
| `timezone` | IANA 名称 | 日程开窗与事件时区偏移（显示用访客本地时钟） |
| `windows.*` | 整数 | 见总览表；Schema 限定合理范围 |

## 3. `config/sources.json`

```jsonc
{
  "presets": ["ai-news", "general-news"],        // 启用的信源包
  "interests": {
    "keywords": ["data visualization", "LLM"],   // 供给评分公式里 0.35 的相关度项
    "boost": 0.15                                 // 命中任一关键词的额外加分（0–0.5）
  },
  "sources": [ /* 自定义信源 + 对预置信源的覆盖 */ ],
  "tag_rules": [                                  // 全局标签规则：作用于该栏目的所有
    { "tag": "llm", "any": ["LLM", "大模型"] },    // 信源（包内规则只作用于本包信源）；
    { "tag": "vis", "any": ["chart"], "section": "papers" }  // 省略 section 则覆盖全部内容栏目
  ]
}
```

**评分公式**：`0.45·新鲜度 + 0.35·关键词相关度 + 0.20·信源权重`；新鲜度按指数衰减（半衰期：新闻 12 小时 / 论文 84 小时）。信源报告了引用数的论文改用
`0.35·新鲜度 + 0.25·相关度 + 0.15·权重 + 0.25·引用影响力`（对数缩放，约 1000 次引用饱和），高被引论文优先展示——前端的"优先"排序与今日页都基于此。日程与课程从不评分——按时间排列。

**按 id 覆盖预置信源**——同 `id` 条目按字段合并：

```json
{ "id": "hn_frontpage_ai", "enabled": false }
{ "id": "verge_ai", "weight": 0.4 }
```

**`enabled`**：`true`（常开）· `false`（关闭）· `"auto"`（`secret_ref` 列出的环境变量齐备时开——有密钥就自动开）。不动配置的急停：把 GitHub *Variable* `<信源ID大写>_ENABLED` 设为 `0`（如 `CANVAS_ENABLED=0`）。

## 4. 信源类型

| `type` | 默认类别 | 必填 | 说明 |
|---|---|---|---|
| `rss` | open | `url` | 可加 `keywords` 做标题过滤；若 RSS/Atom 自带足量正文，会自动进入站内全文阅读 |
| `opml` | open | `url` 或 `path` | `RSS_MAX_FEEDS` 限制展开数（默认 10） |
| `feed-json` | open | `url` | JSON Feed 1.x 或裸数组 |
| `static-page` | open | `url`（+ `query` CSS 选择器） | 条目以构建时间为时间戳 |
| `arxiv` | optional | `query` | 如 `cat:cs.HC OR cat:cs.GR`，或 `au:"Jane Doe"` |
| `openalex` | optional | `query` 和/或 `filter` | 只有配 `OPENALEX_API_KEY` 才可靠 |
| `crossref` | optional | `issn` 列表或 `query` | 期刊追踪；按记录创建日期算新旧 |
| `semanticscholar` | optional | `query` | 免密钥尽力而为 |
| `ics` | private | `secret_ref` | URL 全部在 `ICS_SOURCES_B64` 里——**绝不**写进配置 |
| `canvas` | private | `secret_ref` | `CANVAS_BASE_URL` + `CANVAS_TOKEN` |

通用字段：`id`（snake_case，唯一）、`name`、`section`（`news`/`papers`/`following`/`schedule`/`courses`）、`weight`（0–1，默认 0.8）、`max_results`（默认 50）、`lang`（`"zh"`/`"en"` 固定该信源条目的语言；省略则逐条自动检测）。当前界面语言也会筛选可见新闻/研究内容：英文模式只显示英文条目，中文模式只显示中文条目。Schema **拒绝**在 `category: "private"` 信源上出现 `url`/`path`。

v1 的全文阅读器没有配置开关。仅对 RSS/Atom 信源，若 feed 条目本身提供足量嵌入正文，管线会标记 **可阅读全文**，把清洗后的纯文本写入 `data/articles/`，前端通过 `#/read/<section>/<item_id>` 打开。只有摘要的 feed 仍与过去一样跳转到原站。

### 关注学者与实验室（`following` 栏目）

把任意信源指向 `section: "following"`，就会得到独立的"关注"导航页，按被关注对象分组。最合适的是带 `filter` 的 `openalex` 信源——复制粘贴模板见 `examples/follows.sources.snippet.json`：

```json
{ "id": "follow_jane_doe", "type": "openalex", "section": "following",
  "name": "Jane Doe", "filter": "authorships.author.id:A5023888391" }
```

在 <https://openalex.org> 搜索学者，作者页 URL 结尾即 `A…` id；实验室/机构用 `authorships.institutions.lineage:I…`。arXiv 作者检索（`au:"Jane Doe"`）和实验室博客 RSS 指向同一栏目同样可行。全部免密钥——零 Secret 构建保持绿色。

### 4a. 可选 AI 增强功能（每日简报 + 今日一图）

不是信源——一个构建时的附加功能，默认关闭，没有任何配置文件字段（所有开关都是环境变量，读取方式与 `CONTACT_MAILTO`/`OPENALEX_API_KEY` 完全一致）。只在服务端运行：用你自己的 Key，绝非访客提供的 Key。构建会分别请求英文与中文摘要；只有找到 CC0 图片时才追加一次简短图片说明调用，并且每次定时构建最多一次图库检索（绝不按访客次数调用）——按设计做了预算控制。

| 配置这个 Secret…… | ……就会得到 |
|---|---|
| `LLM_API_KEY` | 今日页面问候语后出现按语言分别生成的 AI 每日简报，「头条」「优选论文」栏目各附一行对应语言摘要 |
| `LLM_API_KEY` **加上** `SMITHSONIAN_API_KEY` | 上述功能，外加「今日一图」栏目：从 [Smithsonian Open Access API](https://www.si.edu/openaccess) 中挑选一张与当日内容有松散、创意关联的公共领域图片，附一句 AI 生成的说明与来源链接 |

`LLM_API_KEY` 面向任何 OpenAI Chat Completions 兼容端点
（`{LLM_BASE_URL}/chat/completions`，`Authorization: Bearer`）——OpenAI、
OpenRouter、Groq、Together、自建 Ollama/vLLM 均可；用 `LLM_BASE_URL` /
`LLM_MODEL` 两个 Variable 调整端点/模型（默认：`https://api.openai.com/v1`、
`gpt-4o-mini`）。`SMITHSONIAN_API_KEY` 在 <https://api.data.gov/signup/>
免费申请——该 Key 通用于所有 api.data.gov API，包括 Smithsonian。

硬性保证：

- 只读取你的 `news`/`papers` 条目——**绝不**涉及日程或课程。
- 英文与中文摘要分别生成；每个摘要都会读取英中两种输入，但优先围绕目标语言。
- `--smoke` 时**绝不**发出任何网络请求，无论配置了哪些 Key。
- 只有 Smithsonian 明确标注 `usage.access: "CC0"` 的图片才会展示——权利
  状态不确定的结果一律视为「今日无图」。
- 与其他任何栏目遵循完全相同的公开/私密加密规则：`visibility: "public"`
  时明文，`visibility: "private"` 时加密。
- `LLM_SUMMARY_ENABLED=0` / `TODAYS_IMAGE_ENABLED=0`（Variable）可在保留
  Key 的情况下单独急停某个功能。

确切的载荷结构见 `docs/DATA_CONTRACT.md` 的 `insights.json` 一节。

## 5. 信源包（`config/presets/<id>.json`）

```json
{
  "id": "academic-hci",
  "name": { "en": "Academic · HCI", "zh": "学术 · 人机交互" },
  "category": "optional",
  "section": "papers",
  "sources": [
    { "id": "arxiv_hci", "type": "arxiv", "name": "arXiv cs.HC",
      "query": "cat:cs.HC", "max_results": 60, "weight": 1.0 }
  ],
  "tag_rules": [
    { "tag": "eval-study", "any": ["user study", "participants"] }
  ]
}
```

在 `sources.json` 的 `presets` 里加上 `"academic-hci"` 即启用。`tag_rules` 只作用于**本包自己的信源**——AI 包的规则不会给 BBC 的新闻打标签。

## 6. Secrets 与 Variables 总表

| 名称 | 类型 | 谁需要 |
|---|---|---|
| `NEWSDASH_PASSPHRASE` | Secret | 一切加密（私密栏目；`visibility:"private"` 时全站） |
| `ICS_SOURCES_B64` | Secret | `ics` 信源 |
| `CANVAS_BASE_URL`、`CANVAS_TOKEN` | Secret | `canvas` 信源 |
| `OPENALEX_API_KEY` | Secret | 稳定的 `openalex` |
| `FOLLOW_OPML_B64` | Secret | 私人 OPML |
| `LLM_API_KEY` | Secret | AI 每日简报 + 分栏摘要（§4a） |
| `SMITHSONIAN_API_KEY` | Secret | 今日一图（§4a）；需同时配置 `LLM_API_KEY` |
| `CONTACT_MAILTO` | Variable | CrossRef/OpenAlex 礼貌池 |
| `<ID>_ENABLED` | Variable | 设 `0` = 急停信源 `<id>` |
| `RSS_MAX_FEEDS` | Variable | OPML 展开上限 |
| `LLM_BASE_URL` / `LLM_MODEL` | Variable | AI 端点与模型（§4a） |
| `LLM_SUMMARY_ENABLED` / `TODAYS_IMAGE_ENABLED` | Variable | 设 `0` = 急停对应 AI 功能 |

## 7. 「想改 X」速查表

| 我想…… | 改这里 |
|---|---|
| 更快/更慢更新 | `update.yml` 的 cron（公开仓库可用 `*/30 * * * *`；私有仓库注意每月 2000 分钟） |
| 更长的新闻窗口 | `site.json → windows.news_hours` |
| 论文回看更久 | `windows.papers_days` |
| 归档留更久 | `windows.archive_days` |
| 关掉某个预置源 | `sources.json` 加 `{ "id": "...", "enabled": false }` |
| 追踪一本期刊 | 新建 crossref 信源，填它的 `issn` |
| 关注某学者/实验室 | openalex 信源加 `filter` + `section: "following"`（见 §4） |
| 给全站加主题标签 | `sources.json` 顶层 `tag_rules`（见 §3） |
| 把某信源标为中文 | 信源上加 `"lang": "zh"` |
| 提升我的主题 | `interests.keywords`（+ `boost`） |
| 开启 AI 每日简报 | Secret `LLM_API_KEY`（§4a） |
| 加上今日一图 | Secret `SMITHSONIAN_API_KEY`（+ `LLM_API_KEY`）（§4a） |
| 立刻停掉 Canvas | Variable `CANVAS_ENABLED=0` |
| 换默认主题/语言 | `site.json → theme` / `default_language` |
| 改站名 | `site.json → title` |

手改之后：`python scripts/validate_config.py`，提交——下一次定时运行自动生效（或 `gh workflow run update.yml`）。
