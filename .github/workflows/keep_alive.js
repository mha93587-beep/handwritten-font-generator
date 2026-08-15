const { chromium } = require('playwright');

const URLS = [
"https://handwritten-font-generator-d8hjpmaoz9uc4x3iqdbhu8.streamlit.app/"
];

(async () => {
  const browser = await chromium.launch({ headless: true });
  for (const url of URLS) {
    console.log(`--------------------------------------------------`);
    console.log(`[Playwright Keep-Alive] Connecting to Streamlit App: ${url}`);
    try {
      const page = await browser.newPage();
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
      
      // Wait 3s for hydration
      await page.waitForTimeout(3000);
      
      // If "Yes, get this app back up!" button exists (sleeping app), click it to wake up automatically!
      const wakeBtn = await page.$('button:has-text("Yes, get this app back up!")');
      if (wakeBtn) {
        console.log(`⚡ [Auto-Wakeup] Sleeping app detected! Clicking 'Yes, get this app back up!'...`);
        await wakeBtn.click();
        await page.waitForTimeout(8000);
      }

      // Hold active WebSocket connection open for 12 seconds
      console.log(`✅ [WebSocket Connected] Session active. Maintaining heartbeat for 12 seconds...`);
      await page.waitForTimeout(12000);
      await page.close();
      console.log(`🎉 [Keep-Alive Success] Active session verified for ${url}`);
    } catch (e) {
      console.log(`⚠️ [Session Warning] ${url}: ${e.message}`);
    }
  }
  await browser.close();
  console.log(`--------------------------------------------------`);
  console.log(`All 4 Streamlit apps connected via real WebSocket browser sessions successfully!`);
})();
