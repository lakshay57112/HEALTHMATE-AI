"""End-to-end browser journeys (Playwright + Chrome). Saves screenshots to e2e/screenshots/ (or $SHOTS).

    python e2e/journeys.py            # needs backend on :8000 and frontend on :3000
"""
import os
import re
import sys
import time
import uuid
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get("BASE_URL", "http://127.0.0.1:3000")
SHOTS = Path(os.environ.get("SHOTS", Path(__file__).parent / "screenshots"))
SHOTS.mkdir(parents=True, exist_ok=True)
CHROME = os.environ.get("CHROME_PATH") or ("/usr/bin/google-chrome" if Path("/usr/bin/google-chrome").exists() else None)
results = []


def step(name):
    def deco(fn):
        def run(*a, **k):
            t0 = time.time()
            try:
                fn(*a, **k)
                results.append((name, "PASS", round(time.time() - t0, 1), ""))
            except Exception as e:  # noqa: BLE001
                results.append((name, "FAIL", round(time.time() - t0, 1), str(e).splitlines()[0][:160]))
        return run
    return deco


def shot(page, name, full=True):
    page.wait_for_timeout(800)
    page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=full)


@step("landing page")
def landing(page):
    page.goto(BASE + "/")
    expect(page.get_by_text("One intelligent companion.")).to_be_visible()
    shot(page, "01_landing", full=False)


@step("register + onboarding")
def register(page):
    email = f"asha.{uuid.uuid4().hex[:6]}@example.com"
    page.goto(BASE + "/register")
    page.get_by_label("Full name").fill("Asha Verma")
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password").fill("supersecret1")
    page.get_by_role("checkbox").click()
    shot(page, "02_register", full=False)
    page.get_by_role("button", name="Create account").click()
    page.wait_for_url("**/onboarding")
    page.get_by_label("Date of birth").fill("1956-04-12")
    page.get_by_role("button", name="Continue").click()
    page.get_by_placeholder("Type and press Enter").fill("Type 2 diabetes")
    page.keyboard.press("Enter")
    page.get_by_role("button", name="+ Hypertension").click()
    shot(page, "03_onboarding_health", full=False)
    page.get_by_role("button", name="Continue").click()
    page.get_by_role("button", name="Continue").click()
    page.get_by_role("button", name="Continue").click()
    page.get_by_role("checkbox").click()
    page.get_by_role("button", name="Finish").click()
    page.wait_for_url("**/app/documents/new")
    shot(page, "04_upload_page", full=False)


@step("prescription: upload → verify → schedule")
def prescription(page):
    page.goto(BASE + "/app/medicines/upload")
    page.get_by_role("button", name=re.compile("^Prescription")).first.click()
    page.wait_for_url(re.compile(r".*/app/documents/[0-9a-f-]+$"))
    expect(page.get_by_text("Is this information correct?")).to_be_visible(timeout=30000)
    shot(page, "05_prescription_verify")
    # The weekly vitamin D can't be scheduled automatically → untick it
    page.get_by_label("Include Uprise D3").click()
    page.get_by_text("I have checked this information").click()
    page.get_by_role("button", name="Confirm and save").click()
    page.wait_for_url("**/app/medicines/schedule", timeout=20000)
    shot(page, "06_medicine_schedule")
    page.goto(BASE + "/app/medicines")  # doses whose time already passed today are (correctly) not shown on the schedule
    expect(page.get_by_text("Glycomet").first).to_be_visible(timeout=15000)
    expect(page.get_by_text("Uprise D3")).to_have_count(0)
    shot(page, "06b_medicines_after_rx")


@step("lab report: upload → verify → analysis (EN + HI)")
def lab(page):
    page.goto(BASE + "/app/reports/upload")
    page.get_by_role("button", name=re.compile("blood report")).click()
    expect(page.get_by_text("Is this information correct?")).to_be_visible(timeout=30000)
    shot(page, "07_lab_verify")
    page.get_by_text("I have checked this information").click()
    page.get_by_role("button", name="Confirm and save").click()
    page.wait_for_url(re.compile(r".*/app/reports/[0-9a-f-]+$"), timeout=20000)
    expect(page.get_by_text("Important findings")).to_be_visible()
    shot(page, "08_report_analysis")
    page.get_by_role("radio", name="हिंदी").click()
    page.wait_for_timeout(300)
    shot(page, "09_report_hindi", full=False)


@step("security sample flagged")
def injection(page):
    page.goto(BASE + "/app/documents/new")
    page.get_by_role("button", name=re.compile("Security test")).click()
    expect(page.get_by_text("looks like instructions to an AI")).to_be_visible(timeout=30000)
    shot(page, "10_injection_flag", full=False)


@step("new user dashboard")
def new_dash(page):
    page.goto(BASE + "/app")
    expect(page.get_by_text("Today's medicines").first).to_be_visible(timeout=15000)
    shot(page, "11_dashboard_new_user")


@step("demo patient: dashboard (desktop + mobile)")
def demo_dash(page, mobile):
    page.context.clear_cookies()
    page.goto(BASE + "/login")
    page.get_by_role("button", name="Demo patient").click()
    page.wait_for_url("**/app")
    expect(page.get_by_text("Health measurements")).to_be_visible(timeout=15000)
    shot(page, "12_dashboard_demo")
    mobile.context.add_cookies(page.context.cookies())
    mobile.goto(BASE + "/app")
    expect(mobile.get_by_text("Health measurements")).to_be_visible(timeout=15000)
    shot(mobile, "13_dashboard_mobile")


@step("medicines, nutrition, planner, food")
def modules(page):
    page.goto(BASE + "/app/medicines")
    expect(page.get_by_text("Active medicines")).to_be_visible(timeout=15000)
    shot(page, "14_medicines")
    page.goto(BASE + "/app/nutrition")
    expect(page.get_by_text("Your plan follows these rules")).to_be_visible(timeout=15000)
    shot(page, "15_nutrition")
    page.goto(BASE + "/app/nutrition/planner")
    expect(page.get_by_text("Total")).to_be_visible(timeout=15000)
    shot(page, "16_planner", full=False)
    page.goto(BASE + "/app/nutrition")
    page.locator("a[href*='/app/nutrition/foods/']").first.click()
    expect(page.get_by_text("Why this suits you")).to_be_visible(timeout=15000)
    shot(page, "17_food_detail")


@step("assistant: tools, guardrail, HITL approval")
def assistant(page):
    page.goto(BASE + "/app/assistant")
    page.wait_for_timeout(1200)
    if page.get_by_role("alertdialog", name="Medicine reminder").count():  # in-app reminder popup can cover the chat
        page.get_by_role("button", name="Dismiss").click()
    box = page.get_by_label("Message")
    box.fill("What medicines are scheduled today?")
    box.press("Enter")
    expect(page.get_by_text("Looked up today's medicines")).to_be_visible(timeout=20000)
    box.fill("Should I double my metformin dose?")
    box.press("Enter")
    expect(page.get_by_text("can't advise changing a dose")).to_be_visible(timeout=20000)
    box.fill("Log my BP 132/86")
    box.press("Enter")
    expect(page.get_by_text("Needs your approval")).to_be_visible(timeout=20000)
    page.get_by_role("button", name="Approve").click()
    expect(page.get_by_text("approved")).to_be_visible(timeout=10000)
    shot(page, "18_assistant", full=False)


@step("appointments, history, family, settings")
def misc(page):
    for path, text, name in [("/app/appointments", "Dr. Anjali Mehta", "19_appointments"), ("/app/history", "How are you feeling today?", "20_history"),
                             ("/app/family", "Priya Kumar", "21_family"), ("/app/notifications", "Refill reminder", "22_notifications"),
                             ("/app/settings/reminders", "Speak reminders aloud", "23_reminder_settings")]:
        page.goto(BASE + path)
        expect(page.get_by_text(text).first).to_be_visible(timeout=15000)
        shot(page, name)
    page.goto(BASE + "/app/settings")
    page.get_by_role("tab", name="AI activity").click()
    expect(page.get_by_text("Recent AI runs")).to_be_visible(timeout=15000)
    shot(page, "24_ai_activity")


@step("caregiver dashboard")
def caregiver(page):
    page.context.clear_cookies()
    page.goto(BASE + "/login")
    page.get_by_role("button", name="Demo caregiver").click()
    page.wait_for_url("**/caregiver")
    expect(page.get_by_text("Ramesh Kumar").first).to_be_visible(timeout=15000)
    shot(page, "25_caregiver")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME, headless=True, args=["--no-sandbox"]) if CHROME else p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1366, "height": 860}, device_scale_factor=1, locale="en-IN", timezone_id="Asia/Kolkata")
        page = ctx.new_page()
        mctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="en-IN", timezone_id="Asia/Kolkata")
        mobile = mctx.new_page()
        landing(page); register(page); prescription(page); lab(page); injection(page); new_dash(page)
        demo_dash(page, mobile); modules(page); assistant(page); misc(page); caregiver(page)
        browser.close()
    w = max(len(r[0]) for r in results)
    for name, status, secs, err in results:
        print(f"{status:4}  {name:<{w}}  {secs:>5}s  {err}")
    print(f"\n{sum(r[1] == 'PASS' for r in results)}/{len(results)} journeys passed · screenshots in {SHOTS}")
    return 0 if all(r[1] == "PASS" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
