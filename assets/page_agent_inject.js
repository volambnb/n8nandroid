/**
 * Page-Agent Injection Helper
 * 
 * This script is injected into IXBrowser profiles via Playwright.
 * It loads the Page-Agent library and exposes a helper for the
 * Python orchestrator to call.
 * 
 * Usage from Playwright (Python):
 *   await page.add_script_tag(path="assets/page_agent_inject.js")
 *   result = await page.evaluate("window.__runPageAgent(opts)")
 */
(function () {
    "use strict";

    // Prevent double-injection
    if (window.__PAGE_AGENT_INJECTED) return;
    window.__PAGE_AGENT_INJECTED = true;

    /**
     * Load the Page-Agent IIFE bundle from CDN (once).
     * @param {string} cdnUrl
     * @returns {Promise<void>}
     */
    function loadPageAgent(cdnUrl) {
        return new Promise((resolve, reject) => {
            if (window.PageAgent) {
                resolve();
                return;
            }
            const script = document.createElement("script");
            script.src = cdnUrl;
            script.crossOrigin = "true";
            script.onload = () => resolve();
            script.onerror = () => reject(new Error("Failed to load Page-Agent from " + cdnUrl));
            document.head.appendChild(script);
        });
    }

    /**
     * Execute a task using Page-Agent.
     * 
     * @param {Object} opts
     * @param {string} opts.task      – Natural language instruction
     * @param {string} opts.model     – LLM model name (e.g. "gpt-4o")
     * @param {string} opts.baseURL   – LLM API base URL
     * @param {string} opts.apiKey    – LLM API key
     * @param {string} opts.language  – Agent language ("en-US")
     * @param {string} [opts.cdnUrl]  – Page-Agent CDN URL (optional, uses default)
     * @returns {Promise<{success: boolean, data: string}>}
     */
    window.__runPageAgent = async function (opts) {
        const cdnUrl = opts.cdnUrl || "https://cdn.jsdelivr.net/npm/page-agent@latest/dist/iife/page-agent.js";

        await loadPageAgent(cdnUrl);

        if (!window.PageAgent) {
            throw new Error("PageAgent class not available after script load");
        }

        const agent = new window.PageAgent({
            model: opts.model,
            baseURL: opts.baseURL,
            apiKey: opts.apiKey,
            language: opts.language || "en-US",
        });

        const result = await agent.execute(opts.task);
        return {
            success: result.success,
            data: result.data || "",
        };
    };
})();
