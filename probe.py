#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GitHub 러너 등 해외 IP에서 진학어플라이 경쟁률 페이지가 열리는지 헤더 변형별로 탐침한다."""
import urllib.request
import urllib.error

URL = "https://addon.jinhakapply.com/RatioV1/RatioH/Ratio11400471.html"
UA_CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
VARIANTS = {
    "plain": {},
    "ua": {"User-Agent": UA_CHROME},
    "ua+lang": {"User-Agent": UA_CHROME, "Accept-Language": "ko-KR,ko;q=0.9"},
    "ua+lang+ref": {"User-Agent": UA_CHROME, "Accept-Language": "ko-KR,ko;q=0.9", "Referer": "https://www.jinhakapply.com/"},
    "browser-full": {"User-Agent": UA_CHROME, "Accept-Language": "ko-KR,ko;q=0.9", "Referer": "https://www.jinhakapply.com/",
                     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                     "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Site": "same-site", "Upgrade-Insecure-Requests": "1"},
    "googlebot": {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"},
    "http": {"User-Agent": UA_CHROME, "_url": URL.replace("https://", "http://")},
}
for name, h in VARIANTS.items():
    h = dict(h)
    url = h.pop("_url", URL)
    try:
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            print("%-14s %s %dB server=%s" % (name, r.status, len(body), r.headers.get("Server")))
    except urllib.error.HTTPError as e:
        print("%-14s HTTP %s server=%s cf=%s" % (name, e.code, e.headers.get("Server"), e.headers.get("cf-mitigated") or e.headers.get("CF-RAY")))
    except Exception as e:
        print("%-14s ERR %s" % (name, e))
