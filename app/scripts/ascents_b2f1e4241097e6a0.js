
const { chromium } = require('playwright-extra');
const stealth = require('puppeteer-extra-plugin-stealth')();
chromium.use(stealth);

(async () => {
    const browser = await chromium.launch({headless: false});
    const context = await browser.newContext({
        storageState: process.env.PLAYWRIGHT_COOKIES_FILE,
        viewport: { width: 1920 + Math.floor(Math.random() * 100 - 50), height: 1080 + Math.floor(Math.random() * 100 - 50) },
        userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0'
    });
    const page = await context.newPage();
    
    const allAscents = [];
    const categories = ['sportclimbing', 'bouldering'];
    
    for (const category of categories) {
        const categoryUrl = 'https://www.8a.nu/user/adam-ondra/' + category;
        await page.goto(categoryUrl, { timeout: 60000, waitUntil: 'domcontentloaded' });
        await new Promise(resolve => setTimeout(resolve, 5000));
        
        let pageIndex = 0;
        let hasMorePages = true;
        
        while (hasMorePages) {
            await new Promise(resolve => setTimeout(resolve, 2000));
            
            const apiUrl = 'https://www.8a.nu/unificationAPI/ascent/v1/web/users/adam-ondra/ascents' +
                '?category=' + category +
                '&pageIndex=' + pageIndex +
                '&pageSize=50' +
                '&sortField=date_desc' +
                '&timeFilter=0' +
                '&gradeFilter=0' +
                '&typeFilter=' +
                '&includeProjects=true' +
                '&searchQuery=' +
                '&showRepeats=true' +
                '&showDuplicates=false';
            
            const response = await page.evaluate(async (url) => {
                const res = await fetch(url, {
                    method: 'GET',
                    headers: {
                        'Accept': 'application/json',
                        'Referer': window.location.href,
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    credentials: 'include'
                });
                return { status: res.status, body: await res.text() };
            }, apiUrl);
            
            if (response.status === 429) {
                throw new Error('Rate limit exceeded');
            }
            
            if (response.status === 401 || response.status === 403) {
                throw new Error('Authentication failed');
            }
            
            let data = JSON.parse(response.body);
            const ascents = data.ascents || [];
            if (ascents.length === 0) {
                hasMorePages = false;
                break;
            }
            
            ascents.forEach(ascent => {
                ascent.platform = 'eight_a';
                ascent.discipline = ascent.category === 0 ? 'sport' : 'boulder';
                delete ascent.category;
                allAscents.push(ascent);
            });
            
            pageIndex++;
        }
    }
    
    console.log(JSON.stringify({ 
        ascents: allAscents,
        totalItems: allAscents.length,
        pageIndex: 0
    }));
    await browser.close();
})();
