import asyncio
from playwright.async_api import async_playwright
import urllib.parse

async def search_google_for_ats(title, company):
    async with async_playwright() as p:
        # Launch browser in headless mode
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        query = f"{title} {company} careers apply"
        print(f"Searching Google for: {query}")
        
        # Navigate to Google Search
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        await page.goto(url, wait_until="domcontentloaded")
        
        # Wait a moment for results
        await page.wait_for_timeout(2000)
        
        # Check if we hit a captcha
        if "sorry/index" in page.url:
            print("Hit Google Captcha!")
            await browser.close()
            return None
            
        # Extract links
        links = await page.evaluate('''() => {
            const anchors = Array.from(document.querySelectorAll('a[href]'));
            return anchors.map(a => a.href);
        }''')
        
        ats_link = None
        for link in links:
            if 'google.com' not in link and link.startswith('http'):
                # Heuristic: check if it contains ATS keywords or specific job patterns
                if any(x in link.lower() for x in ['wd1.myworkdayjobs.com', 'greenhouse.io', 'lever.co', 'job', 'req', 'posting']):
                    print(f"Found ATS Link: {link}")
                    ats_link = link
                    break
        
        if not ats_link:
            print("No ATS link found in first page.")
            
        await browser.close()
        return ats_link

if __name__ == "__main__":
    asyncio.run(search_google_for_ats("Software Engineer (Level 1)", "Northrop Grumman Australia"))
