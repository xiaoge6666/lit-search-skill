# -*- coding: utf-8 -*-
"""PMC 官网 POW 直连下载模板（Europe PMC render / fullTextPDF 404 时的兜底）。

原理：
  curl.exe 直连（默认不走系统代理）→ 若返回 POW_CHALLENGE 页面，
  解算 sha256 前缀 nonce → 带 cookie `cloudpmc-viewer-pow=<challenge>,<nonce>` 重试。
  实测 Nature / MMBR / mBio 类文章全通。

用法：改 jobs 列表 [(PMCID, 输出文件名), ...]；python pmc_pow_dl.py
依赖：curl.exe（Windows 10/11 自带）、Python 3.8+
"""
import hashlib
import io
import os
import re
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUT_DIR = os.environ.get("LIT_OUT", os.path.join(os.path.expanduser("~"), "Downloads", "literature"))
os.makedirs(OUT_DIR, exist_ok=True)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
MIN_SIZE = 50 * 1024


def solve_pow(challenge, difficulty=4):
    """暴力找 nonce，使 sha256(challenge + nonce) 以 difficulty 个 0 开头。"""
    target = "0" * difficulty
    nonce = 0
    while True:
        digest = hashlib.sha256(f"{challenge}{nonce}".encode()).hexdigest()
        if digest.startswith(target):
            return nonce, digest
        nonce += 1


def curl_get(url, cookie=None):
    cmd = ["curl.exe", "-s", "-L", "--connect-timeout", "10", "--max-time", "90",
           "-A", UA, "-w", "\n%{http_code}"]
    if cookie:
        cmd += ["-b", cookie]
    cmd.append(url)
    result = subprocess.run(cmd, capture_output=True, timeout=120)
    out = result.stdout
    lines = out.split(b"\n")
    status = int(lines[-1].strip()) if lines and lines[-1].strip().isdigit() else 0
    content = b"\n".join(lines[:-1])
    return status, content


def download_pmc_pdf(pmcid, outfile):
    if os.path.exists(outfile) and os.path.getsize(outfile) > MIN_SIZE:
        return f"already: {os.path.getsize(outfile)} B"

    url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/pdf/main.pdf"
    status, content = curl_get(url)
    if content[:4] == b"%PDF" and len(content) > MIN_SIZE:
        with open(outfile, "wb") as fh:
            fh.write(content)
        return f"OK direct ({len(content)} B)"

    text = content.decode("utf-8", errors="replace")
    m = re.search(r'POW_CHALLENGE\s*=\s*"([^"]+)"', text)
    if not m:
        return f"no POW, status={status}: {text[:120]}"

    challenge = m.group(1)
    dm = re.search(r'POW_DIFFICULTY\s*=\s*"(\d+)"', text)
    difficulty = int(dm.group(1)) if dm else 4
    nonce, _ = solve_pow(challenge, difficulty)

    cookie = f"cloudpmc-viewer-pow={challenge},{nonce}; Domain=.ncbi.nlm.nih.gov; Path=/"
    status, content = curl_get(url, cookie=cookie)
    if content[:4] == b"%PDF" and len(content) > MIN_SIZE:
        with open(outfile, "wb") as fh:
            fh.write(content)
        return f"OK POW ({len(content)} B)"
    return f"FAIL status={status} len={len(content)}"


if __name__ == "__main__":
    jobs = [
        ("PMCXXXXXXX", "NCBI_Author-Year_short-title.pdf"),
    ]
    for pmcid, name in jobs:
        print(f"{pmcid} ->", end=" ")
        try:
            print(download_pmc_pdf(pmcid, os.path.join(OUT_DIR, name)))
        except Exception as exc:  # noqa: BLE001
            print(f"ERR {exc}")