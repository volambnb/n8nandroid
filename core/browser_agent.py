"""Browser Agent – bridges IXBrowser profiles to Page-Agent via Playwright CDP."""

from __future__ import annotations

import asyncio
import json
import logging
import random
from dataclasses import dataclass, field
from typing import Any

from playwright.async_api import Browser, Page, async_playwright

from config.settings import settings
from core.profile_manager import OpenResult

logger = logging.getLogger(__name__)

# Page-Agent bootstrap JS – injected once per page.  The actual task execution
# happens via a second evaluate() call so we can pass dynamic params.
_PAGE_AGENT_SETUP_JS = """
() => {
    return new Promise((resolve, reject) => {
        if (window.__PAGE_AGENT_READY) { resolve(true); return; }
        const script = document.createElement('script');
        script.src = '%CDN_URL%';
        script.crossOrigin = 'true';
        script.onload = () => { window.__PAGE_AGENT_READY = true; resolve(true); };
        script.onerror = (e) => reject('Failed to load Page-Agent script');
        document.head.appendChild(script);
    });
}
"""

_PAGE_AGENT_EXEC_JS = """
async (opts) => {
    const agent = new PageAgent({
        model:    opts.model,
        baseURL:  opts.baseURL,
        apiKey:   opts.apiKey,
        language: opts.language,
    });
    const result = await agent.execute(opts.task);
    return { success: result.success, data: result.data };
}
"""


@dataclass
class TaskResult:
    success: bool
    data: str
    profile_id: str
    error: str | None = None


class BrowserAgent:
    """Connects to an IXBrowser profile via CDP and runs Page-Agent tasks."""

    def __init__(self) -> None:
        self._pw_context = None
        self._pw = None

    async def _ensure_playwright(self):
        if self._pw is None:
            self._pw_context = async_playwright()
            self._pw = await self._pw_context.start()
        return self._pw

    async def close(self):
        if self._pw_context is not None:
            await self._pw_context.__aexit__(None, None, None)
            self._pw = None
            self._pw_context = None

    # ── core execution flow ──────────────────────────────────────────

    async def execute_task(
        self,
        profile: OpenResult,
        task_prompt: str,
        url: str | None = None,
        min_delay: float | None = None,
        max_delay: float | None = None,
        timeout: float | None = None,
    ) -> TaskResult:
        """Open CDP connection, inject Page-Agent, execute task, return result.

        The Playwright browser object is connected/disconnected per call so
        each profile gets a clean connection.
        """
        pw = await self._ensure_playwright()
        cdp_url = f"http://{profile.debugging_address}"
        browser: Browser | None = None
        timeout = timeout or settings.task_timeout

        try:
            browser = await pw.chromium.connect_over_cdp(cdp_url)
            contexts = browser.contexts
            if not contexts:
                return TaskResult(
                    success=False,
                    data="",
                    profile_id=profile.profile_id,
                    error="No browser contexts found",
                )

            page: Page = contexts[0].pages[0] if contexts[0].pages else await contexts[0].new_page()

            # Navigate to target URL if provided
            if url:
                delay = random.uniform(
                    min_delay or settings.task_min_delay,
                    max_delay or settings.task_max_delay,
                )
                await asyncio.sleep(delay)
                await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                # Wait for page to settle
                await asyncio.sleep(random.uniform(2, 4))

            # Inject Page-Agent JS
            setup_js = _PAGE_AGENT_SETUP_JS.replace("%CDN_URL%", settings.page_agent_cdn)
            await page.evaluate(setup_js)
            await asyncio.sleep(1)  # let the script initialise

            # Execute the task via Page-Agent
            result = await asyncio.wait_for(
                page.evaluate(
                    _PAGE_AGENT_EXEC_JS,
                    {
                        "model": settings.openai_model,
                        "baseURL": settings.openai_base_url,
                        "apiKey": settings.openai_api_key,
                        "language": settings.page_agent_language,
                        "task": task_prompt,
                    },
                ),
                timeout=timeout,
            )

            return TaskResult(
                success=result.get("success", False),
                data=result.get("data", ""),
                profile_id=profile.profile_id,
            )

        except asyncio.TimeoutError:
            logger.warning("Task timed out for profile %s", profile.profile_id)
            return TaskResult(
                success=False,
                data="",
                profile_id=profile.profile_id,
                error=f"Task timed out after {timeout}s",
            )
        except Exception as exc:
            logger.exception("Task error for profile %s", profile.profile_id)
            return TaskResult(
                success=False,
                data="",
                profile_id=profile.profile_id,
                error=str(exc),
            )
        finally:
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass
