import json
from pathlib import Path

from playwright.sync_api import sync_playwright


OUT_DIR = Path("artifacts/drug_checker")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def run():
    logs = []
    net = []
    reqs = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        page.on(
            "console",
            lambda msg: logs.append(
                {"type": msg.type, "text": msg.text, "location": msg.location}
            ),
        )

        def _resp(res):
            if "/check-interactions" in res.url:
                req = res.request
                body = None
                try:
                    body = req.post_data
                except Exception:
                    body = None
                net.append(
                    {
                        "url": res.url,
                        "status": res.status,
                        "method": req.method,
                        "request_body": body,
                    }
                )

        page.on("response", _resp)
        page.on(
            "request",
            lambda req: reqs.append(
                {
                    "url": req.url,
                    "method": req.method,
                    "post_data": req.post_data if "/check-interactions" in req.url else None,
                }
            )
            if "/check-interactions" in req.url
            else None,
        )

        page.goto("http://127.0.0.1:3000/frontend/index.html", wait_until="networkidle")
        page.fill("#login-email", "arogixai@gmail.com")
        page.fill("#login-password", "Arogix9345@")
        page.click("#login-btn")
        page.wait_for_selector("#app-container", timeout=15000)
        page.click("[data-action='nav-drug']")
        page.wait_for_selector("#screen-drug-checker.active", timeout=10000)

        page.fill("#drug-input", "Clotrimazole, Hydrocortisone, Lithium")
        page.screenshot(path=str(OUT_DIR / "01_drug_input.png"), full_page=True)
        page.click("#check-drug-btn")
        page.wait_for_selector("#drug-result-container:not(.hidden)", timeout=20000)
        page.wait_for_timeout(15000)
        # Wait longer if still pending
        if "Running interaction analysis..." in page.locator("#drug-result-container").inner_text():
            page.wait_for_timeout(30000)
        page.screenshot(path=str(OUT_DIR / "02_drug_result.png"), full_page=True)

        report = {
            "console_logs": logs,
            "requests": reqs,
            "network": net,
            "result_text": page.locator("#drug-result-container").inner_text(),
            "screenshots": [
                str(OUT_DIR / "01_drug_input.png"),
                str(OUT_DIR / "02_drug_result.png"),
            ],
        }
        (OUT_DIR / "e2e_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        browser.close()


if __name__ == "__main__":
    run()
