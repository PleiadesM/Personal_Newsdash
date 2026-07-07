# 信源——分类、预置包与选源之道

[English](SOURCES.md) · 配置语法：[CONFIG_REFERENCE.zh.md](CONFIG_REFERENCE.zh.md) · 密钥配方：[SETUP.zh.md](SETUP.zh.md)

## 1. 三类信源，一条铁律

| 类别 | 定义 | 地址放哪 |
|---|---|---|
| **公开（Open）** | 任何人都能抓取；无凭据 | `url` 写进配置——可以放心提交 |
| **可选（Optional）** | 免密钥学术 API（有限速，但不涉密） | `query`/`issn` 写进配置 |
| **私密（Private）** | 抓取需要凭据 URL 或 Token | **只进 GitHub Secrets**——Schema 拒绝私密信源携带 `url` |

铁律：*拿到地址就等于拿到访问权的，地址本身就是凭据，绝不进仓库。* Google 的「iCal 私密地址」是最典型的例子。

## 2. 内置信源包

**`ai-news`**（公开 → 新闻）：OpenAI News 1.0 · Google AI Blog 1.0 · DeepMind Blog 1.0 · Hugging Face Blog 0.9 · Simon Willison 0.9 · MIT 科技评论 AI 0.85 · The Verge AI 0.8 · Ars Technica AI 0.8 · Hacker News 首页 0.7（关键词过滤：AI/LLM/GPT/Claude/Gemini/model/agent/machine learning/neural）。

**`general-news`**（公开 → 新闻）：BBC World 1.0 · 纽约时报首页 1.0 · 卫报国际 0.9 · NPR 0.9 · BBC 中文 0.8。

**`academic-datavis`**（可选 → 论文）：arXiv `cat:cs.HC OR cat:cs.GR` 1.0（可视化关键词过滤）· OpenAlex "information visualization" 0.9 · Semantic Scholar "data visualization" 0.8。

**`academic-techcomm`**（可选 → 论文）：CrossRef 按 ISSN 追踪 1.0——《Technical Communication Quarterly》(1057-2252)、《J. of Business & Technical Communication》(1050-6519)、《IEEE Trans. Professional Communication》(0361-1434)、《J. of Technical Writing & Communication》(0047-2816)、《Written Communication》(0741-0883) · OpenAlex "technical communication" 0.9 · arXiv cs.HC 写作/文档关键词 0.8。

学术包默认**关闭**——在配置 Issue 里勾选，或手动加进 `presets`。

## 3. 添加信源（照抄即用）

**RSS/Atom**——凡是有订阅源的，首选：

```json
{ "id": "my_lab_blog", "type": "rss", "section": "news",
  "name": "实验室博客", "url": "https://lab.example.edu/feed.xml", "weight": 0.9 }
```

信息量太大的源？加标题过滤：`"keywords": ["visualization", "accessibility"]`。

**OPML**——整份订阅列表。提交文件（`"path": "feeds/follow.opml"`）或走 `FOLLOW_OPML_B64` Secret（构建时解码，绝不提交真实文件）。

**feed-json**——直接消费别的项目公开生成的 feed（承自 ai-news-radar 的模式：用它的产出，别重造它的爬虫）：

```json
{ "id": "their_project", "type": "feed-json", "section": "news",
  "name": "他们的雷达", "url": "https://raw.githubusercontent.com/them/repo/main/feed.json" }
```

**static-page**——没有任何 feed 时的最后手段。`query` 是要收割的链接的 CSS 选择器。注意：静态页面没有时间戳，条目以构建时间为准、在页上一天就「新鲜」一天。

**arXiv**——分类与字段查询，如 `cat:cs.CL`、`cat:cs.HC AND abs:accessibility`。内置 3 秒节流；周末安静是常态。

**CrossRef**——期刊追踪的主力（`academic-techcomm` 就是这样跟住从不上 arXiv 的期刊的）。新旧按记录在 CrossRef *创建*的时间算——对慢节奏期刊而言，「本周新文」正是这个意思：

```json
{ "id": "my_journals", "type": "crossref", "section": "papers",
  "name": "我的期刊", "issn": ["1057-2252", "0741-0883"], "max_results": 40 }
```

**OpenAlex**——2026 年改积分制后，只有配 `OPENALEX_API_KEY` 才稳定；免密钥时尽力而为（被限流就是 0 条）。**Semantic Scholar**——共享免密钥池、经常 429；设计上就是尽力而为。两者都不会搞垮你的构建。

**ICS / Canvas**——私密；配置里只有 `secret_ref`。默认 `config/sources.json` 已把两个条目接到 `ICS_SOURCES_B64` 和 `CANVAS_BASE_URL`+`CANVAS_TOKEN` 上；Secrets 一到位即自动开启。配方见 [SETUP.zh.md 第 6–7 步](SETUP.zh.md)。

## 4. 选源之道（伯乐家法）

1. 优先级：官方 feed → 公开生成的 feed → OPML → 定向静态抓取 → **不如不加**。
2. 先掂量信噪比再接入。一天发 50 条、你只关心 2 条的源，要么上关键词过滤，要么别给它席位。
3. 试用期：新源以 `weight: 0.5` 入场，观察一周的 `source-status.json` 和你自己的阅读行为，再提权、降权或除名。
4. 去重是你的朋友：同一事件的多源报道会合并（高权重者胜出，`also_in` 记录其余）——多源印证看得见，又不刷屏。

## 5. 评分的作用

`score = 0.45·新鲜度 + 0.35·兴趣 + 0.20·权重`——`weight` 区分信赖源与试用源，`interests.keywords`（+ `boost`）不论来源地抬升你的主题。标签来自各包的 `tag_rules`，只作用于该包自己的信源。

## 6. 礼数

默认每 2 小时一次的节奏对谁都客气。arXiv 内置 3 秒请求间隔；设置 `CONTACT_MAILTO` 变量即可加入 CrossRef 与 OpenAlex 的「礼貌池」（更好的限速待遇，出问题时他们也找得到你，而不是直接拉黑）。
