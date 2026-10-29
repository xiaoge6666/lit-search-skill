# lit-search-skill — 知网 + PubMed 文献检索与全文下载 Agent Skill

一个面向 AI Agent（OpenClaw / Claude Skills 等）的**文献检索 SOP**：中文文献走知网，英文文献走 PubMed/NCBI，全文按三级通道兜底下载。

不含任何个人账号、密钥或本机路径 —— 拿到就能直接用。

## 这个技能解决什么

搜文献本身不难，难的是这些坑：

- 知网详情页 URL 直接打开必跳**文字点选验证码**，iframe 里的，自动化过不去
- PubMed 解析 DOI 时会**抓到参考文献列表里的 DOI**（实测错率接近 50%）
- PMC 全文下载遇到 `POW_CHALLENGE` 就卡死
- Wiley / ASM / T&F / ScienceDirect 全 Cloudflare 403，白试很久
- 429 限速后越重试封得越久

这份 SOP 把每条坑的**正确做法**都写死了，Agent 照着跑就行。

## 目录

```
SKILL.md                          技能主体（标准 front matter，丢进 agent 的 skills 目录即可）
lit-search-SOP-cnki-pubmed.md      单文件版：正文 + 三个脚本全文内联，方便直接贴给别人的 agent
templates/
  ncbi_search.py                  PubMed 检索：esearch + esummary + elink 查 PMC + 正确取 DOI
  dl_epmc.py                      Europe PMC 全文下载（?pdf=render）
  pmc_pow_dl.py                   PMC 官网 POW 直连兜底
```

## 怎么用

### 方式 A：作为 Agent Skill 安装

把整个目录放进 agent 的 skills 目录，例如 OpenClaw：

```bash
git clone https://github.com/xiaoge6666/lit-search-skill.git ~/.openclaw/skills/lit-search-skill
```

之后对 agent 说「帮我找 X 主题的文献，知网和 PubMed 都要」，它就会读到 `SKILL.md` 按流程执行。

### 方式 B：单文件分享

只要一个 md 的话，用 `lit-search-SOP-cnki-pubmed.md`——正文和脚本都在里面，直接丢对方文档库或聊天窗口即可。

### 方式 C：自己手动跑脚本

```bash
pip install requests pypdf
python templates/ncbi_search.py     # 改文件里的 TERMS 检索式
python templates/dl_epmc.py         # 改 papers 列表
python templates/pmc_pow_dl.py      # 改 jobs 列表
```

## 依赖与凭据

| 项 | 说明 |
|---|---|
| Python | 3.8+ |
| `pip install requests pypdf` | 必需 |
| `curl.exe` | Windows 10/11 自带；POW 兜底要用它 |
| `NCBI_API_KEY` | **可选**。环境变量传入。不填 3 次/秒，填了 10 次/秒。申请：<https://ncbi.nlm.nih.gov/account/settings> |
| `LIT_PROXY` | **可选**。如 `http://127.0.0.1:7897`。不设则直连（NCBI 直连通常可用） |
| `LIT_OUT` | **可选**。PDF 落盘目录，默认 `~/Downloads/literature` |

脚本一律 `session.trust_env = False` 强制直连——本机开着系统代理时，代理会篡改请求头导致 401 或连接重置。

## 核心内容速览

1. **三条铁律**：知网只走首页搜索框 / DOI 只从 `PubmedData/ArticleIdList` 取 / 429 就停手等冷却
2. **知网**：机构 IP 自动登录 → 首页短词搜 → 点标题进详情 → PDF下载 → NoteExpress 导出补元数据
3. **PubMed**：eutils 四端点、速率限制、结构化检索式
4. **全文四级兜底**：Europe PMC render → EBI fullTextPDF → PMC POW 解算 → PLOS 直链
5. **Scholar cookie 法**：headless 会被 sorry 页拦，用 NID cookie
6. **限速/去重/ASCII 命名**
7. **七步完整流程**
8. **12 条踩坑速查表**
9. 可选：入库 Zotero 的接口铁律

## 范围说明

- 本技能**只做检索与下载**，不涉及任何绕过付费墙的手段：知网依赖**你自己的机构 IP 授权**，PubMed 只取 Open Access 全文。
- 请遵守各数据库的使用条款与所在机构的订阅协议。
- 下载频率控制是硬要求（≤5 篇/批，间隔 ≥1s），既是礼貌也是避免被封。

## License

MIT