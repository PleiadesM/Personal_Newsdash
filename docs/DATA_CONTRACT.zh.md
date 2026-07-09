# 数据契约——pipeline ⇄ 前端

[English](DATA_CONTRACT.md)

这是 Python 管线（`scripts/`）与静态前端（`index.html` + `assets/js/`）
之间的接口说明。凡是改这里，都要同步改两端实现与测试。

## 1. 发现文件：`data/manifest.json`

`manifest.json` 永远明文：登录前也要能读取。前端用
`cache: "no-store"` 加 `?t=<Date.now()>` 获取 manifest；其他数据文件用
`<file>?v=<build_id>`，用构建号绕过 GitHub Pages CDN 缓存。

核心字段：

- `schema_version`、`app`、`app_version`、`status`、`generated_at`、`build_id`
- `site`: 标题、语言、主题、时区、`visibility`
- `crypto`: 只在配置了口令时出现，包含 PBKDF2 参数与快速校验块
- `sections[]`: 每个栏目 `{ id, kind, category, file, encrypted, status, count? }`
- `source_status_file`: 信源健康文件
- `insights_file`: 可选 AI 摘要/今日一图文件，可能为 `null`
- `ai_summary.enabled`: 本次构建是否配置了 `LLM_API_KEY`

栏目 `status` 为 `ok`、`degraded`、`error` 或 `not_configured`。加密栏目不在
manifest 里暴露 `count`；描述性元数据只在解密后的 payload 里。

`visibility: "private"` 时，所有栏目、`source-status`、archive、insights 与全文
阅读文件都加密，页面先进入整页口令门。

## 2. 加密信封

每个 `*.enc.json` 都是一个 JSON 对象：

```jsonc
{ "v": 1, "alg": "AES-256-GCM",
  "kdf": { "name": "PBKDF2", "hash": "SHA-256",
           "iterations": 600000, "salt": "<b64 16B>" },
  "aad": "newsdash:v1:<id>",
  "nonce": "<b64 12B>",
  "ct": "<b64: ciphertext || 16B GCM tag>" }
```

口令先 NFC 规范化，再用 PBKDF2-HMAC-SHA256 派生 32 字节密钥。每次构建一个
salt，每个文件独立 nonce。

AAD 必须由前端根据正在读取的对象本地计算，不能信任信封里的 `aad` 字段：

- 栏目文件：`newsdash:v1:<section_id>`
- 信源健康：`newsdash:v1:source-status`
- AI enrichment：`newsdash:v1:insights`
- 全文阅读文件：`newsdash:v1:article:<section_id>:<item_id>`
- 口令校验块：`newsdash:v1:check`

不要改算法、KDF 参数、salt/nonce 长度或 AAD 规则，除非同步 bump 版本并更新
`scripts/newsdash/crypto.py`、`assets/js/crypto.js`、本文档与 crypto 测试。

## 3. `news` / `papers` / `following`

栏目 payload：

```jsonc
{
  "meta": { "generated_at": "…Z", "section": "news", "kind": "news",
            "window_hours": 24, "count": 142,
            "sources": [ { "id": "openai_blog", "name": "OpenAI News",
                           "category": "open", "section": "news", "type": "rss",
                           "ok": true, "count": 3, "full_text_count": 1,
                           "error": null, "skip_reason": null } ] },
  "items": [ {
    "id": "a1b2c3d4e5f60708",
    "title": "…", "url": "https://…",
    "source": "OpenAI News", "source_id": "openai_blog",
    "category": "open", "section": "news", "kind": "news",
    "published_at": "2026-07-06T12:34:00Z",
    "summary": "纯文本，≤300 字符",
    "full_text_available": true,
    "full_text_file": "articles/news/a1b2c3d4e5f60708.json",
    "tags": ["model-release"], "lang": "en", "score": 0.73,
    "extra": { "also_in": [ { "source": "…", "url": "…" } ] }
  } ]
}
```

`full_text_available` / `full_text_file` 只在 RSS/Atom 条目自带足量嵌入正文时出现。
管线只保存清洗后的纯文本，不保存上游 HTML；v1 不抓取原文页面。全文文件位于
`data/articles/<section>/<item_id>.json`；私密可见性下是 `.enc.json`。

全文文件按需由 `#/read/<section>/<item_id>` 加载：

```jsonc
{
  "meta": { "generated_at": "…Z", "section": "news",
            "item_id": "a1b2c3d4e5f60708",
            "source": "OpenAI News", "source_id": "openai_blog" },
  "item": { /* 同一条摘要 item shape */ },
  "full_text": "清洗后的纯文本正文，上限 50,000 字符"
}
```

论文额外带 `authors`、`venue`，以及 `extra.doi` / `extra.arxiv_id` /
`extra.abstract_snippet` / `extra.citations`。`following` 使用同一 shape。

`item.lang` 为 `"en"` 或 `"zh"`：若信源配置了 `lang`，则整源固定；否则逐条
检测。前端把当前界面语言同时作为内容语言：英文模式只渲染 `lang: "en"` 的
新闻/论文/关注条目与全文阅读；中文模式只渲染 `lang: "zh"` 条目。

## 4. 私密栏目

`schedule` payload 含 `meta.timezone`、`meta.calendars`、`meta.sources` 与
`events[]`。事件已展开 RRULE，按 `start` 排序。

`courses` payload 含 `courses[]`，每门课可带 `announcements[]` 与 `upcoming[]`。

这两类详情在公开站点上也始终加密；公共 `source-status.json` 只暴露私密信源的
聚合数。

## 5. 旁路文件

`source-status.json`：

```jsonc
{ "generated_at": "…Z",
  "sources": [ { "id": "…", "ok": true, "count": 3,
                 "full_text_count": 1, "error": null,
                 "skip_reason": null } ],
  "private_summary": { "total": 2, "configured": 1 } }
```

`archive.json` 只保存 open + optional 条目的滚动摘要，上限 3000。archive 故意移除
`full_text_available` 与 `full_text_file`，避免指向已经被下一次构建清掉的全文文件。

`insights.json` 不是 manifest section；配置 `LLM_API_KEY` 后才可能出现。它只从
`news` / `papers` 条目生成，绝不读取日程或课程；私密可见性下同样加密。

```jsonc
{
  "meta": { "generated_at": "…Z" },
  "summaries": {
    "en": {
      "brief": "英文首页总摘要",
      "news_summary": "英文新闻摘要",
      "papers_summary": "英文研究/论文摘要"
    },
    "zh": {
      "brief": "中文首页总摘要",
      "news_summary": "中文新闻摘要",
      "papers_summary": "中文研究/论文摘要"
    }
  },
  "brief": "summaries.en.brief 的兼容副本",
  "news_summary": "summaries.en.news_summary 的兼容副本",
  "papers_summary": "summaries.en.papers_summary 的兼容副本",
  "todays_image": { /* 找到 CC0 图片时才出现 */ }
}
```

英文与中文摘要由 LLM 分别生成。每次生成都会读取英中两种语言的
`news` / `papers` 输入，但优先围绕目标语言的条目展开，并用目标语言写作。
前端优先读取 `summaries[当前语言]`；顶层三个摘要字段保留为英文/default
兼容副本，供旧缓存前端回退。

## 6. 前端隐私不变量

1. 不把解密内容或口令写入存储；派生密钥只在用户明确勾选“记住此设备”时保存。
2. 高亮、摘录、笔记与收藏只在解锁后显示，保存在本机 IndexedDB / localStorage。
3. 锁定时清除内存密钥、记住的密钥与已解密栏目数据。
4. 概览数字只从已加载的客户端数据计算；不得把私密计数写入明文文件。
5. AI 摘要与今日一图是构建时 enrichment，不在访问者浏览器里调用 LLM。
