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
# Canonical column order in the Sold Permits Active Report
SOLD_PERMITS_COLUMNS = [
    "PROJECT_NO",
    "PERMIT_DESC",
    "OWNER_OCCUPANT",
    "Address",
    "PROJECT_DESC",
    "CURRENT_VALUATION",
    "PERMIT_TYPE",
]


def parse_active_report(html: str) -> list[dict]:
    """[Legacy] Parse from the ARstrings JS array. Kept for offline tests but the
    DOM-rendered path in scrape_via_dom() is the reliable production parser."""
    return []


def parse_from_cells(cells: list[str], records_count: int) -> list[dict]:
    """Build permit records from a flat list of rendered DOM cell strings.

    The Sold Permits Active Report flattens into a sequence that begins with
    chrome rows (search-results banner, date/valuation labels, report date,
    column-header section) and ends with N records × 7 column cells. We
    locate the first cell that looks like an 8-digit project number, then
    walk forward in chunks of 7.
    """
    cleaned = [c.strip() for c in cells if c and c.strip() and c.strip() != "\xa0"]
    n_cols = len(SOLD_PERMITS_COLUMNS)

    # Find first plausible project number (8-digit numeric string)
    pn_idx = next(
        (i for i, c in enumerate(cleaned) if c.isdigit() and len(c) == 8),
        None,
    )
    if pn_idx is None:
        return []

    data = cleaned[pn_idx:]
    rows: list[dict] = []
    for i in range(0, len(data), n_cols):
        chunk = data[i:i + n_cols]
        if len(chunk) != n_cols:
            break
        # Sanity check: the chunk's first cell should still be a project number
        if not (chunk[0].isdigit() and len(chunk[0]) == 8):
            break
        rows.append(dict(zip(SOLD_PERMITS_COLUMNS, chunk)))
        if len(rows) >= records_count:
            break
    return rows


async def scrape_via_dom(project_no: str) -> dict:
    """Lookup one project number and return parsed sub-permit rows.

    Architecture (HTTP+local-render hybrid):
      1. httpx POST → WFServlet returns the full Active Report HTML directly
         (~1.3 MB). No form interaction, no popup window, no auth token.
      2. Save HTML to a temp file and open it in Playwright via file://.
         The page's embedded JS renders the data into the ITableData0 table.
      3. Read cell text from the DOM and reuse parse_from_cells().

    This replaced the old form-click-and-wait-for-popup flow on 2026-05-24
    after the city site stopped opening popups in headless browsers (still
    works fine in headed Chrome — likely a popup-blocker heuristic).
    Bonus: ~3-5× faster per query than the popup flow because there's no
    network navigation in the Playwright step.

    Returns {"project_no": ..., "status": "hit"|"miss"|"error", "rows": [...]}.
    """
    import tempfile
    import os

    tmp_path = None
    try:
        # ---- Step 1: HTTP POST for the raw report ----
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
            "IBIMR_sub_action": "MR_USER_FEX",
        }
        headers = {
            "User-Agent": UA,
            "Referer": FORM_URL,
            "Origin": "https://cohtora.houstontx.gov",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            # GET the form first to set the NSC_ESNS cookie (some queries fail without it).
            await client.get(FORM_URL, headers={"User-Agent": UA})
            r = await client.post(REPORT_URL, data=body, headers=headers)
        html = r.text

        # Quick early exits without spinning up Chromium
        if not html or len(html) < 500:
            return {"project_no": project_no, "status": "error",
                    "error": f"short response: {len(html)}B", "rows": []}
        if "Maintenance" in html:
            return {"project_no": project_no, "status": "miss", "rows": []}
        if "Active Report" not in html:
            return {"project_no": project_no, "status": "miss", "rows": []}

        # ---- Step 2: Render locally via Playwright (file://) ----
        # Use a uniquely-named temp file per call so concurrent workers don't collide
        fd, tmp_path = tempfile.mkstemp(suffix=".html", prefix=f"sp_{project_no}_")
        with os.fdopen(fd, "w") as f:
            f.write(html)

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            ctx = await browser.new_context()
            page = await ctx.new_page()
            try:
                await page.goto(f"file://{tmp_path}",
                                wait_until="domcontentloaded", timeout=20_000)
                try:
                    await page.wait_for_selector("#ITableData0", timeout=15_000)
                except Exception:
                    await browser.close()
                    return {"project_no": project_no, "status": "miss", "rows": []}
                await page.wait_for_timeout(800)  # let AR finish painting

                meta_info = await page.evaluate("""
                    () => {
                        const m = document.querySelector('meta[name="ibi-report"]');
                        if (!m) return {records: 0, columns: 0};
                        const c = m.getAttribute('content') || '';
                        const r = /records=(\\d+),\\s*columns=(\\d+)/.exec(c);
                        return r ? {records: +r[1], columns: +r[2]} : {records: 0, columns: 0};
                    }
                """)
                cells = await page.evaluate("""
                    () => {
                        const t = document.getElementById('ITableData0');
                        if (!t) return [];
                        return Array.from(t.querySelectorAll('td, th'))
                            .map(c => (c.innerText || c.textContent || '').trim());
                    }
                """)
            finally:
                await browser.close()

        rows = parse_from_cells(cells, meta_info.get("records", 0))
        return {
            "project_no": project_no,
            "status": "hit" if rows else "miss",
            "records": len(rows),
            "rows": rows,
        }
    except Exception as e:
        return {"project_no": project_no, "status": "error", "error": str(e), "rows": []}
    finally:
        # Always clean up the temp file
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


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


def _scrape_date() -> "datetime.date":
    """Date this scrape was run. The Sold Permits report doesn't expose a
    per-permit issuance date — just a report-generation date at the top. So
    we use the current calendar date as a proxy. Imperfect (a permit in the
    backfill might actually have been issued days/weeks ago) but it gets
    rows into the year filter and time-series widgets, which is what matters
    for the demo. Daily cron runs will keep this approximately accurate."""
    import datetime
    return datetime.date.today()


def to_permit_row(scraped: dict) -> dict:
    """Map an Active Report row to our Permit model columns.

    Field mapping observed in WebFOCUS output:
      OWNER_OCCUPANT    → builder        (best proxy without a dedicated buyer field)
      Address           → address        (often includes ZIP at the end as "1234 MAIN ST 77079")
      PROJECT_DESC      → comments       (e.g. "SF RESIDENTIAL FOUNDATION ELEVATION 1-1-5-R3-B 2021 IRC")
      CURRENT_VALUATION → project_value  (parsed to float)
      PERMIT_DESC       → permit_type    (friendly name like "Building Pmt", "Electrical Pmt") — consistent with legacy eReport data
      PERMIT_TYPE       → permit_code    (short code like "PX", "13", "BPLB"; co-key with project_no for sub-permit uniqueness)
      PROJECT_NO        → project_no
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

    # Always provide a non-empty permit_code so the composite unique constraint
    # actually deduplicates. Fall back to 'UNK' if the cell was blank — better
    # than NULL (which Postgres treats as distinct from other NULLs).
    permit_code = (scraped.get("PERMIT_TYPE") or "").strip() or "UNK"

    return {
        "project_no": pn,
        "permit_code": permit_code,
        "permit_date": _scrape_date(),
        "permit_type": (scraped.get("PERMIT_DESC") or "").strip() or None,
        "address": address or None,
        "zip_code": zip_code,
        "comments": (scraped.get("PROJECT_DESC") or "").strip() or None,
        "builder": (scraped.get("OWNER_OCCUPANT") or "").strip() or None,
        "project_value": project_value,
        "source": "houston_sold_permits",
    }
