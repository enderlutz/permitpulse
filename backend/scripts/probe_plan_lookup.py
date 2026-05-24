"""Probe the City of Houston Plan Lookup tool to discover its underlying
REST API and what fields it returns for a project number.

Opens the Angular SPA in a real browser, captures all network requests,
and prints the ones that look like API calls + their response bodies.

Run from `backend/`:
    python -m scripts.probe_plan_lookup 26003886
"""
import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright


LOOKUP_URL = "https://pdinet.pd.houstontx.gov/cohilms/webs/Plan_LookUp.asp"


async def main(project_no: str):
    captured: list[dict] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context()
        page = await ctx.new_page()

        async def on_response(resp):
            url = resp.url
            host = urlparse(url).hostname or ""
            # Skip static asset noise (CSS, JS, fonts, telerik, etc.)
            if any(x in url for x in (".js", ".css", ".woff", ".png", ".svg", ".ico", "telerik.com", "fonts.")):
                return
            if "gov" not in host and "pdinet" not in host:
                return
            try:
                body = await resp.text()
            except Exception:
                body = "<binary>"
            captured.append({
                "method": resp.request.method,
                "url": url,
                "status": resp.status,
                "ct": resp.headers.get("content-type", ""),
                "body_preview": body[:1500],
                "body_size": len(body),
            })

        page.on("response", on_response)

        print(f"Loading lookup page...")
        await page.goto(LOOKUP_URL, wait_until="domcontentloaded", timeout=60_000)
        # Wait for the Angular app to mount and render
        await page.wait_for_selector("app-root", timeout=30_000, state="attached")
        # Wait for ANY input to appear inside app-root (Angular forms take time)
        for _ in range(20):
            input_count = await page.evaluate("() => document.querySelectorAll('input').length")
            if input_count > 0:
                print(f"Inputs appeared (n={input_count}) after polling")
                break
            await page.wait_for_timeout(1_000)
        await page.wait_for_timeout(2_000)

        # Print app-root inner HTML so we know what's actually rendered
        inner = await page.evaluate("() => document.querySelector('app-root')?.innerHTML || '(empty)'")
        print("=== app-root inner HTML (first 3000 chars) ===")
        print(inner[:3000])
        print("=== end inner HTML ===")
        print()

        # Enumerate every interactive element so we can see what's on the page
        all_inputs = await page.evaluate("""
            () => Array.from(document.querySelectorAll('input, button, select, textarea')).map(e => ({
                tag: e.tagName,
                type: e.type || null,
                id: e.id || null,
                name: e.name || null,
                placeholder: e.placeholder || null,
                ariaLabel: e.getAttribute('aria-label'),
                text: (e.innerText || e.value || '').slice(0, 50),
            }))
        """)
        print(f"Found {len(all_inputs)} interactive elements:")
        for el in all_inputs[:30]:
            print(f"  {el}")
        print()

        # Find the project-number-ish input
        target_input = None
        for sel in [
            "input[placeholder*='Project' i]",
            "input[placeholder*='number' i]",
            "input[aria-label*='Project' i]",
            "input[id*='project' i]",
            "input[name*='project' i]",
            "input[type='text']",
            "input[type='number']",
            "input",
        ]:
            try:
                if await page.locator(sel).count() > 0:
                    target_input = page.locator(sel).first
                    print(f"Using input selector: {sel}")
                    break
            except Exception:
                pass

        if target_input:
            await target_input.click()
            await target_input.fill(project_no)
            print(f"Filled {project_no} into the input")
            await page.wait_for_timeout(500)

            # Trigger search — try Enter key first, then any visible button
            await target_input.press("Enter")
            print("Pressed Enter")
            await page.wait_for_timeout(2_000)

            # Try clicking any search-y button
            for sel in [
                "button:has-text('Search')",
                "button:has-text('Lookup')",
                "button:has-text('Submit')",
                "button:has-text('Go')",
                "button[type='submit']",
                "[role='button']:has-text('Search')",
            ]:
                try:
                    btn = page.locator(sel).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click()
                        print(f"Clicked: {sel}")
                        break
                except Exception:
                    pass

            await page.wait_for_timeout(6_000)

        # Dump final DOM text content too
        text_content = await page.evaluate("() => document.body.innerText")
        print()
        print("=" * 80)
        print("FINAL VISIBLE TEXT (first 3000 chars):")
        print(text_content[:3000])
        print()

        await browser.close()

    print()
    print(f"Captured {len(captured)} API-ish responses:")
    print("=" * 80)
    for r in captured:
        print(f"\n[{r['status']}] {r['method']} {r['url']}")
        print(f"  Content-Type: {r['ct']}   Body size: {r['body_size']}")
        if r['ct'].startswith("application/json") or r['body_preview'].startswith("[") or r['body_preview'].startswith("{"):
            print(f"  --- JSON preview ---")
            print(f"  {r['body_preview']}")
        else:
            print(f"  --- HTML/text preview (first 500 chars) ---")
            print(f"  {r['body_preview'][:500]}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.probe_plan_lookup <project_no>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
