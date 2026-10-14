"""Repeatable local browser probe for public page loading.

Run with Selenium available, for example:
    uv run --with selenium python scripts/measure_public_pages.py http://127.0.0.1:5017

These are browser lab observations, not field Core Web Vitals or Lighthouse scores.
"""

import argparse
import json
import time
from statistics import median
from urllib.parse import urljoin

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options


OBSERVER = """
window.__pageProbe = {lcp: null, cls: 0, shifts: []};
new PerformanceObserver(list => {
  for (const e of list.getEntries()) {
    window.__pageProbe.lcp = {
      ms: e.startTime,
      tag: e.element?.tagName || null,
      id: e.element?.id || null,
      src: e.element?.currentSrc || e.url || null,
      text: (e.element?.textContent || '').trim().slice(0, 90)
    };
  }
}).observe({type: 'largest-contentful-paint', buffered: true});
new PerformanceObserver(list => {
  for (const e of list.getEntries()) {
    if (!e.hadRecentInput) {
      window.__pageProbe.cls += e.value;
      window.__pageProbe.shifts.push({ms: Math.round(e.startTime), value: e.value,
        sources: (e.sources || []).slice(0, 4).map(s => ({
          tag: s.node?.tagName || null, className: String(s.node?.className || '').slice(0, 70),
          text: (s.node?.textContent || '').trim().slice(0, 60),
          previous: s.previousRect, current: s.currentRect
        }))});
    }
  }
}).observe({type: 'layout-shift', buffered: true});
"""

MEASURE = """
const navigation = performance.getEntriesByType('navigation')[0];
return {
  readyState: document.readyState,
  lcp: window.__pageProbe?.lcp || null,
  cls: window.__pageProbe?.cls || 0,
  shifts: window.__pageProbe?.shifts || [],
  ttfbMs: navigation?.responseStart || null,
  viewportWidth: innerWidth,
  documentWidth: document.documentElement.scrollWidth,
  images: [...document.images].filter(i => i.currentSrc).map(i => ({
    name: i.currentSrc.split('/').pop(),
    width: i.naturalWidth,
    loading: i.loading,
    priority: i.fetchPriority
  })),
  transferredImageBytes: performance.getEntriesByType('resource')
    .filter(e => /\\.(png|jpe?g|webp)(\\?|$)/i.test(e.name))
    .reduce((sum, e) => sum + (e.transferSize || 0), 0),
  slowResources: performance.getEntriesByType('resource')
    .sort((a, b) => b.duration - a.duration).slice(0, 6)
    .map(e => ({name: e.name.split('/').slice(-2).join('/').slice(0, 100),
                durationMs: Math.round(e.duration)}))
};
"""


def run(origin, paths, profile, count, settle):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.page_load_strategy = "eager"
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": OBSERVER})
        driver.execute_cdp_cmd("Network.enable", {})
        driver.execute_cdp_cmd("Network.setCacheDisabled", {"cacheDisabled": True})
        if profile == "mobile":
            width, height, latency, download = 390, 844, 150, 200_000
        else:
            width, height, latency, download = 1365, 768, 40, 1_250_000
        driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
            "width": width, "height": height, "deviceScaleFactor": 1,
            "mobile": profile == "mobile",
        })
        driver.execute_cdp_cmd("Network.emulateNetworkConditions", {
            "offline": False, "latency": latency,
            "downloadThroughput": download, "uploadThroughput": 100_000,
        })
        observations = []
        for path in paths:
            for sample in range(1, count + 1):
                driver.execute_cdp_cmd("Network.clearBrowserCache", {})
                try:
                    driver.get(urljoin(origin.rstrip("/") + "/", path.lstrip("/")))
                except TimeoutException:
                    pass
                time.sleep(settle)
                result = driver.execute_script(MEASURE)
                observations.append({"path": path, "sample": sample, **result})
        summary = {}
        for path in paths:
            rows = [row for row in observations if row["path"] == path]
            summary[path] = {
                "lcpMsMedian": median(row["lcp"]["ms"] for row in rows if row["lcp"]),
                "clsMedian": median(row["cls"] for row in rows),
                "ttfbMsMedian": median(row["ttfbMs"] for row in rows),
                "lcpElements": [row["lcp"] for row in rows],
                "imageBytesMedian": median(row["transferredImageBytes"] for row in rows),
            }
        return {
            "origin": origin, "profile": profile, "runsPerPage": count,
            "conditions": {"width": width, "height": height, "latencyMs": latency,
                           "downloadBytesPerSecond": download, "cacheDisabled": True,
                           "settleSeconds": settle},
            "summary": summary, "observations": observations,
        }
    finally:
        driver.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("origin")
    parser.add_argument("--paths", nargs="+", default=["/", "/km/", "/bmi", "/km/bmi"])
    parser.add_argument("--profile", choices=["mobile", "desktop"], required=True)
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--settle", type=float, default=5)
    args = parser.parse_args()
    print(json.dumps(run(args.origin, args.paths, args.profile, args.runs, args.settle), ensure_ascii=True))
