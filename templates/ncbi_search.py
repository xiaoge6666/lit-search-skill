# -*- coding: utf-8 -*-
"""NCBI 检索模板：eutils esearch + esummary + elink 查 PMC。

凭据：从环境变量 NCBI_API_KEY 读取（不硬编码任何 key）。
无 key 也能跑，但限速 3 次/秒；有 key 是 10 次/秒。
用法：改 TERMS 里的检索式，直接 python ncbi_search.py
"""
import os
import sys
import io
import time

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
API_KEY = os.environ.get("NCBI_API_KEY", "").strip()
# 需要代理时设 LIT_PROXY=http://127.0.0.1:7897；不设则直连（NCBI 直连通常可用）
_PROXY = os.environ.get("LIT_PROXY", "").strip()
PROXIES = {"http": _PROXY, "https": _PROXY} if _PROXY else None
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) literature-search/1.0"

# 修改点：检索式（结构化写法命中率最高）
TERMS = [
    ('"TARGET_GENE"[Title] AND (fung*[Title/Abstract] OR yeast*[Title/Abstract]'
     ' OR Fusarium[Title/Abstract] OR Candida[Title/Abstract])', "target-gene+fungi"),
    ('"TARGET_TOPIC"[Title/Abstract] AND 2020:2026[dp]', "topic-2020-2026"),
]


def call(url, params):
    """直连优先，失败再走代理；每路最多重试 2 次。"""
    if API_KEY:
        params = dict(params, api_key=API_KEY)
    headers = {"User-Agent": UA}
    session = requests.Session()
    session.trust_env = False  # 🔴 必须：否则系统代理会篡改请求头
    last = None
    for proxies in ((PROXIES, None) if PROXIES else (None,)):
        for _ in range(2):
            try:
                return session.get(url, params=params, proxies=proxies,
                                   headers=headers, timeout=45)
            except Exception as exc:  # noqa: BLE001
                last = exc
                time.sleep(1.5)
    raise last


def esearch(term, n=25):
    r = call(BASE + "esearch.fcgi",
             {"db": "pubmed", "term": term, "retmax": n, "retmode": "json"})
    return r.json()["esearchresult"].get("idlist", [])


def esummary(pmids):
    out = {}
    for i in range(0, len(pmids), 50):
        chunk = pmids[i:i + 50]
        r = call(BASE + "esummary.fcgi",
                 {"db": "pubmed", "id": ",".join(chunk), "retmode": "json"})
        for key, val in r.json()["result"].items():
            if key != "uids":
                out[key] = val
        time.sleep(0.4)
    return out


def elink_pmc(pmid):
    r = call(BASE + "elink.fcgi",
             {"dbfrom": "pubmed", "db": "pmc", "id": pmid, "retmode": "json"})
    try:
        for linkset in r.json()["linksets"]:
            for db in linkset.get("linksetdbs", []):
                if db["dbto"] == "pmc":
                    return db["links"][0]
    except Exception:  # noqa: BLE001
        pass
    return None


def efetch_doi(pmid):
    """🔴 DOI 只从 PubmedData/ArticleIdList 取。
    用 iter('ArticleId') 会抓到参考文献列表里的 DOI（实测错率接近 50%）。"""
    import xml.etree.ElementTree as ET
    r = call(BASE + "efetch.fcgi",
             {"db": "pubmed", "id": pmid, "retmode": "xml"})
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError:
        return None
    for node in root.findall(".//PubmedData/ArticleIdList/ArticleId"):
        if node.get("IdType") == "doi":
            return (node.text or "").strip()
    return None


if __name__ == "__main__":
    for term, label in TERMS:
        print(f"\n===== {label} =====")
        ids = esearch(term)
        print("hits:", len(ids))
        sums = esummary(ids[:12])
        for pid in ids[:12]:
            s = sums.get(pid)
            if not s:
                continue
            print(f"PMID {pid} | {s.get('pubdate', '')} | PMC={elink_pmc(pid)}")
            print(f"   {s.get('title', '')[:110]}")
        time.sleep(1)