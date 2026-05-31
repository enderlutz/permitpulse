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
# Drill-down endpoint discovered 2026-05-28 — exposes the true per-project
# issuance Date (and FCC Group + Buyer) that the search-results page hides.
# Same WFServlet, different IBIF_ex value. See fetch_project_detail() below.
DETAIL_URL = REPORT_URL
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


# ---------------------------- Project Detail (drill-down) -------------------
#
# The Sold Permits search-results page exposes 7 columns and NO issuance date.
# However each row's PROJECT_NO is a drill-down link to IBIF_ex=sold_permit_d,
# which returns a richer "Project Details" page including the real per-project
# permit Date, FCC Group, and Buyer. PT (permit_code) is required; passing a
# PT that doesn't belong to that project yields "no output".
#
# Date is per-sub-permit, NOT per-project. Each sub-permit (Building, Electrical,
# Plumbing, etc.) gets issued on its own day — plan review (PX) typically months
# before the actual trade permits. So we drill once per (PN, PT) to capture each
# sub-permit's true issuance date. Verified 2026-05-28 on PN=26017768: PX=2026-03-03,
# Building=2026-03-04, Electrical=2026-05-14, Plumbing=2026-05-16, HVAC=2026-05-15.

_DATE_RE  = re.compile(r"Date\s*:\s*(\d{4})/(\d{1,2})/(\d{1,2})")
_USE_RE   = re.compile(r"USE\s*:\s*(.*?)\s*Owner/Occupant", re.S)
_OWNER_RE = re.compile(r"Owner/Occupant\s*:\s*(.*?)\s*Job Address", re.S)
_ADDR_RE  = re.compile(r"Job Address\s*:\s*(.*?)\s*Valuation", re.S)
_VAL_RE   = re.compile(r"Valuation\s*:\s*\$?\s*([\d,]+(?:\.\d+)?)")
_FCC_RE   = re.compile(r"FCC Group\s*:\s*(.*?)\s*Buyer", re.S)
_BUYER_RE = re.compile(r"Buyer\s*:\s*(.*?)\s*Address\s*:", re.S)


def _parse_detail_html(html: str) -> Optional[dict]:
    """Strip HTML and pull the labeled Project Details fields. Returns None
    when the response isn't a Project Details page (e.g. wrong PT, error)."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    if "Date :" not in text:
        return None
    d = _DATE_RE.search(text)
    permit_date = None
    if d:
        import datetime
        try:
            permit_date = datetime.date(int(d.group(1)), int(d.group(2)), int(d.group(3)))
        except ValueError:
            permit_date = None

    def _grab(rx):
        m = rx.search(text)
        if not m:
            return None
        v = m.group(1).strip()
        return v or None

    val_raw = _grab(_VAL_RE)
    project_value = None
    if val_raw:
        try:
            project_value = float(val_raw.replace(",", ""))
        except ValueError:
            project_value = None

    return {
        "permit_date": permit_date,
        "use_description": _grab(_USE_RE),
        "owner": _grab(_OWNER_RE),
        "job_address": _grab(_ADDR_RE),
        "project_value": project_value,
        "fcc_group": _grab(_FCC_RE),
        "buyer": _grab(_BUYER_RE),
    }


async def fetch_project_detail(client: httpx.AsyncClient, project_no: str, permit_type: str) -> Optional[dict]:
    """Hit the sold_permit_d drill-down and return the parsed Project Details
    dict (with `permit_date`, `owner`, `project_value`, `fcc_group`, etc.).

    Returns None if the (PN, PT) pair doesn't resolve — caller can try a
    different sub-permit code. Stateless GET; no session token needed."""
    params = {
        "IBIF_webapp": "/ibi_apps",
        "IBIC_server": "EDASERVE",
        "IBIWF_msgviewer": "OFF",
        "IBIAPP_app": "soldpermits",
        "IBIF_ex": "sold_permit_d",
        "CLICKED_ON": "",
        "PN": project_no,
        "PT": permit_type,
    }
    try:
        r = await client.get(DETAIL_URL, params=params, headers={"User-Agent": UA}, timeout=20)
    except httpx.HTTPError:
        return None
    if r.status_code != 200 or not r.text:
        return None
    return _parse_detail_html(r.text)


# Common PT codes ordered roughly by hit frequency on Houston residential builds.
# Used by enrichment paths where we don't already know a valid sub-permit code
# (e.g. eReport rows that carry permit_code='LEGACY' from a pre-migration insert).
COMMON_PT_CANDIDATES = ["BU", "13", "11", "12", "14", "PX", "CC", "BX", "GI", "CO", "FF", "WK", "FG"]


async def fetch_project_detail_any_pt(
    client: httpx.AsyncClient,
    project_no: str,
    pt_hints: Optional[list[str]] = None,
) -> Optional[dict]:
    """Try a list of candidate PTs until the drill-down returns Project Details.
    Use pt_hints when we already know one valid sub-permit code; fall back to
    COMMON_PT_CANDIDATES otherwise. ~5-7 attempts worst-case but most hit on 1-2."""
    seen: set[str] = set()
    sequence: list[str] = []
    for pt in (pt_hints or []):
        if pt and pt not in seen and pt not in ("LEGACY", "UNK"):
            sequence.append(pt); seen.add(pt)
    for pt in COMMON_PT_CANDIDATES:
        if pt not in seen:
            sequence.append(pt); seen.add(pt)
    for pt in sequence:
        result = await fetch_project_detail(client, project_no, pt)
        if result and result.get("permit_date"):
            return result
    return None


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

        # Enrich each sub-permit row with its own Date / Valuation / FCC Group /
        # Buyer via the drill-down detail report. The search-results page exposes
        # NO issuance date — only the detail page does, and dates vary by
        # sub-permit type (PX is typically months before the actual trade permits).
        # Drilling per (PN, PT) gives per-sub-permit accuracy.
        details_by_pt: dict[str, dict] = {}
        if rows:
            pts = [r.get("PERMIT_TYPE", "").strip() for r in rows if r.get("PERMIT_TYPE")]
            unique_pts = list({pt for pt in pts if pt})
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as detail_client:
                detail_results = await asyncio.gather(
                    *[fetch_project_detail(detail_client, project_no, pt) for pt in unique_pts],
                    return_exceptions=True,
                )
            for pt, d in zip(unique_pts, detail_results):
                if isinstance(d, dict) and d.get("permit_date"):
                    details_by_pt[pt] = d

        return {
            "project_no": project_no,
            "status": "hit" if rows else "miss",
            "records": len(rows),
            "rows": rows,
            "details_by_pt": details_by_pt,
        }
    except Exception as e:
        return {"project_no": project_no, "status": "error", "error": str(e), "rows": [], "details_by_pt": {}}
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
    """Fallback only — used when the drill-down detail page failed to return
    a valid Date. The Project Details page is the authoritative source for
    issuance date; this just keeps rows out of NULL-date land so they still
    show up in widgets while we wait for a retry. Prior behavior used today()
    unconditionally and produced 36k mis-dated rows in May 2026, all of which
    were actually issued anywhere from Jan 2025 through May 2026."""
    import datetime
    return datetime.date.today()


def to_permit_row(scraped: dict, detail: Optional[dict] = None) -> dict:
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

    # Prefer drill-down detail for date + valuation when available. The search
    # results page never exposes the real issuance date, and its CURRENT_VALUATION
    # is often "0" for projects whose valuation lives only in the detail.
    permit_date = detail["permit_date"] if detail and detail.get("permit_date") else _scrape_date()
    if detail and detail.get("project_value") is not None:
        project_value = detail["project_value"]

    from schemas import classify_permit_nature
    permit_type = (scraped.get("PERMIT_DESC") or "").strip() or None
    comments = (scraped.get("PROJECT_DESC") or "").strip() or None
    return {
        "project_no": pn,
        "permit_code": permit_code,
        "permit_date": permit_date,
        "permit_type": permit_type,
        "permit_nature": classify_permit_nature(permit_type, comments),
        "address": address or None,
        "zip_code": zip_code,
        "comments": comments,
        "builder": (scraped.get("OWNER_OCCUPANT") or "").strip() or None,
        "project_value": project_value,
        "source": "houston_sold_permits",
    }
