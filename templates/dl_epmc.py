# -*- coding: utf-8 -*-
"""Europe PMC PDF 下载模板：用 ?pdf=render 端点批量取 Open Access 全文。

用法：
  1. 改 papers 列表 [(PMCID, 输出文件名), ...]
  2. python dl_epmc.py
  3. 仍然 404 的 → 切 templates/pmc_pow_dl.py（PMC 官网 POW 直连）

校验：content[:4] == b"%PDF" 且 > 50KB，否则视为失败（多半拿到的是登录页/HTML）。
"""
import io
import os
import sys
import time

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# PDF 落盘目录（默认 ~/Downloads/literature，可改）
OUT_DIR = os.environ.get("LIT_OUT", os.path.join(os.path.expanduser("~"), "Downloads", "literature"))
os.makedirs(OUT_DIR, exist_ok=True)

_PROXY = os.environ.get("LIT_PROXY", "").strip()
PROXIES = {"http": _PROXY, "https": _PROXY} if _PROXY else None
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
MIN_SIZE = 50 * 1024

papers = [
    ("PMCXXXXXXX", "NCBI_Author-Year_short-title.pdf"),
]

session = requests.Session()
session.trust_env = False  # 🔴 必须：绕过系统代理，避免请求头被改写

for pmcid, out in papers:
    fpath = os.path.join(OUT_DIR, out)
    if os.path.exists(fpath) and os.path.getsize(fpath) > MIN_SIZE:
        print(pmcid, "exists", os.path.getsize(fpath), "B")
        continue

    url = f"https://europepmc.org/articles/{pmcid}?pdf=render"
    done = False
    for proxies in ((PROXIES, None) if PROXIES else (None,)):
        tag = "proxy" if proxies else "direct"
        try:
            r = session.get(url, proxies=proxies, timeout=120, allow_redirects=True,
                            headers={"User-Agent": UA})
            ok = (r.status_code == 200 and r.content[:4] == b"%PDF"
                  and len(r.content) > MIN_SIZE)
            if ok:
                with open(fpath, "wb") as fh:
                    fh.write(r.content)
                print(pmcid, "OK", len(r.content), "B via", tag)
                done = True
                break
            print(pmcid, "try", tag, "status", r.status_code, "len", len(r.content))
        except Exception as exc:  # noqa: BLE001
            print(pmcid, "try", tag, "ERR", str(exc)[:80])
        time.sleep(1.5)

    if not done:
        print(pmcid, "FAILED ALL -> 切 templates/pmc_pow_dl.py（PMC 官网 POW 直连）")