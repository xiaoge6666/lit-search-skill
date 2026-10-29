---
name: "literature-search-cnki-pubmed"
description: "从知网(CNKI)与 PubMed/NCBI(PMC) 检索并下载文献的实战 SOP：知网只走首页搜索框绕 clickWord 验证码、PubMed eutils 检索与 elink 查 PMC、Europe PMC/PMC-POW/PLOS 三级 PDF 兜底、DOI 解析防参考文献污染、429 限速与去重；用户说「找/下 X 主题的文献」「知网下不了」「PubMed 拿全文」时触发"
---

# literature-search-cnki-pubmed — 知网 + PubMed 文献检索与全文下载

> 这是一个**只讲检索与下载**的通用版，不含任何个人账号、密钥、本机路径。
> 需要「下载后入 Zotero 建条目/笔记」的部分见文末 §8（可选）。

## 0. 三条铁律（先看这三条能省几小时）

1. **知网只走「首页搜索框」**——直接打开 `kns8s`/`kcms2` 详情 URL 必跳**文字点选验证码**，而验证码在 iframe 里，自动化过不去。
2. **PubMed 的 DOI 只能从 `PubmedData/ArticleIdList` 取**——用 `elem.iter("ArticleId")` 会一路抓到**参考文献列表里的 DOI**（实测 89 篇里错 42 篇，连带通讯作者信息全错）。
3. **429/403 一律停手等冷却**（≥15 分钟，实测可能超 24h）。密集重试会把临时限流升级成封禁。

---

## 1. 知网（CNKI）：中文文献 / 学位论文 / 机构权限文献

适用：中文期刊、硕博学位论文、需要机构订阅权限的全文。

### 1.1 前置
- 在**机构 IP 内**用浏览器打开知网，会自动 IP 登录（登录态 cookie 可长期保持），**不需要找"IP 登录"按钮**。
- 若用 OpenClaw `browser` 工具：把 `*.cnki.net`、`cnki.net`、`chndoi.org` 加进 `browser.ssrfPolicy.hostnameAllowlist`，否则被 SSRF 策略拦。
- 判定「知网不可用」前必须**实测一次**，不要凭旧印象断言。

### 1.2 检索与进详情（唯一可行路径）
1. 打开知网首页，在首页搜索框输入**短关键词（3–6 个词，命中率最高）**，回车/点搜索。
2. 结果页点**标题**进入详情页（通常新开标签）。
3. ❌ 结果页上的搜索框 `type + Enter` **不会触发重新检索**——要换词就回首页重搜。
4. ❌ 不要拼 `kns8s/defaultresult` / `kcms2/article/abstract` 这类详情 URL 直接开。

### 1.3 下载
- 详情页点「PDF下载」；若跳登录页或弹「IP 超出范围」**无视**，下载通常照常开始。
- 浏览器下载目录：`%TEMP%\openclaw\downloads\`（OpenClaw 托管的浏览器）；按 `%PDF` 头校验后转存到你的文献目录。
- 偶发滑块 / 「暂无数据」：**重试 2–3 次即过**，不是被封。

### 1.4 元数据（比 PDF 更可靠的做法）
- 详情页 `evaluate` 抓 `document.body.innerText`：能拿到导师、学科、年度、DOI、摘要。
- **学位论文年份**经常抓不到 → 用 `pypdf` 读 PDF 首页补。
- 批量补元数据：结果页勾选多篇 → 「导出与分析」→「导出文献」→ 选 **NoteExpress / RefWorks 格式**（字段最全：全量作者/导师/学校/学位/年/关键词/完整摘要/DOI）。GB/T 7714 只有前 3 作者 + 等，不适合回填。

---

## 2. PubMed / NCBI：英文文献的主力源

NCBI 三源里**最友好**：免费 API、反爬弱、有 PMC 全文通道。模板见 `templates/ncbi_search.py`。

### 2.1 eutils 基本流程
```
esearch.fcgi  → 拿 PMID 列表
esummary.fcgi → 拿题录（标题/期刊/年/作者/卷期页/DOI 有时缺）
efetch.fcgi   → retmode=xml 拿全字段（作者单位、摘要、MeSH、DOI）
elink.fcgi    → dbfrom=pubmed&db=pmc 判断有没有 PMC 全文
```

- `retmode=json` 只对 esearch/esummary 好用；`efetch` 用 `retmode=xml`。
- 速率：**无 key 3 次/秒；有 key（`api_key=`）10 次/秒**。key 申请：ncbi.nlm.nih.gov/account/settings。
- 密钥**只从环境变量/本地凭据文件运行时读取**，禁止硬编码进脚本或粘贴进对话（会被脱敏机制污染成 `sk-…` 之类，落盘直接语法错误）。

### 2.2 🔴 DOI 解析（最常见的坑）
```python
# 正确：只在 PubmedData 里找
doi = None
for node in root.findall(".//PubmedData/ArticleIdList/ArticleId"):
    if node.get("IdType") == "doi":
        doi = node.text
        break

# 错误：iter() 会把 Citation/ArticleIdList（参考文献）里的 DOI 也抓进来
```

### 2.3 结构化检索式（命中率高）
```python
TERMS = [
 '("topic"[Title] AND (fung*[Title/Abstract] OR yeast*[Title/Abstract]))',
 '"gene name"[Title] AND 2020:2026[dp]',          # 带年份窗口
 '(review[pt]) AND "topic"[Title]',               # 只要综述
]
```
- `[dp]` 日期、`[pt]` 出版类型、`[tiab]` 标题+摘要、`[au]` 作者。
- 想批量监控某主题新文：`esearch` 加 `mindate/maxdate` + `datetype=pdat`，本地存 PMID 去重。

---

## 3. 全文下载：三级兜底（按顺序试）

| 顺序 | 通道 | 说明 | 模板 |
|---|---|---|---|
| 1 | **Europe PMC** `https://europepmc.org/articles/{PMCID}?pdf=render` | 最省事，Open Access 基本都能拿 | `templates/dl_epmc.py` |
| 2 | **EBI** `fullTextPDF` | 部分出版社走这条 | 同上脚本里换 URL |
| 3 | **PMC 官网 POW 直连** `https://pmc.ncbi.nlm.nih.gov/articles/{PMCID}/pdf/main.pdf` | EPMC 404 时切它；遇 `POW_CHALLENGE` 需解 sha256 前缀 nonce 并带 cookie 重试 | `templates/pmc_pow_dl.py` |
| 4 | **PLOS 直链** | `journals.plos.org/plosone/article/file?id=<DOI>&type=printable` | — |

校验：`content[:4] == b"%PDF"` 且 **> 50 KB**（拦截登录页/HTML 错误页）。

### 3.1 哪些源会硬失败（别浪费重试）
- Wiley / ASM / Taylor&Francis / ScienceDirect：Cloudflare reCAPTCHA 或 403。
  → 有 PMC 版本就走 PMC（mBio 等 ASM 刊都有）；没有就换 OA 备选。
- ScienceDirect 的签名 URL **有效期约 300 秒**，拿到必须马上用。
- PMC 有版本的，**优先 Europe PMC**，比官网 POW 稳。

### 3.2 代理与直连
- NCBI / Europe PMC：**直连通常可用**；被限流时再挂代理。
- 若用 `requests` 而本机开了系统代理（Clash 等），**务必** `session.trust_env = False` 强制直连——否则代理会篡改请求头导致 401/连接重置（Zotero/GitHub/DeepSeek 同坑）。
- `curl.exe` 默认不走系统代理，POW 解算那条路要用 curl 而不是 requests。

---

## 4. Google Scholar（补充源，最难）

- headless 浏览器会被 `sorry` 页拦。可行法是 **cookie 法**：先用 `requests` GET `google.com` 拿 `NID` cookie → 同一 session 访问 `scholar.google.com/scholar?q=...` 返回 200 可解析。
- 成功率不是 100%；**每次只挑 2 篇高被引 OA**，别指望批量。
- Scholar 条目常缺 DOI → 用 Crossref 按标题补全后回填。
- Wiley/T&F/ScienceDirect 命中也是 CF 403，直接跳过。

---

## 5. 限速、去重与反封

- 批处理：**≤5 篇/批，单条间隔 ≥1s**。
- `429 / 403 Too many authentication failures` = 临时封禁，**立即停止**，等 ≥15 分钟（可能 24h+）。禁止边等边试。
- 去重：入库/落盘前先按 **DOI 优先，其次 标题规范化（小写、去标点、压空白）** 比对已有序号；实测一批 9 篇里能有 4 篇重复。
- 文件命名：`来源_作者-年_短标题.pdf`（ASCII 化，避免中文附件名在部分 API/Release 上传时被吞）。

---

## 6. 一次性完整流程（可直接照跑）

```
① 定主题 → 拆 2-3 组检索式
② PubMed(esearch) 拿候选 PMID → esummary 粗筛标题/年份/期刊
③ elink 查 PMC → 有 PMCID 的进"可下全文"清单
④ Europe PMC render 批量下 → 404 的转 PMC POW → 仍失败试 PLOS
⑤ 中文/学位论文：走知网首页搜索框 → 详情 → PDF下载 → 导出 NoteExpress 补元数据
⑥ 全部过 %PDF + >50KB 校验，按 DOI 去重
⑦ 输出清单：标题 | 年 | 期刊 | DOI | PMID/PMCID | 本地文件名
```

---

## 7. 踩坑速查表

| 现象 | 原因 / 解法 |
|---|---|
| 知网一打开就跳点选验证码 | 直开了 kns8s/kcms2 详情 URL → 改用首页搜索框 |
| 知网结果页换词不生效 | 结果页搜索框不触发重检索 → 回首页重搜 |
| 知网偶发「暂无数据」/滑块 | 正常波动，重试 2–3 次 |
| PubMed DOI 对不上、作者全错 | 用了 `iter("ArticleId")` 抓到参考文献 DOI → 只取 `PubmedData/ArticleIdList` |
| Europe PMC `?pdf=render` 404 | 转 PMC 官网 POW 直连 |
| PMC 官网返回 `POW_CHALLENGE` HTML | 解 sha256 前缀 nonce，带 `cloudpmc-viewer-pow=<challenge>,<nonce>` cookie 重试 |
| 下载得到 HTML 不是 PDF | 校验 `%PDF` 头 + 大小 >50KB |
| 401 / header 报 Bearer 错 | requests 走了系统代理 → `session.trust_env=False` |
| 429 越重试越久 | 停 ≥15 分钟；批量改 ≤5 篇/批、间隔 ≥1s |
| OpenAlex 突然全 429 | 免费额度按**出口 IP 每日**共享，北京 08:00 重置；挂代理无效 |
| 中文附件名上传后变 `_v2.pdf` | 用 ASCII 文件名 |
| 控制台中文/emoji 显示成 `?` | 只是 GBK 渲染问题，文件本身没坏；用 `ascii()` 码位打印判断 |

---

## 8. 可选：下载后入 Zotero

- **PDF 一律用 linked_file 本地链接**，路径写**反斜杠绝对路径**（正斜杠会被当成 URL scheme 剥掉盘符，双击打不开）。
- 写接口铁律：
  - body 必须是 **JSON 数组** `[{...}]`（单对象报 `400 Uploaded data must be a JSON array`）。
  - 认证用 **`Zotero-API-Key` header**；`apikey` query 参数无效（会被当匿名 403，容易误判"API 被封"）。
  - `creators` 每项必须带 `creatorType: "author"`，缺了整条**静默失败**。
  - 成功码常是 **200**，结果看响应 `successful` / `failed`，**HTTP 200 也可能是静默丢弃**。
  - 子条目（note/attachment）**禁带 `collections`**；附件单独 POST + 显式 `parentItem`。
  - 并入已有合集：`GET` 取 `version` → `POST /items` `[{key, version, collections:[...]}]`。`PUT /items` 一律 405。
  - 删除要带 `If-Unmodified-Since-Version`；连续删易 428，间隔 ≥3s。
- **Desktop 同步会把本地旧值顶回云端**：批量改完隔几分钟用 **Web API** 复查一次（本地 connector `127.0.0.1:23119` 查不到刚写的云端数据，这是正常的，别误判失败）。
- 中文作者名常见「名 姓」倒置：`lastName` 为 1–2 字且是 CJK 时，按「姓+名」重新拼。

---

## 附：文件清单

```
SKILL.md                      本文件
templates/ncbi_search.py      PubMed 检索（esearch + esummary + elink 查 PMC）
templates/dl_epmc.py          Europe PMC PDF 批量下载
templates/pmc_pow_dl.py       PMC 官网 POW 直连兜底
```

依赖：`pip install requests pypdf`；`curl.exe`（Windows 10+ 自带）。
凭据：`NCBI_API_KEY` 用环境变量传入，脚本不做任何硬编码。

## 完成判据

- 每篇目标文献都有「来源 / DOI / PMID 或 PMCID / 本地文件 / 文件大小」一行记录；
- 落盘 PDF 100% 通过 `%PDF` + >50KB 校验；
- 无重复 DOI；
- 中文文献元数据与详情页/PDF 首页一致（标题、年、期刊/学校）。