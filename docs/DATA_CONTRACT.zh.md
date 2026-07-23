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
- `insights_file`: 可选 AI 摘要/今日一图/无关一则文件，可能为 `null`
- `threads_file`: 公开范围「线索」文件，可能为 `null`（未启用/无结果）
- `threads_private_file`: 私密范围「线索」文件（opt-in），可能为 `null`
- `ai_summary.enabled`: 本次构建是否配置了 `LLM_API_KEY`

栏目 `status` 为 `ok`、`degraded`、`error` 或 `not_configured`。加密栏目不在
manifest 里暴露 `count`；描述性元数据只在解密后的 payload 里。

`visibility: "private"` 时，所有栏目、`source-status`、archive、insights 与全文
阅读文件都加密，页面先进入整页口令门。

`id: "private"` 是一个一等公民的 `kind: "news"` 栏目，由 `category:
"private"` 的信源供给（见 `docs/CONFIG_REFERENCE.zh.md`「私密 URL
信源」）。只有配置了至少一个私密信源时才会出现在 `sections[]` 里；且不论
站点本身的 `visibility` 是什么，它**永远** `encrypted: true`、同样省略
`count`——公开站点只要配了一个私密信源，这一个栏目照样以密文形式出现在
同一道口令门后面。

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
- 公开范围「线索」：`newsdash:v1:threads`
- 私密范围「线索」：`newsdash:v1:threads-private`
- 全文阅读文件：`newsdash:v1:article:<section_id>:<item_id>`
- 口令校验块：`newsdash:v1:check`

（信封本身参数不因「线索」改变，无需 bump `v`。）

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

由私密信源（`category: "private"`）供给的栏目，其详情在公开站点上也始终
加密；公共 `source-status.json` 只暴露私密信源的聚合数。这就是上面
manifest 一节提到的 `id: "private"` 栏目：`kind: "news"`，只要配置了任一
私密信源就出现，且永远 `encrypted: true`、省略 `count`。

## 5. 旁路文件

`source-status.json`：

```jsonc
{ "generated_at": "…Z",
  "sources": [ { "id": "…", "ok": true, "count": 3,
                 "full_text_count": 1, "error": null,
                 "skip_reason": null } ],
  "private_summary": { "total": 2, "configured": 1 } }
```

私密信源永远只以 `private_summary` 汇总出现——绝不会有某个私密信源的单独
条目、名称、条数或报错；详情只存在于加密的 `private` 栏目自己的 `meta`
里。

`archive.json` 只保存 open + optional 条目的滚动摘要，上限 3000。archive 故意移除
`full_text_available` 与 `full_text_file`，避免指向已经被下一次构建清掉的全文文件。

`insights.json` 不是 manifest section；配置 `LLM_API_KEY` 后才可能出现。它只从
`news` / `papers` 条目的标题和短摘要生成，绝不读取全文正文；私密可见性下同样加密。

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
  "todays_image": { /* 找到 CC0 图片时才出现 */ },
  "apropos_of_nothing": {
    "topic": "competitive pumpkin growing",
    "query": "(\"pumpkin championship\" OR \"giant pumpkin\")",
    "summaries": {
      "en": {
        "summary": "一条英文短摘要。",
        "why_irrelevant": "一句英文说明它为何偏离当前信息流。"
      },
      "zh": {
        "summary": "一条中文短摘要。",
        "why_irrelevant": "一句中文说明它为何偏离当前信息流。"
      }
    },
    "source": {
      "title": "Giant pumpkin champion breaks local record",
      "url": "https://example.org/pumpkin",
      "name": "example.org",
      "published_at": "2026-07-08T10:00:00Z"
    }
  }
}
```

英文与中文摘要由 LLM 分别生成。每次生成都会读取英中两种语言的
`news` / `papers` 输入，但优先围绕目标语言的条目展开，并用目标语言写作。
前端优先读取 `summaries[当前语言]`；顶层三个摘要字段保留为英文/default
兼容副本，供旧缓存前端回退。

`apropos_of_nothing` 是构建时的“破信息茧房”模块。配置的 LLM 先只读取
`news` / `papers` 的标题与短摘要，提出一个温和、低风险、尽量远离当前信息流的
英文搜索词；管线再通过 GDELT DOC API（`mode=artlist`、`format=json`、一周窗口）
检索公开新闻，最后由 LLM 为其中一个带来源的结果写出英中双语短卡片。如果 GDELT
被限流或本次没有带来源的结果，该字段会在这次构建中省略。访客浏览器不会为了这个
模块联系 GDELT 或 LLM 端点。

### `threads.json` / `threads.enc.json` / `threads-private.enc.json` —「线索」可选 AI enrichment

不是 manifest section，而是 `manifest.threads_file` / `threads_private_file`
指向的旁路文件，因此不会自动出现导航标签。「线索 · Threads」取代前端计算的
Highlights 区块：由 LLM 挑出今日至少被两个不同信源触及的关键词主题，每条附
双语释义、一句「为何是现在」的时机说明、一个收敛度判定，以及指回原始条目的
逐信源 angle。仅当 `site.json → threads.enabled`（默认 `true`）且配置了
`LLM_API_KEY` 时构建；`--smoke` 下永不运行；每个范围各调用一次双语 LLM。

两个完全隔离的范围：

- **public**——输入只取 `open`/`optional` 类别栏目；写为 `threads.json`，
  或在 `visibility: "private"` 时写为 `threads.enc.json`（AAD
  `newsdash:v1:threads`）。
- **private**——通过 `threads.include_private`（默认 `false`）显式开启；
  输入只取 `category: "private"` 栏目。不论站点可见性如何永远加密写出为
  `threads-private.enc.json`（AAD `newsdash:v1:threads-private`）——不存在
  明文版本。只有同时满足 `include_private`、已配置口令、`LLM_API_KEY` 三者
  时才会运行。

```jsonc
{
  "meta": { "generated_at": "…Z", "scope": "public", "count": 5 },
  "threads": [ {
      "id": "t1",                           // "t1"…"tN"（public）或 "p1"…"pN"（private），二者绝不冲突
      "keyword": { "en": "compute sovereignty", "zh": "算力主权" },
      "gloss":   { "en": "1–2 句轻盈释义，可略带诗意", "zh": "…" },   // 每种语言 ≤240 字符
      "why_now": { "en": "一句时机说明", "zh": "…" },                 // 每种语言 ≤120 字符
      "convergence": "convergent",          // "convergent" | "mixed" | "divergent"（非法值会被纠正为 "mixed"）
      "relates_to": ["t3"],                 // 本次构建中其他相关线索的 id，可为 []
      "angles": [ {                         // ≥2 条，解析后至少对应 2 个不同信源
          "item_id": "…", "section": "news", "source": "…",
          "phrase": { "en": "≤8 词", "zh": "≤16 字" },
          "url": "https://…",
          "full_text_file": "articles/news/….json"   // 仅当解析出的条目有全文阅读文件时才出现
      } ]
  } ]
}
```

private 版本 shape 相同，`"scope": "private"`，id 为 `p1…pN`。

**防幻觉引用机制**：prompt 把候选条目编号为 `[1]…[N]`；模型只返回整数引用
作为 angle；管线据此解析出真实的 `item_id`、`section`、`source`、`url`、
`full_text_file` 并自行填入——这些字段从不直接采信模型输出。越界引用会被
丢弃；解析后关联信源不足 2 个的线索整条丢弃（不信任模型自称的收敛）。线索
条数上限为 `threads.max_threads`（2–6，默认 6）。

**前端回退规则**：「线索」取代 Highlights。当 `threads_file` 为 `null`、
文件加载失败，或加载后的 payload 没有线索时，前端回退渲染既有的
Highlights 区块（遵循 `site.ranking`）。

## 6. 前端隐私不变量

1. 不把解密内容或口令写入存储；派生密钥只在用户明确勾选“记住此设备”时保存。
2. 高亮、摘录、笔记与收藏只在解锁后显示，保存在本机 IndexedDB / localStorage。
3. 锁定时清除内存密钥、记住的密钥与已解密栏目数据。
4. 概览数字只从已加载的客户端数据计算；不得把私密计数写入明文文件。
5. AI 摘要、今日一图与“无关一则”都是构建时 enrichment，不在访问者浏览器里调用 LLM。
6. 私密范围「线索」只在解锁后渲染——与其他加密栏目同一道门。公开「线索」
   只从非私密类别的输入构建，即使站点上同时存在私密栏目也绝不掺入其数据。
7. 线索的 `angles` 字段故意不受内容语言过滤器约束（该过滤器作用于
   `news`/`papers`/`following`/Today 信息流区块）——跨语言的收敛正是这个
   功能的意义所在，不要为了「统一语言」而过滤 angles。
