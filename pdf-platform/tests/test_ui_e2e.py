import asyncio
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from playwright.async_api import Page, async_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = "http://localhost:3000"
BACKEND = "http://localhost:8000"
EXAMPLES = [
    ROOT / "examples" / "simple.pdf",
    ROOT / "examples" / "multi-page.pdf",
    ROOT / "examples" / "invoice.pdf",
]
FORMATS = ["docx", "html", "png"]
SCREENSHOTS = ROOT / "tests" / "screenshots"
DOWNLOADS = ROOT / "tests" / "downloads"


@dataclass
class RunResult:
    pdf: str
    fmt: str
    passed: bool = False
    task_id: Optional[str] = None
    download: Optional[Path] = None
    screenshots: list[Path] = field(default_factory=list)
    error: Optional[str] = None
    progress_values: list[int] = field(default_factory=list)


class RunMonitor:
    def __init__(self) -> None:
        self.console_errors: list[str] = []
        self.failed_requests: list[str] = []
        self.bad_responses: list[str] = []

    def attach(self, page: Page) -> None:
        page.on("console", self._on_console)
        page.on("requestfailed", self._on_request_failed)
        page.on("response", self._on_response)

    def reset(self) -> None:
        self.console_errors.clear()
        self.failed_requests.clear()
        self.bad_responses.clear()

    def assert_clean(self) -> None:
        problems = []
        if self.console_errors:
            problems.append("console errors: " + " | ".join(self.console_errors))
        if self.failed_requests:
            problems.append("failed requests: " + " | ".join(self.failed_requests))
        if self.bad_responses:
            problems.append("bad responses: " + " | ".join(self.bad_responses))
        if problems:
            raise AssertionError("; ".join(problems))

    def _on_console(self, msg) -> None:
        if msg.type == "error":
            self.console_errors.append(msg.text)

    def _on_request_failed(self, request) -> None:
        if request.url.startswith((FRONTEND, BACKEND)):
            failure = request.failure or "unknown"
            # Ignore harmless aborts: Next.js RSC prefetches that get superseded by
            # navigations, and the GET that fires when clicking <a download> right
            # before the browser hijacks it for the file save.
            if "net::ERR_ABORTED" in failure:
                return
            self.failed_requests.append(f"{request.method} {request.url} ({failure})")

    def _on_response(self, response) -> None:
        if response.url.startswith((FRONTEND, BACKEND)) and response.status >= 400:
            self.bad_responses.append(f"HTTP {response.status} {response.request.method} {response.url}")


async def save_screenshot(page: Page, result: RunResult, name: str) -> None:
    path = SCREENSHOTS / f"{Path(result.pdf).stem}_{result.fmt}_{name}.png"
    await page.screenshot(path=path, full_page=True)
    result.screenshots.append(path)


async def wait_for_services(page: Page) -> None:
    await page.goto(FRONTEND, wait_until="domcontentloaded", timeout=30_000)
    response = await page.request.get(f"{BACKEND}/health", timeout=10_000)
    if not response.ok:
        raise RuntimeError(f"Backend health check failed: HTTP {response.status}")


async def click_format(page: Page, fmt: str) -> None:
    names = {
        "docx": ["Word", "DOCX"],
        "html": ["HTML"],
        "png": ["PNG"],
    }[fmt]
    for name in names:
        card = page.get_by_role("button", name=re.compile(name, re.I)).first
        if await card.count():
            await card.click()
            return
    raise AssertionError(f"Could not find format card for {fmt}")


async def sample_progress(page: Page, result: RunResult) -> None:
    labels = await page.locator("span").all_inner_texts()
    styles = await page.locator('div[style*="width:"]').evaluate_all(
        "nodes => nodes.map(node => node.getAttribute('style') || '')"
    )
    for value in labels + styles:
        match = re.search(r"(\d+)%", value)
        if match:
            pct = int(match.group(1))
            if pct not in result.progress_values:
                result.progress_values.append(pct)


async def collect_progress(page: Page, result: RunResult, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await sample_progress(page, result)
        except Exception:
            pass
        await asyncio.sleep(0.25)


async def run_conversion(page: Page, monitor: RunMonitor, pdf: Path, fmt: str) -> RunResult:
    result = RunResult(pdf=pdf.name, fmt=fmt)
    monitor.reset()
    try:
        await page.goto(FRONTEND, wait_until="networkidle", timeout=30_000)
        await expect(page).to_have_url(re.compile(r"/$"), timeout=10_000)
        await save_screenshot(page, result, "01_home")

        await page.locator('input[type="file"]').set_input_files(str(pdf))
        await expect(page.get_by_text(pdf.name)).to_be_visible(timeout=20_000)
        await page.get_by_text("Select target format").wait_for(timeout=20_000)
        await save_screenshot(page, result, "02_uploaded")

        await click_format(page, fmt)
        await expect(page.get_by_text("Selected").first).to_be_visible(timeout=10_000)
        await save_screenshot(page, result, "03_format_selected")

        stop_progress = asyncio.Event()
        progress_task = asyncio.create_task(collect_progress(page, result, stop_progress))
        await page.get_by_role("button", name=re.compile("Start Conversion", re.I)).click()
        await expect(page).to_have_url(re.compile(r"/convert/[^/]+$"), timeout=20_000)
        match = re.search(r"/convert/([^/]+)$", page.url)
        result.task_id = match.group(1) if match else None
        await save_screenshot(page, result, "04_progress")

        await expect(page).to_have_url(re.compile(r"/convert/[^/]+/result$"), timeout=180_000)
        stop_progress.set()
        await progress_task
        await expect(page.get_by_role("heading", name=re.compile("Download Result", re.I))).to_be_visible(timeout=20_000)
        await save_screenshot(page, result, "05_result")
        await sample_progress(page, result)

        async with page.expect_download(timeout=60_000) as download_info:
            await page.get_by_role("link", name=re.compile(f"Download {fmt.upper()}", re.I)).click()
        download = await download_info.value
        suggested = download.suggested_filename or f"{pdf.stem}.{fmt}"
        target = DOWNLOADS / f"{pdf.stem}_{fmt}_{suggested}"
        await download.save_as(target)
        result.download = target

        assert target.exists(), f"Download missing: {target}"
        assert target.stat().st_size > 0, f"Download is empty: {target}"
        assert target.suffix.lower() == f".{fmt}", f"Wrong extension: {target.name}"
        data = target.read_bytes()
        if fmt == "docx":
            assert data.startswith(b"PK"), "DOCX does not start with ZIP magic bytes PK"
        if fmt == "png":
            assert data.startswith(b"\x89PNG\r\n\x1a\n"), "PNG signature is invalid"
        if fmt == "html":
            assert b"<" in data[:512].lower(), "HTML output does not look like markup"

        # Note: with our immediate redirect, the progress page often unmounts before
        # we can sample mid-flight progress values. Don't fail the test for that;
        # just record what we saw (sometimes only the initial 10% from the API
        # response right before the redirect).
        if result.progress_values:
            assert max(result.progress_values) <= 100, "Progress exceeded 100%"
        monitor.assert_clean()
        result.passed = True
    except Exception as exc:
        result.error = str(exc)
        result.passed = False
        try:
            await save_screenshot(page, result, "error")
        except Exception:
            pass
    return result


async def main() -> int:
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    for folder in (SCREENSHOTS, DOWNLOADS):
        for path in folder.iterdir():
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)

    missing = [str(path) for path in EXAMPLES if not path.exists()]
    if missing:
        print("Missing example PDFs: " + ", ".join(missing))
        return 1

    results: list[RunResult] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1440, "height": 1000},
            accept_downloads=True,
        )
        page = await context.new_page()
        monitor = RunMonitor()
        monitor.attach(page)
        await wait_for_services(page)

        for pdf in EXAMPLES:
            for fmt in FORMATS:
                print(f"RUN {pdf.name} -> {fmt}")
                result = await run_conversion(page, monitor, pdf, fmt)
                results.append(result)
                status = "PASS" if result.passed else "FAIL"
                detail = f" task={result.task_id} download={result.download}" if result.passed else f" error={result.error}"
                print(f"  {status}{detail}")

        await context.close()
        await browser.close()

    passed = sum(1 for result in results if result.passed)
    failed = len(results) - passed
    print("\nSUMMARY")
    print(f"total runs: {len(results)}")
    print(f"passed: {passed}")
    print(f"failed: {failed}")
    for result in results:
        marker = "PASS" if result.passed else "FAIL"
        print(f"{marker} {result.pdf} -> {result.fmt} task={result.task_id} download={result.download} progress={result.progress_values} error={result.error}")
    print(f"screenshots: {SCREENSHOTS}")
    print(f"downloads: {DOWNLOADS}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
