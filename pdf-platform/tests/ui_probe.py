"""快速探测 UI：完成完整流程一次到底，每步截图 + 打印实际 DOM"""
import asyncio, os, json
from playwright.async_api import async_playwright

SMOKE = "/tmp/ui_smoke.pdf"
FRONTEND = "http://localhost:3000"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await ctx.new_page()

        # 开启网络日志
        page.on("response", lambda r: print(f"  HTTP {r.status} {r.request.method} {r.url}")
                if "/api/" in r.url else None)
        page.on("console", lambda m: print(f"  [console.{m.type}] {m.text}"))

        print("\n=== STEP 1: 打开首页 ===")
        await page.goto(FRONTEND, wait_until="networkidle")
        await page.screenshot(path="/tmp/probe_01_home.png", full_page=True)

        print("\n=== STEP 2: 上传 PDF ===")
        await page.set_input_files('input[type="file"]', SMOKE)
        await page.wait_for_timeout(2500)
        await page.screenshot(path="/tmp/probe_02_uploaded.png", full_page=True)

        # 打印所有按钮的文字 + disabled
        print("\n--- 所有 button ---")
        btns = await page.query_selector_all("button")
        for i, b in enumerate(btns):
            txt = (await b.inner_text()).strip()[:50]
            disabled = await b.is_disabled()
            visible = await b.is_visible()
            print(f"  [{i}] visible={visible} disabled={disabled} text={txt!r}")

        # 打印所有 role=button / clickable cards
        print("\n--- 候选格式卡 (button + 可点击 div) ---")
        cards = await page.query_selector_all('[role="button"], button[class*="format"], div[class*="card"]')
        for i, c in enumerate(cards[:20]):
            txt = (await c.inner_text()).strip()[:60]
            print(f"  [{i}] {txt!r}")

        print("\n=== STEP 3: 试着点击 'Word' 格式 ===")
        # 用 :has-text 找
        try:
            target = page.get_by_text("Word", exact=False).first
            await target.click()
            print("  ✅ clicked 'Word'")
        except Exception as e:
            print(f"  ❌ {e}")
        await page.wait_for_timeout(800)
        await page.screenshot(path="/tmp/probe_03_word_selected.png", full_page=True)

        # 再次列出按钮，看转换按钮是否变 enabled
        print("\n--- 选择 Word 后的 button 状态 ---")
        btns = await page.query_selector_all("button")
        for i, b in enumerate(btns):
            txt = (await b.inner_text()).strip()[:50]
            disabled = await b.is_disabled()
            visible = await b.is_visible()
            if visible:
                print(f"  [{i}] disabled={disabled} text={txt!r}")

        print("\n=== STEP 4: 点击 Convert / Start 按钮 ===")
        try:
            # 尝试多种文案
            for selector in [
                'button:has-text("Convert")',
                'button:has-text("Start")',
                'button:has-text("Begin")',
                'button:has-text("转换")',
                'button:has-text("开始")',
            ]:
                btn = await page.query_selector(selector)
                if btn and await btn.is_visible() and not await btn.is_disabled():
                    print(f"  found button via: {selector}")
                    await btn.click()
                    print("  ✅ clicked")
                    break
            else:
                print("  ⚠️ 找不到可点的转换按钮")
        except Exception as e:
            print(f"  ❌ {e}")

        await page.wait_for_timeout(4000)
        await page.screenshot(path="/tmp/probe_04_after_convert.png", full_page=True)

        # 看下页面有没有进度/结果
        body = await page.inner_text("body")
        print(f"\n  body keywords: complete={('complete' in body.lower())} download={('download' in body.lower())} fail={('fail' in body.lower())}")
        print(f"  body excerpt: {body[:300]!r}")

        # 等更久看完成
        for i in range(20):
            await page.wait_for_timeout(1000)
            body = await page.inner_text("body")
            if "download" in body.lower() or "complete" in body.lower() or "fail" in body.lower():
                print(f"  reached terminal state after {i+1}s")
                break

        await page.screenshot(path="/tmp/probe_05_final.png", full_page=True)
        print(f"\n  最终 body excerpt: {body[:500]!r}")

        await browser.close()


asyncio.run(main())
