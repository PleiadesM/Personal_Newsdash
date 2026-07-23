# 安全模型

[English](SECURITY_MODEL.md) · 实现：`scripts/newsdash/crypto.py` · 契约：[DATA_CONTRACT.md](DATA_CONTRACT.md)

> **一句话——你得到什么、得不到什么**
>
> 受保护的：私密栏目的**内容**（私密模式下则是全部内容），以及批注的可见性。
> 不受保护的：**元数据**——文件大小、更新节奏、提交时间、以及某栏目*是否*已配置。
>
> **私密站点是一个加密的公开站点——而不是一个私有仓库。**
> 免费版 GitHub Pages 永远可被公网访问；你的隐私来自密码学，而不是访问控制。

## 1. 加密规格

每个 `*.enc.json` 文件是一个信封：

```json
{ "v": 1, "alg": "AES-256-GCM",
  "kdf": { "name": "PBKDF2", "hash": "SHA-256", "iterations": 600000, "salt": "<b64 16B>" },
  "aad": "newsdash:v1:<section_id>", "nonce": "<b64 12B>",
  "ct": "<b64 密文||16B GCM tag>" }
```

- 密钥 = 对 **NFC 规范化**后的口令做 PBKDF2-HMAC-SHA256——中文和组合变音符口令在任何平台派生结果一致。
- 每次流水线运行一个盐（即一次密钥派生，约 0.5 秒）；每个文件一个全新随机 nonce——这正是 AES-GCM 的标准用法。
- AAD 把密文绑定到栏目 id：`news.enc.json` 的内容永远不可能被当成 `papers` 呈现。
- `manifest.crypto.check` 存有以 `newsdash:v1:check` 为 AAD 加密的 `"newsdash:ok"`，浏览器可在下载任何数据*之前*一秒内验证口令。它给攻击者的信息不多于任何一个数据文件（每次猜测同样要付 KDF 成本）。
- 格式由跨语言测试锁定：CI 里 Node 的 WebCrypto 解密一个 Python 加密的测试向量（`tests/test_crypto_webcrypto.mjs`）。

## 2. 威胁分析

| 对手 | 结果 |
|---|---|
| 路过的访客 / 爬虫 | 看到公开栏目（公开模式）或口令门（私密模式）；私密载荷只是密文 |
| 克隆仓库的人 | 一样——密文，外加密文的 git 历史 |
| **对口令的离线爆破** | **真正的威胁。** 密文是公开的；PBKDF2-600k 让每次猜测在民用硬件上花约 0.3 秒，但这只能*拖慢*字典攻击。弱口令（"hunter2"）会沦陷；≥4 个随机单词（约 50+ bit）不会。这是用户手里最重要的一个决定 |
| 在你的公开仓库乱开配置 Issue 的人 | 应用工作流**只**响应仓库所有者本人开的 Issue；正文经环境变量→文件传递（无 shell/模板插值）；凭据模式扫描器会拒绝内容疑似含密钥的表单 |
| 恶意 PR | GitHub 默认不向 fork PR 暴露 Secrets；CI 的守卫任务还会 grep 明文私密文件和疑似 Token 的字符串 |
| 被攻破的 Actions 运行器 | 能看到那次运行的 Secrets——这与任何 CI 系统的信任边界相同。缓解：权限受限的 Token、轮换习惯 |
| 恶意订阅源的 XSS | 前端从不把订阅内容当 HTML 渲染——只用 `textContent` 的 DOM 构建器（`assets/js/dom.js`）；条目链接先限定为 `http(s)` 才能成为超链接 |

## 3. 什么东西永远不出哪个门

- **私密信源的带权限 URL 就是凭据**（capability URL）。它们只存在于各自的 GitHub Secret 里，进程内解码，绝不写盘。私密信源的错误上报只保留异常**类名**——`requests` 的报错信息可能带出完整 URL。
- 构建日志不打印私密栏目的条数、标题、名称——公开仓库的 **Actions 日志是公开的**。
- `source-status.json` 只以汇总形式显示私密信源（`已配置 n / m`）；细节随加密载荷走。
- **加固记录：** 滚动归档 `archive.json`/`.enc.json` 的写入循环现在会在
  把条目并入归档 map 之前，显式跳过任何 category 为 `private` 的栏目。
  此前它并不按 category 过滤——一旦 `visibility: "public"` 的站点上存在
  私密栏目，其条目本会被一并归档进**明文** `archive.json`，与公开/可选
  条目混在一起，泄露私密标题/摘要的明文。已在「线索」上线的同一轮
  （v0.3.0）修复；见 `scripts/build.py` 的归档区块。

### 3a. 单信源 Secret 的传输方式

私密信源（`category: "private"`）无需在工作流里逐一具名，就能把自己的
凭据 URL 送到构建过程：**整份** GitHub Actions Secrets 表通过
`NEWSDASH_SOURCE_SECRETS: ${{ toJSON(secrets) }}` 一次性传进**唯一一个**
构建步骤（见 `.github/workflows/update.yml`）；在
`scripts/newsdash/config.py` 里，这份数据只会被过滤出匹配
`^SRC_[A-Z0-9_]+$` 的键，且这些键绝不会覆盖已经存在的真实环境变量。无论
经过这层过滤与否，Actions 自带的日志脱敏对每个 Secret 值都生效。解析出的
凭据 URL 此后只存在于**构建进程的内存**里——也就是那次运行的
`src.url`——绝不写进配置、绝不写日志（私密信源的报错只保留异常类名）、
也绝不出现在任何输出文件里，包括 `source-status.json`（它永远只能看到
汇总的 `private_summary`）。把这一点当作不变量：**一旦某个私密信源的
URL 被贴到任何公开场合**——Issue、PR、日志、聊天——立即视同泄露，马上
轮换/重新生成（见 §5）。

### 3b. 可选 AI 增强功能的数据流出（默认关闭）

只有配置了 `LLM_API_KEY` 和/或 `SMITHSONIAN_API_KEY`（见
`docs/CONFIG_REFERENCE.zh.md` §4a）才会出现以下三种数据流：

- **构建时（服务端 → LLM 端点）。** 每次定时构建，流水线可能会把你的
  `news`/`papers` 条目的**标题与短摘要**发送给你配置的 LLM 端点——绝不
  发送完整正文，绝不涉及私密栏目内容，绝不涉及口令。这是整个流水线
  中唯一一条会联系你无法确认身份的第三方的代码路径（其余每个抓取器都
  指向一个固定、具名的 API）。生成的文字在构建时就烘焙进
  `insights.json`/`.enc.json`；访客的浏览器绝不会联系 LLM 端点。
- **构建时（服务端 → GDELT DOC API）。** 如果启用“无关一则”，管线会用
  LLM 生成的离题公开新闻检索词请求一次 GDELT。请求中**不会**包含私密栏目
  数据、全文正文、口令、Token 或带权限的信源 URL。
- **运行时（访客浏览器 → Smithsonian CDN）。** 若「今日一图」渲染出来，
  `<img>` 标签会直接从 Smithsonian 的图片 CDN（`ids.si.edu`）拉取图片——
  这是本仪表盘**第一次**从访客浏览器发起运行时第三方资源请求（此前所有
  资源都来自你自己的 Pages 域名）。已用标签上的
  `referrerpolicy="no-referrer"` 做了缓解，但该请求本身（来源 IP、时间）
  仍会像网络上任何被外链的图片一样，对 Smithsonian 可见。

两个功能都默认关闭，只有你主动添加对应 Secret 才会启用；且两者在端点
不可达或行为异常时都会静默跳过，绝不导致构建失败。

### 3c. 私密范围「线索」（opt-in，默认关闭）

「线索 · Threads」（`docs/CONFIG_REFERENCE.zh.md` §4a）的**公开**范围只对
`open`/`optional` 条目运行——数据流出方式与上面的每日简报相同。它的
**私密**范围是一个单独的显式 opt-in（`threads.include_private`，默认
`false`），有更严格的约定：

- **输入隔离。** 私密范围的 LLM 调用只用 `category: "private"` 的载荷构造
  ——它绝不会看到 `open`/`optional` 条目，公开范围的调用也绝不会看到私密
  条目。两个范围各自单独打包、单独构造 prompt、单独发起请求。
- **只加密输出。** 私密范围的结果只写入
  `data/threads-private.enc.json`，AAD 为 `newsdash:v1:threads-private`。
  它没有明文代码路径——与其他任何跟随站点 `visibility` 的栏目不同，即使
  站点 `visibility: "public"`，这个文件也永远是密文。
- **日志纪律。** 私密路径的错误处理只打印两行之一，且都不含细节，因为
  公开仓库的 Actions 日志是公开的：成功时 `[threads:private] written`，
  失败时 `[threads:private] error: <ExceptionTypeName> (detail withheld)`
  ——绝不出现 HTTP 状态码、响应体、条目标题或计数。

## 4. 浏览器侧

- 派生密钥保存在内存里。**「在此设备上记住」**（需勾选）把派生密钥字节——而非口令——存入 `localStorage`；此后拿到这个浏览器配置的人就能解锁。共用电脑请勿勾选。
- **锁定**会抹除内存中的密钥、记住的密钥以及所有已解密数据，并重新渲染。
- 批注存在你设备的 IndexedDB 里，仅解锁期间渲染。v0.1 里它们**在本地未加密存储**（在你自己的浏览器配置内）；加密同步是 v0.2 的事项。

## 5. 轮换与应急手册

| 情形 | 处理 |
|---|---|
| 更换口令 | 更新 `NEWSDASH_PASSPHRASE` → 跑一次 *Update Newsdash*。新密文全面替换。**git 历史仍保留旧密文**、只受旧口令保护——要么接受，要么清史（`git filter-repo --path data --invert-paths` 后强推并重跑） |
| 信源带权限 URL 或 Token 泄露 | 在源头轮换（重新生成/重置），再更新对应的 GitHub Secret |
| 把密钥粘进了 Issue/聊天/日志 | 视同泄露：立即轮换。配置 Issue 的扫描器会尽力拦截，但轮换才是唯一真解 |
| 忘了口令 | **没有恢复机制。** 设一个新的；之后的数据用新口令加密；历史里的旧密文永远封存 |

## 6. 残余风险与非目标

- 元数据泄露（大小、节奏、配置了哪些栏目）——已接受并如实写明。
- Pages 地址可被猜出（`<用户名>.github.io/<仓库名>`）；私密模式给出的是口令门，不是 404。
- 不做密钥托管或找回，这是设计决定。
- 不做多用户、角色或分享——这是单人仪表盘。需要真正的访问控制时，请使用 GitHub Enterprise 的受控 Pages 或私有托管。
