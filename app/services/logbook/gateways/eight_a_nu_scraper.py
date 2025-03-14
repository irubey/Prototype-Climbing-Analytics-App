"""
8a.nu scraping service (CLI Version).

This module provides synchronous, production-ready functionality for:
- Authenticating with 8a.nu
- Scraping climbing ascent data
"""

# Standard library imports
from typing import Dict, List, Optional, Any
import subprocess
import json
import os
import random
import time
import urllib.parse
import re
import traceback
import secrets

# Application imports (adjust these based on your project structure)
from logging import getLogger  # Replace with your actual logging setup if different
logger = getLogger(__name__)

class ScrapingError(Exception):
    """Custom exception for scraping-related errors."""
    pass

class EightANuScraper:
    """CLI-based client for 8a.nu that handles authentication and data retrieval without asyncio."""
    
    BASE_URL = "https://www.8a.nu"
    LOGIN_URL = f"{BASE_URL}/login"
    ASCENTS_API_ENDPOINT = f"{BASE_URL}/unificationAPI/ascent/v1/web/users"
    TIMEOUT_SECONDS = 90  # Increased subprocess timeout
    RETRY_ATTEMPTS = 1    # Retry on transient failures
    MIN_DELAY = 2         # Minimum delay between requests (seconds)
    NODE_PATH = "node"    # Can be overridden with absolute path if needed
    
    def __init__(self, proxy_list: Optional[List[str]] = None):
        """Initialize the scraper with optional proxy list."""
        self.proxy_list = proxy_list or []
        self._user_slug = None
        self._cookie_file = None
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        self.scripts_dir = os.path.join(self.project_root, "scripts")
        os.makedirs(self.scripts_dir, exist_ok=True)
    
    def _get_random_proxy(self) -> Optional[Dict[str, str]]:
        """Get a random proxy from the proxy list."""
        if not self.proxy_list:
            return None
        proxy_url = random.choice(self.proxy_list)
        try:
            parsed = urllib.parse.urlparse(proxy_url)
            return {
                "server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
                "username": parsed.username,
                "password": parsed.password
            } if parsed.username and parsed.password else {
                "server": proxy_url
            }
        except Exception as e:
            logger.warning(f"Failed to parse proxy URL {proxy_url}: {str(e)}")
            return None
    
    def __enter__(self):
        """Initialize cookie file in scripts/ directory."""
        self._cookie_file = os.path.join(self.scripts_dir, f"cookies_{secrets.token_hex(8)}.json")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up cookie file."""
        if self._cookie_file and os.path.exists(self._cookie_file):
            try:
                os.remove(self._cookie_file)
            except Exception as e:
                logger.warning(f"Failed to remove cookie file {self._cookie_file}: {str(e)}")
        self._cookie_file = None
    
    def _extract_json(self, output: str) -> Any:
        """Extract JSON from potentially noisy CLI output."""
        match = re.search(r'\{.*\}', output, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON found in output: {output[:100]}")
        return json.loads(match.group(0))
    
    def _run_script(self, script_path: str, proxy: Optional[Dict[str, str]] = None) -> str:
        """Run a Playwright script with retries and timeout."""
        cmd = [self.NODE_PATH, script_path]
        env = os.environ.copy()
        if proxy:
            env["PLAYWRIGHT_PROXY_SERVER"] = proxy["server"]
            if "username" in proxy and "password" in proxy:
                env["PLAYWRIGHT_PROXY_USERNAME"] = proxy["username"]
                env["PLAYWRIGHT_PROXY_PASSWORD"] = proxy["password"]
        if self._cookie_file:
            env["PLAYWRIGHT_COOKIES_FILE"] = self._cookie_file
            
        # Set up debug screenshot path
        debug_dir = os.path.join(self.project_root, "debug")
        os.makedirs(debug_dir, exist_ok=True)
        env["PLAYWRIGHT_SCREENSHOT_PATH"] = os.path.join(debug_dir, f"8a_debug_{secrets.token_hex(4)}.png")
        
        for attempt in range(self.RETRY_ATTEMPTS + 1):
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=self.TIMEOUT_SECONDS,
                    env=env,
                    cwd=self.project_root,
                    encoding="utf-8"
                )
                if result.stderr:
                    logger.debug(f"Script stderr: {result.stderr}")
                return result.stdout
            except subprocess.TimeoutExpired as e:
                logger.warning(f"Script timed out after {self.TIMEOUT_SECONDS}s, attempt {attempt + 1}/{self.RETRY_ATTEMPTS + 1}")
                if attempt == self.RETRY_ATTEMPTS:
                    raise ScrapingError(f"Script timed out after {self.RETRY_ATTEMPTS + 1} attempts: {e.stderr}")
            except subprocess.CalledProcessError as e:
                logger.warning(f"Script failed, attempt {attempt + 1}/{self.RETRY_ATTEMPTS + 1}: {e.stderr}")
                if attempt == self.RETRY_ATTEMPTS:
                    raise ScrapingError(f"Script failed after {self.RETRY_ATTEMPTS + 1} attempts: {e.stderr}")
            time.sleep(self.MIN_DELAY * (attempt + 1))  # Exponential backoff
        return ""
    
    def authenticate(self, username: str, password: str) -> str:
        """Authenticate with 8a.nu using provided credentials and return the user slug."""
        if self._user_slug and os.path.exists(self._cookie_file):
            logger.info(f"Using existing session for slug: {self._user_slug}")
            return self._user_slug
        
        script_path = os.path.join(self.scripts_dir, f"auth_{secrets.token_hex(8)}.js")
        try:
            with open(script_path, "w") as f:
                f.write(f"""
const {{ chromium }} = require('playwright-extra');
const stealth = require('puppeteer-extra-plugin-stealth')();
chromium.use(stealth);

(async () => {{
    const browser = await chromium.launch({{headless: true}});
    const context = await browser.newContext({{
        storageState: {{cookies: [], origins: []}},
        viewport: {{width: 1920 + Math.floor(Math.random() * 100 - 50), height: 1080 + Math.floor(Math.random() * 100 - 50)}},
        userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0',
        extraHTTPHeaders: {{
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1'
        }}
    }});
    const page = await context.newPage();
    
    await page.evaluate(() => {{
        navigator.webdriver = false;
        Object.defineProperty(navigator, 'platform', {{value: 'Win32'}});
    }});
    
    await page.goto('https://www.8a.nu/login', {{timeout: 60000, waitUntil: 'domcontentloaded'}});
    console.log('Navigated to:', page.url());
    
    try {{
        await page.waitForURL('https://vlatka.vertical-life.info/auth/**', {{timeout: 60000}});
        console.log('Redirected to Vertical Life:', page.url());
    }} catch (e) {{
        console.log('Failed to redirect to Vertical Life, current URL:', page.url());
        console.log('Page content:', await page.content().catch(() => 'Unable to get content'));
        throw e;
    }}
    
    try {{
        await page.waitForSelector('input#username', {{timeout: 60000}});
        console.log('Found login form at:', page.url());
    }} catch (e) {{
        console.log('Login form not found, current URL:', page.url());
        console.log('Page content:', await page.content().catch(() => 'Unable to get content'));
        throw e;
    }}
    
    await page.fill('input#username', "{username.replace('"', '\\"')}");
    await page.fill('input#password', "{password.replace('"', '\\"')}");
    await page.click('input#kc-login');
    
    await page.waitForURL('https://www.8a.nu/**', {{timeout: 60000}});
    console.log('Redirected back to 8a.nu:', page.url());
    
    await page.waitForLoadState('domcontentloaded', {{timeout: 30000}});
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    const slug = await page.evaluate(() => {{
        const profileMenu = document.querySelector('div.profile-menu');
        if (!profileMenu) {{
            const fallbackLink = document.querySelector('div.user-name a[href^="/user/"]') ||
                                document.querySelector('.profile-img-wrapper a[href^="/user/"]') ||
                                document.querySelector('a[href^="/user/"]');
            if (!fallbackLink) return null;
            return fallbackLink.href.split('/user/')[1].split('/')[0];
        }}
        const link = profileMenu.querySelector('a[href^="/user/"]') || profileMenu.querySelector('a');
        if (!link || !link.href.includes('/user/')) return null;
        return link.href.split('/user/')[1].split('/')[0];
    }});
    
    if (!slug) {{
        console.log('Debug: Could not find user slug. Page URL:', page.url());
        await page.screenshot({{ path: process.env.PLAYWRIGHT_SCREENSHOT_PATH || '/tmp/8a_debug.png' }});
        throw new Error('User slug not found');
    }}
    
    await context.storageState({{path: process.env.PLAYWRIGHT_COOKIES_FILE}});
    console.log(JSON.stringify({{ "slug": slug }}));
    await browser.close();
}})();
""")
            
            proxy = self._get_random_proxy()
            output = self._run_script(script_path, proxy)
            logger.debug(f"Script output: {output}")
            result = self._extract_json(output)
            self._user_slug = result.get("slug")
            
            if not self._user_slug:
                raise ScrapingError("Could not extract user slug")
                
            logger.info(f"Authenticated with 8a.nu, slug: {self._user_slug}")
            return self._user_slug
            
        except Exception as e:
            logger.error("Authentication failed: %s", str(e), extra={"traceback": traceback.format_exc()})
            raise ScrapingError(f"Failed to authenticate with 8a.nu: {str(e)}")
        finally:
            if os.path.exists(script_path):
                os.remove(script_path)
    
    def get_ascents(self) -> Dict[str, Any]:
        """Retrieve all ascents data from 8a.nu API using Playwright script with session persistence and stealth."""
        if not self._user_slug:
            raise ScrapingError("Not authenticated. Call authenticate() first")
        
        script_path = os.path.join(self.scripts_dir, f"ascents_{secrets.token_hex(8)}.js")
        try:
            with open(script_path, "w") as f:
                f.write(f"""
    const {{ chromium }} = require('playwright-extra');
    const stealth = require('puppeteer-extra-plugin-stealth')();
    chromium.use(stealth);

    (async () => {{
        const browser = await chromium.launch({{headless: false}});
        const context = await browser.newContext({{
            storageState: process.env.PLAYWRIGHT_COOKIES_FILE,
            viewport: {{ width: 1920 + Math.floor(Math.random() * 100 - 50), height: 1080 + Math.floor(Math.random() * 100 - 50) }},
            userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0',
            extraHTTPHeaders: {{
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin'
            }}
        }});
        const page = await context.newPage();
        
        await page.evaluate(() => {{
            navigator.webdriver = false;
            Object.defineProperty(navigator, 'platform', {{ value: 'Win32' }});
        }});
        
        console.error('Loaded cookies:', JSON.stringify(await context.cookies()));
        console.error('Starting to fetch ascents for user slug:', '{self._user_slug}');
        const allAscents = [];
        const categories = ['sportclimbing', 'bouldering'];
        
        for (const category of categories) {{
            console.error('Processing category:', category);
            const categoryUrl = 'https://www.8a.nu/user/{self._user_slug}/' + category;
            try {{
                await page.goto(categoryUrl, {{ timeout: 60000, waitUntil: 'domcontentloaded' }});
                console.error('Navigated to category page:', page.url());
                await new Promise(resolve => setTimeout(resolve, 5000));
            }} catch (error) {{
                console.error('Error navigating to category', category, ':', error.message);
                continue;
            }}
            
            page.on('request', request => {{
                console.error('Request URL:', request.url());
                console.error('Request Headers:', JSON.stringify(request.headers()));
            }});
            
            let pageIndex = 0;
            let hasMorePages = true;
            
            while (hasMorePages) {{
                await new Promise(resolve => setTimeout(resolve, {self.MIN_DELAY * 1000}));
                
                const apiUrl = 'https://www.8a.nu/unificationAPI/ascent/v1/web/users/{self._user_slug}/ascents' +
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
                
                console.error('Requesting:', apiUrl);
                
                try {{
                    console.error('Starting API fetch within page context for:', apiUrl);
                    const response = await page.evaluate(async (url) => {{
                        try {{
                            const res = await fetch(url, {{
                                method: 'GET',
                                headers: {{
                                    'Accept': 'application/json, text/plain, */*',
                                    'Accept-Language': 'en-US,en;q=0.5',
                                    'Accept-Encoding': 'gzip, deflate, br, zstd',
                                    'Referer': window.location.href,
                                    'Sec-Fetch-Dest': 'empty',
                                    'Sec-Fetch-Mode': 'cors',
                                    'Sec-Fetch-Site': 'same-origin',
                                    'Pragma': 'no-cache',
                                    'Cache-Control': 'no-cache',
                                    'X-Requested-With': 'XMLHttpRequest'
                                }},
                                credentials: 'include'
                            }});
                            const text = await res.text();
                            console.error('Fetch status:', res.status);
                            console.error('Fetch response body:', text.substring(0, 500) + (text.length > 500 ? '...' : ''));
                            return {{ status: res.status, body: text }};
                        }} catch (error) {{
                            console.error('Inner fetch error:', error.message);
                            throw error;
                        }}
                    }}, apiUrl);
                    
                    console.error('Fetch completed, status:', response.status);
                    
                    let data;
                    try {{
                        data = JSON.parse(response.body);
                    }} catch (e) {{
                        console.error('JSON parse error:', e.message, 'Response body:', response.body);
                        await page.screenshot({{ path: process.env.PLAYWRIGHT_SCREENSHOT_PATH || '/tmp/8a_api_error.png' }});
                        break;
                    }}
                    
                    if (response.status !== 200) {{
                        console.error('Request failed with status', response.status, 'body:', response.body);
                        break;
                    }}
                    
                    const ascents = data.ascents || [];
                    if (ascents.length === 0) {{
                        console.error('No more ascents for', category, 'after page', pageIndex);
                        hasMorePages = false;
                        break;
                    }}
                    
                    console.error('Found', ascents.length, 'ascents for', category, 'on page', pageIndex);
                    
                    ascents.forEach(ascent => {{
                        ascent.platform = 'eight_a';
                        ascent.discipline = ascent.category === 0 ? 'sport' : 'boulder';
                        delete ascent.category;
                        allAscents.push(ascent);
                    }});
                    
                    pageIndex++;
                }} catch (error) {{
                    console.error('Fetch error:', error.message);
                    console.error('Fetch error details:', JSON.stringify(error));
                    await page.screenshot({{ path: process.env.PLAYWRIGHT_SCREENSHOT_PATH || '/tmp/8a_api_error.png' }});
                    break;
                }}
            }}
        }}
        
        console.error('Total ascents found:', allAscents.length);
        console.log(JSON.stringify({{ 
            ascents: allAscents,
            totalItems: allAscents.length,
            pageIndex: 0
        }}));
        
        await browser.close();
    }})().catch(error => {{
        console.error('Unhandled error:', error.message);
        console.error('Error stack trace:', error.stack || 'No stack trace available');
        process.exit(1);
    }});
    """)
            
            proxy = self._get_random_proxy()
            output = self._run_script(script_path, proxy)
            logger.debug(f"Ascent response output: {output[:500]}...")
            
            try:
                data = self._extract_json(output)
                all_ascents = data.get("ascents", [])
                
                if not all_ascents:
                    logger.warning("No ascents found in the response")
                    logger.debug(f"Full response: {output}")
                    raise ScrapingError("Failed to retrieve any ascents from 8a.nu")
                    
                logger.info(f"Fetched {len(all_ascents)} ascents from 8a.nu")
                
                return {
                    "ascents": all_ascents,
                    "totalItems": len(all_ascents),
                    "pageIndex": 0,
                    "user_slug": self._user_slug
                }
            except ValueError as e:
                logger.error("JSON parsing error: %s", str(e), extra={"traceback": traceback.format_exc()})
                raise ScrapingError(f"Failed to parse ascent data: {str(e)}")
            
        except Exception as e:
            logger.error("Ascent retrieval failed: %s", str(e), extra={"traceback": traceback.format_exc()})
            raise ScrapingError(f"Failed to retrieve ascents: {str(e)}")
        finally:
            if os.path.exists(script_path):
                os.remove(script_path)

if __name__ == "__main__":
    # Example usage
    proxy_list = []  # Add your proxy list here for production
    with EightANuScraper(proxy_list) as scraper:
        scraper.authenticate("your_username", "your_password")
        ascents_data = scraper.get_ascents()
        print(json.dumps(ascents_data, indent=2))