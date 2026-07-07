# Page Skill｜书童Skill

**The maintainer-side agent skill for [Personal Newsdash](../../README.md).**
Open your Newsdash repo in Claude Code / Codex and the skill turns setup and
maintenance into a conversation: it interviews you, writes your config,
classifies new sources, and walks you through every GitHub Secret — without
ever touching a secret value.

## Kickoff prompt

```text
Use Page Skill for Personal Newsdash. Interview me first: which preset packs I want
(ai-news, general-news, academic-datavis, academic-techcomm), my interest keywords,
my theme and timezone, and whether the site should be public or private. Then classify
any extra sources I give you as Open, Private, or Optional. Walk me through every
GitHub secret step by step — but never ask me to paste a secret value into the chat,
and never commit tokens, calendar URLs, or passphrases into the repo.
```

## Why "Page｜书童"?

A 书童 is the scholar's study attendant in classical China: he keeps the
master's schedule, fetches the day's readings, sorts the correspondence — and
never breaks the seal on a private letter. "Page" carries the same triple
duty in English: the page boy who attends, the pages you read, and the GitHub
Pages he sweeps every two hours. Where ai-news-radar's 伯乐 (Scout) judged
horses, the 书童 carries your books.

## What it will and won't do

| Will | Won't |
|---|---|
| Interview you and edit `config/` for you | Ask you to paste a passphrase, token, or calendar URL into chat |
| Tell you the exact secret name + settings URL + terminal one-liner | Echo, store, or commit any secret value |
| Classify new sources (Open / Private / Optional) and write the config entry | Add a capability URL to the repo (the schema blocks it anyway) |
| Run the validators and watch the deploy | Print your decrypted schedule into a log |

---

# 中文说明

**Page Skill｜书童Skill** 是 Personal Newsdash（个人新闻台）内置的维护侧智能体技能。
在 Claude Code / Codex 中打开你的仓库，它会以对话的方式完成配置：先访谈你的需求，
替你修改 `config/`，为新信源分类，并一步步指导你在 GitHub 上添加各个 Secret——
但绝不经手任何密钥的值。

**为什么叫「书童」？** 书童是书斋里的伴读小童：管先生的日程、取当日的书报、
理往来的信件——却从不拆先生的私信。英文 "Page" 恰好一语三关：伴读的书童（page boy）、
你读的页面（pages）、还有他每两小时洒扫一遍的 GitHub Pages。ai-news-radar 的
伯乐相马，新闻台的书童捧书。

**启动提示词**（粘贴给你的智能体即可，中文交流亦可）：见上方 Kickoff prompt。
