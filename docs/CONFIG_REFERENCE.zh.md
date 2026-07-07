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
| `default_language` | `"en"` \| `"zh"` | 访客切换之前的默认界面语言 |
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
  "sources": [ /* 自定义信源 + 对预置信源的覆盖 */ ]
}
```

**评分公式**：`0.45·新鲜度 + 0.35·关键词相关度 + 0.20·信源权重`；新鲜度按指数衰减（半衰期：新闻 12 小时 / 论文 84 小时）。日程与课程从不评分——按时间排列。

**按 id 覆盖预置信源**——同 `id` 条目按字段合并：

```json
{ "id": "hn_frontpage_ai", "enabled": false }
{ "id": "verge_ai", "weight": 0.4 }
```

**`enabled`**：`true`（常开）· `false`（关闭）· `"auto"`（`secret_ref` 列出的环境变量齐备时开——有密钥就自动开）。不动配置的急停：把 GitHub *Variable* `<信源ID大写>_ENABLED` 设为 `0`（如 `CANVAS_ENABLED=0`）。

## 4. 信源类型

| `type` | 默认类别 | 必填 | 说明 |
|---|---|---|---|
| `rss` | open | `url` | 可加 `keywords` 做标题过滤 |
| `opml` | open | `url` 或 `path` | `RSS_MAX_FEEDS` 限制展开数（默认 10） |
| `feed-json` | open | `url` | JSON Feed 1.x 或裸数组 |
| `static-page` | open | `url`（+ `query` CSS 选择器） | 条目以构建时间为时间戳 |
| `arxiv` | optional | `query` | 如 `cat:cs.HC OR cat:cs.GR` |
| `openalex` | optional | `query` | 只有配 `OPENALEX_API_KEY` 才可靠 |
| `crossref` | optional | `issn` 列表或 `query` | 期刊追踪；按记录创建日期算新旧 |
| `semanticscholar` | optional | `query` | 免密钥尽力而为 |
| `ics` | private | `secret_ref` | URL 全部在 `ICS_SOURCES_B64` 里——**绝不**写进配置 |
| `canvas` | private | `secret_ref` | `CANVAS_BASE_URL` + `CANVAS_TOKEN` |

通用字段：`id`（snake_case，唯一）、`name`、`section`（`news`/`papers`/`schedule`/`courses`）、`weight`（0–1，默认 0.8）、`max_results`（默认 50）。Schema **拒绝**在 `category: "private"` 信源上出现 `url`/`path`。

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
| `CONTACT_MAILTO` | Variable | CrossRef/OpenAlex 礼貌池 |
| `<ID>_ENABLED` | Variable | 设 `0` = 急停信源 `<id>` |
| `RSS_MAX_FEEDS` | Variable | OPML 展开上限 |

## 7. 「想改 X」速查表

| 我想…… | 改这里 |
|---|---|
| 更快/更慢更新 | `update.yml` 的 cron（公开仓库可用 `*/30 * * * *`；私有仓库注意每月 2000 分钟） |
| 更长的新闻窗口 | `site.json → windows.news_hours` |
| 论文回看更久 | `windows.papers_days` |
| 归档留更久 | `windows.archive_days` |
| 关掉某个预置源 | `sources.json` 加 `{ "id": "...", "enabled": false }` |
| 追踪一本期刊 | 新建 crossref 信源，填它的 `issn` |
| 提升我的主题 | `interests.keywords`（+ `boost`） |
| 立刻停掉 Canvas | Variable `CANVAS_ENABLED=0` |
| 换默认主题/语言 | `site.json → theme` / `default_language` |
| 改站名 | `site.json → title` |

手改之后：`python scripts/validate_config.py`，提交——下一次定时运行自动生效（或 `gh workflow run update.yml`）。
