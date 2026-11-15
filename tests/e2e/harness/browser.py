"""Playwright smoke checks of a deployed org's dashboard."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

TIMEOUT_MS = 60_000


@contextmanager
def dashboard(ui_url: str, artifacts: Path) -> Iterator[Page]:
    """Open the dashboard logged in as `e2e`, keeping a trace and a final screenshot in `artifacts`."""
    artifacts.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context()
        context.tracing.start(screenshots=True, snapshots=True)
        page = context.new_page()
        page.set_default_timeout(TIMEOUT_MS)
        try:
            page.goto(ui_url)
            login = page.get_by_placeholder('Your name')
            login.fill('e2e')
            login.press('Enter')
            yield page
        finally:
            page.screenshot(path=artifacts / 'dashboard.png', full_page=True)
            context.tracing.stop(path=artifacts / 'trace.zip')
            browser.close()


def open_tab(page: Page, name: str) -> None:
    """Switch the dashboard to the tab called `name`, such as `Runs` or `Inbox`."""
    page.get_by_role('button', name=name, exact=True).click()


def expect_run_listed(page: Page, target: str) -> None:
    """Open the Runs view and wait until a run of `target` is listed."""
    open_tab(page, 'Runs')
    expect(page.get_by_text(target).first).to_be_visible()


def approve_from_inbox(page: Page, run_id: str) -> None:
    """Open the Inbox and approve the approval held by `run_id`."""
    open_tab(page, 'Inbox')
    card = page.locator('div', has_text=f'run {run_id[:8]}').filter(has=page.get_by_role('button', name='Approve'))
    card.last.get_by_role('button', name='Approve').click()
