"""Scraper for the Houston Sold Permits Search WebFOCUS application.

The discovery: every search mode (ZIP, Buyer, Address, Date Range, etc.) returns
the literal error "This selection is under Maintenance" — except for Project
Number lookup, which works reliably and returns rich per-permit data with
owner name, address, valuation, project description, multi-permit breakdown.

Strategy: enumerate plausible 2026+ project numbers via PN lookup. Houston
project numbers follow the pattern YYDDDxxx where YY is the year and DDDxxx
is a per-year sequence. Active 2026 prefixes observed: 26001-26025ish; we
walk the live range from a configured floor upward, stopping when we hit a
long run of empty responses.

Authentication: the WebFOCUS server requires a session auth token + cookies
issued by the form page on first load. We harvest these once with Playwright,
then issue the actual report POSTs via httpx (4-5x faster than browser).
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from random import random
from typing import Optional

import httpx
from playwright.async_api import async_playwright


FORM_URL = "https://cohtora.houstontx.gov/approot/soldpermits/online_permit.htm"
REPORT_URL = "https://cohtora.houstontx.gov/ibi_apps/WFServlet.ibfs"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"


# ---------------------------- Session harvesting ----------------------------

@dataclass
class Session:
    token: str
    cookies: httpx.Cookies


async def harvest_session() -> Session:
    """Open the form, submit a dummy search, capture the auth token + cookies."""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=UA)
        page = await ctx.new_page()

        token_holder: dict[str, Optional[str]] = {"token": None}

        def on_request(req):
            if "WFServlet" in req.url and req.method == "POST" and req.post_data:
                m = re.search(r"IBIWF_SES_AUTH_TOKEN=([0-9a-f]+)", req.post_data)
                if m and not token_holder["token"]:
                    token_holder["token"] = m.group(1)

        page.on("request", on_request)

        await page.goto(FORM_URL, wait_until="domcontentloaded", timeout=60_000)
        await page.locator("input#SELTD_PN").wait_for(state="attached", timeout=60_000)
        await page.wait_for_timeout(1_500)
        await page.locator("input#SELTD_PN").check()
        await page.locator('input[name="SRH"]').fill("00000000")
        try:
            async with ctx.expect_event("page", timeout=30_000) as p_info:
                await page.locator("input#form1Submit").click()
            popup = await p_info.value
            await popup.wait_for_load_state("domcontentloaded", timeout=30_000)
        except Exception:
            pass

        playwright_cookies = await ctx.cookies()
        await browser.close()

        if not token_holder["token"]:
            raise RuntimeError("Failed to harvest session auth token from form")

        jar = httpx.Cookies()
        for c in playwright_cookies:
            jar.set(c["name"], c["value"], domain=c["domain"], path=c.get("path", "/"))
        return Session(token=token_holder["token"], cookies=jar)


# ---------------------------- Active Report parsing -------------------------

META_RE = re.compile(r'<meta[^>]+name="ibi-report"[^>]+content="[^"]*records=(\d+),\s*columns=(\d+)', re.I)
# Known canonical header tokens that show up in the headers section. The
# last column varies (Plan Review Fee / Electrical Pmt / etc.), so we use
# the FIXED prefix to find the headers block, then count len(headers).
FIXED_HEADERS = ["PERMIT_DESC", "OWNER_OCCUPANT", "Address", "PROJECT_DESC", "CURRENT_VALUATION", "PERMIT_TYPE"]


def parse_active_report(html: str) -> list[dict]:
    """Pull permit records from the ARstrings JavaScript array.

    Anchors on the ibi-report meta tag (records=N, columns=N) and the fixed
    header tokens to slice the data block accurately.
    """
    meta = META_RE.search(html)
    if not meta:
        return []
    records_count, columns_count = int(meta.group(1)), int(meta.group(2))
    if records_count == 0:
        return []

    arrays = re.findall(r"ARstrings\s*=\s*\[(.*?)\];", html, flags=re.S)
    for raw in arrays:
        toks = re.findall(r"'((?:[^'\\]|\\.)*)'", raw)
        if not toks:
            continue
        # Find the fixed-header window
        try:
            start = next(i for i in range(len(toks) - len(FIXED_HEADERS))
                         if toks[i:i + len(FIXED_HEADERS)] == FIXED_HEADERS)
        except StopIteration:
            continue
        # Walk forward to capture any extra header tokens (variable last column)
        # until we have exactly `columns_count` headers
        # PROJECT_NO is one before PERMIT_DESC; include if present
        first_header_idx = start
        if start > 0 and toks[start - 1] == "PROJECT_NO":
            first_header_idx = start - 1
        headers = toks[first_header_idx:first_header_idx + columns_count]
        if len(headers) != columns_count:
            continue
        data_start = first_header_idx + columns_count
        expected_data_len = columns_count * records_count
        data_tokens = toks[data_start:data_start + expected_data_len]
        if len(data_tokens) < expected_data_len:
            # data may have run out — best effort with what we have
            usable_records = len(data_tokens) // columns_count
            data_tokens = data_tokens[:usable_records * columns_count]
        rows = []
        for r in range(0, len(data_tokens), columns_count):
            chunk = data_tokens[r:r + columns_count]
            rows.append(dict(zip(headers, chunk)))
        return rows
    return []


# ---------------------------- HTTP report fetch -----------------------------

def lookup_project(client: httpx.Client, session: Session, project_no: str) -> dict:
    """Query a single project number. Returns a dict with status + parsed rows."""
    body = {
        "IBIAPP_app": "soldpermits",
        "IBIF_ex": "online_per_se",
        "IBIC_server": "EDASERVE",
        "VALMN": " ",
        "VALMX": " ",
        "SRH": project_no,
        "SELTD": "PN",
        "PTYPE": "11",
        "ERRTITLE": " ",
        "IBIMR_Random": str(random()),
        "IBIWF_SES_AUTH_TOKEN": session.token,
        "IBIMR_sub_action": "MR_USER_FEX",
    }
    headers = {
        "User-Agent": UA,
        "Referer": FORM_URL,
        "Origin": "https://cohtora.houstontx.gov",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    r = client.post(REPORT_URL, data=body, headers=headers, timeout=30, cookies=session.cookies)
    html = r.text
    if "Active Report" in html:
        rows = parse_active_report(html)
        return {"project_no": project_no, "status": "hit", "records": len(rows), "rows": rows}
    if "Maintenance" in html or "no record" in html.lower():
        return {"project_no": project_no, "status": "miss", "rows": []}
    return {"project_no": project_no, "status": "unknown", "size": len(html), "rows": []}


async def lookup_project_async(client: httpx.AsyncClient, session: Session, project_no: str) -> dict:
    body = {
        "IBIAPP_app": "soldpermits",
        "IBIF_ex": "online_per_se",
        "IBIC_server": "EDASERVE",
        "VALMN": " ",
        "VALMX": " ",
        "SRH": project_no,
        "SELTD": "PN",
        "PTYPE": "11",
        "ERRTITLE": " ",
        "IBIMR_Random": str(random()),
        "IBIWF_SES_AUTH_TOKEN": session.token,
        "IBIMR_sub_action": "MR_USER_FEX",
    }
    headers = {
        "User-Agent": UA,
        "Referer": FORM_URL,
        "Origin": "https://cohtora.houstontx.gov",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    try:
        r = await client.post(REPORT_URL, data=body, headers=headers, timeout=30)
    except httpx.HTTPError as e:
        return {"project_no": project_no, "status": "error", "error": str(e), "rows": []}
    html = r.text
    if "Active Report" in html:
        rows = parse_active_report(html)
        return {"project_no": project_no, "status": "hit", "records": len(rows), "rows": rows}
    if "Maintenance" in html or "no record" in html.lower():
        return {"project_no": project_no, "status": "miss", "rows": []}
    return {"project_no": project_no, "status": "unknown", "size": len(html), "rows": []}


# ---------------------------- Normalization ---------------------------------

VALUATION_RE = re.compile(r"[\d.]+")

def to_permit_row(scraped: dict) -> dict:
    """Map an Active Report row to our Permit model columns.

    Field mapping observed in WebFOCUS output:
      OWNER_OCCUPANT   → builder        (best proxy without the dedicated buyer field)
      Address          → address        (often includes ZIP at the end as "1234 MAIN ST 77079")
      PROJECT_DESC     → comments       (e.g. "SF RESIDENTIAL FOUNDATION ELEVATION 1-1-5-R3-B 2021 IRC")
      CURRENT_VALUATION → project_value (parsed to float)
      PERMIT_TYPE      → permit_type
      PROJECT_NO       → project_no
    """
    pn = (scraped.get("PROJECT_NO") or "").strip()
    addr_full = (scraped.get("Address") or "").strip()
    zip_match = re.search(r"\b(\d{5})\b\s*$", addr_full)
    zip_code = zip_match.group(1) if zip_match else None
    address = re.sub(r"\s*\d{5}\s*$", "", addr_full).strip() if zip_match else addr_full

    valuation_raw = (scraped.get("CURRENT_VALUATION") or "").strip()
    val_match = VALUATION_RE.search(valuation_raw)
    try:
        project_value = float(val_match.group(0)) if val_match else None
    except ValueError:
        project_value = None

    return {
        "project_no": pn,
        "permit_type": (scraped.get("PERMIT_TYPE") or "").strip() or None,
        "address": address or None,
        "zip_code": zip_code,
        "comments": (scraped.get("PROJECT_DESC") or "").strip() or None,
        "builder": (scraped.get("OWNER_OCCUPANT") or "").strip() or None,
        "project_value": project_value,
        "source": "houston_sold_permits",
    }
