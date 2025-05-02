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
from app.core.logging import logger

class ScrapingError(Exception):
    """Custom exception for scraping-related errors."""
    pass

class AccountManager:
    """Manages a pool of 8a.nu accounts and their session cookies."""
    def __init__(self):
        self.accounts = [
            (os.getenv(f"ACCOUNT{i}_USERNAME"), os.getenv(f"ACCOUNT{i}_PASSWORD"))
            for i in range(1, int(os.getenv("NUM_ACCOUNTS", "3")) + 1)
            if os.getenv(f"ACCOUNT{i}_USERNAME") and os.getenv(f"ACCOUNT{i}_PASSWORD")
        ]
        if not self.accounts:
            raise ValueError("No accounts configured in environment variables")
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        self.cookie_dir = os.path.join(self.project_root, "cookies")
        os.makedirs(self.cookie_dir, exist_ok=True)
        self.cookie_files = [os.path.join(self.cookie_dir, f"account{i}.json") for i in range(len(self.accounts))]

    def get_random_account(self) -> tuple[int, tuple[str, str], str]:
        """Select a random account and return its index, credentials, and cookie file."""
        index = random.randint(0, len(self.accounts) - 1)
        return index, self.accounts[index], self.cookie_files[index]

class EightANuScraper:
    """CLI-based client for 8a.nu that handles authentication and data retrieval without asyncio."""
    
    BASE_URL = "https://www.8a.nu"
    LOGIN_URL = f"{BASE_URL}/login"
    ASCENTS_API_ENDPOINT = f"{BASE_URL}/unificationAPI/ascent/v1/web/users"
    TIMEOUT_SECONDS = 60 * 5
    RETRY_ATTEMPTS = 3  # Increased retry attempts
    MIN_DELAY = 2
    MAX_DELAY = 60  # Maximum delay in seconds
    NODE_PATH = "node"
    
    def __init__(self, cookie_file: str, proxy_list: Optional[List[str]] = None):
        """Initialize the scraper with a specific cookie file and optional proxy list."""
        self.cookie_file = cookie_file
        self.proxy_list = proxy_list or []
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        self.scripts_dir = os.path.join(self.project_root, "scripts")
        os.makedirs(self.scripts_dir, exist_ok=True)
        self._current_credentials = None  # Store current credentials for re-authentication
        self._auth_retries = 0  # Track authentication retries
        self._rate_limit_retries = 0  # Track rate limit retries
        self._current_delay = self.MIN_DELAY  # Current delay for exponential backoff
        
        # Ensure cookie directory exists
        cookie_dir = os.path.dirname(self.cookie_file)
        if cookie_dir:
            os.makedirs(cookie_dir, exist_ok=True)
            
        logger.info("Initialized EightANuScraper", extra={
            "cookie_file": self.cookie_file,
            "proxy_count": len(self.proxy_list),
            "scripts_dir": self.scripts_dir,
            "min_delay": self.MIN_DELAY,
            "max_delay": self.MAX_DELAY
        })
    
    def _calculate_backoff_delay(self) -> float:
        """Calculate exponential backoff delay with jitter."""
        # Exponential backoff: delay = min_delay * (2 ^ retries)
        delay = min(self.MIN_DELAY * (2 ** self._rate_limit_retries), self.MAX_DELAY)
        # Add jitter: random value between 0 and 1 second
        jitter = random.uniform(0, 1)
        return delay + jitter
    
    def _handle_rate_limit(self) -> None:
        """Handle rate limiting by implementing exponential backoff."""
        self._rate_limit_retries += 1
        self._current_delay = self._calculate_backoff_delay()
        
        logger.warning("Rate limit encountered", extra={
            "retry_count": self._rate_limit_retries,
            "current_delay": self._current_delay,
            "max_delay": self.MAX_DELAY
        })
        
        time.sleep(self._current_delay)
    
    def _reset_rate_limit(self) -> None:
        """Reset rate limit tracking."""
        self._rate_limit_retries = 0
        self._current_delay = self.MIN_DELAY
    
    def _validate_cookie_file(self) -> bool:
        """Validate that the cookie file exists and contains valid cookies."""
        try:
            if not os.path.exists(self.cookie_file):
                logger.info(f"Cookie file {self.cookie_file} does not exist")
                return False
                
            # Check if file is readable and contains valid JSON
            with open(self.cookie_file, 'r') as f:
                cookies = json.load(f)
                
            # Basic validation of cookie structure
            if not isinstance(cookies, dict):
                logger.warning(f"Invalid cookie file format in {self.cookie_file}")
                return False
                
            # Check for required cookie fields
            required_fields = {'cookies', 'origins'}
            if not all(field in cookies for field in required_fields):
                logger.warning(f"Missing required fields in cookie file {self.cookie_file}")
                return False
                
            # Check if cookies list exists and is not empty
            cookie_count = len(cookies.get('cookies', []))
            if cookie_count == 0:
                logger.warning(f"No cookies found in {self.cookie_file}")
                return False
                
            logger.info(f"Validated cookie file", extra={
                "cookie_file": self.cookie_file,
                "cookie_count": cookie_count,
                "has_origins": bool(cookies.get('origins'))
            })
            return True
            
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in cookie file {self.cookie_file}")
            return False
        except Exception as e:
            logger.warning(f"Error validating cookie file {self.cookie_file}: {str(e)}")
            return False
    
    def _initialize_cookie_file(self, username: str, password: str) -> None:
        """Initialize a new cookie file with authentication."""
        try:
            logger.info("Initializing new cookie file", extra={
                "cookie_file": self.cookie_file,
                "username": username[:3] + "***"  # Log partial username for security
            })
            
            # Create empty cookie file structure
            with open(self.cookie_file, 'w') as f:
                json.dump({'cookies': [], 'origins': []}, f)
                
            # Authenticate to populate cookies
            self.authenticate(username, password)
            
            # Verify cookies were created
            if not self._validate_cookie_file():
                raise ScrapingError("Failed to initialize valid cookie file")
                
            logger.info(f"Successfully initialized cookie file", extra={
                "cookie_file": self.cookie_file,
                "auth_retries": self._auth_retries
            })
            
        except Exception as e:
            logger.error(f"Failed to initialize cookie file", extra={
                "cookie_file": self.cookie_file,
                "error": str(e),
                "error_type": type(e).__name__
            })
            if os.path.exists(self.cookie_file):
                os.remove(self.cookie_file)
            raise ScrapingError(f"Failed to initialize cookie file: {str(e)}")
    
    def _get_random_proxy(self) -> Optional[Dict[str, str]]:
        """Get a random proxy from the proxy list."""
        if not self.proxy_list:
            logger.debug("No proxies available")
            return None
            
        proxy_url = random.choice(self.proxy_list)
        try:
            parsed = urllib.parse.urlparse(proxy_url)
            proxy = {
                "server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
                "username": parsed.username,
                "password": parsed.password
            } if parsed.username and parsed.password else {
                "server": proxy_url
            }
            
            logger.info("Selected proxy", extra={
                "proxy_server": proxy["server"],
                "has_credentials": bool(parsed.username and parsed.password)
            })
            return proxy
            
        except Exception as e:
            logger.warning(f"Failed to parse proxy URL", extra={
                "proxy_url": proxy_url,
                "error": str(e)
            })
            return None
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit; no cleanup of persistent cookie file."""
        pass
    
    def _extract_json(self, output: str) -> Any:
        """Extract JSON from CLI output."""
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
                
        env["PLAYWRIGHT_COOKIES_FILE"] = self.cookie_file
        
        debug_dir = os.path.join(self.project_root, "debug")
        os.makedirs(debug_dir, exist_ok=True)
        screenshot_path = os.path.join(debug_dir, f"8a_debug_{secrets.token_hex(4)}.png")
        env["PLAYWRIGHT_SCREENSHOT_PATH"] = screenshot_path
        
        logger.info("Running Playwright script", extra={
            "script_path": script_path,
            "has_proxy": bool(proxy),
            "cookie_file": self.cookie_file,
            "screenshot_path": screenshot_path
        })
        
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
                    logger.debug(f"Script stderr", extra={
                        "stderr": result.stderr,
                        "attempt": attempt + 1
                    })
                return result.stdout
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
                logger.warning(f"Script failed", extra={
                    "attempt": attempt + 1,
                    "total_attempts": self.RETRY_ATTEMPTS + 1,
                    "error": str(e),
                    "error_type": type(e).__name__
                })
                if attempt == self.RETRY_ATTEMPTS:
                    raise ScrapingError(f"Script failed after {self.RETRY_ATTEMPTS + 1} attempts: {str(e)}")
            time.sleep(self.MIN_DELAY * (attempt + 1))
        return ""
    
    def authenticate(self, username: str, password: str):
        """Authenticate with 8a.nu using provided credentials."""
        self._current_credentials = (username, password)  # Store credentials for potential re-authentication
        self._auth_retries = 0  # Reset auth retries counter
        
        logger.info("Starting authentication", extra={
            "username": username[:3] + "***",  # Log partial username for security
            "cookie_file": self.cookie_file
        })
        
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
        userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0'
    }});
    const page = await context.newPage();
    
    await page.goto('https://www.8a.nu/login', {{timeout: 60000, waitUntil: 'domcontentloaded'}});
    await page.waitForURL('https://vlatka.vertical-life.info/auth/**', {{timeout: 60000}});
    await page.waitForSelector('input#username', {{timeout: 60000}});
    
    await page.fill('input#username', "{username.replace('"', '\\"')}");
    await page.fill('input#password', "{password.replace('"', '\\"')}");
    await page.click('input#kc-login');
    
    await page.waitForURL('https://www.8a.nu/**', {{timeout: 60000}});
    await page.waitForLoadState('domcontentloaded', {{timeout: 30000}});
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    await context.storageState({{path: process.env.PLAYWRIGHT_COOKIES_FILE}});
    console.log(JSON.stringify({{ "status": "authenticated" }}));
    await browser.close();
}})();
""")
            
            proxy = self._get_random_proxy()
            output = self._run_script(script_path, proxy)
            result = self._extract_json(output)
            if result.get("status") != "authenticated":
                raise ScrapingError("Authentication failed")
                
            logger.info("Authentication successful", extra={
                "cookie_file": self.cookie_file,
                "has_proxy": bool(proxy)
            })
            
        except Exception as e:
            logger.error("Authentication failed", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc()
            })
            raise ScrapingError(f"Failed to authenticate with 8a.nu: {str(e)}")
        finally:
            if os.path.exists(script_path):
                os.remove(script_path)
    
    def get_ascents(self, target_slug: str) -> Dict[str, Any]:
        """Retrieve ascents data for the target slug using Playwright script."""
        logger.info(
            "Starting 8a.nu data fetch",
            extra={
                "target_slug": target_slug,
                "cookie_file": self.cookie_file
            }
        )
        
        if not self._current_credentials:
            raise ScrapingError("Not authenticated. Call authenticate() first")
            
        logger.info("Starting ascent retrieval", extra={
            "target_slug": target_slug,
            "cookie_file": self.cookie_file,
            "auth_retries": self._auth_retries,
            "current_delay": self._current_delay
        })
            
        # Validate cookie file and re-authenticate if necessary
        if not self._validate_cookie_file():
            logger.info(f"Cookie file is invalid or missing, re-authenticating...", extra={
                "cookie_file": self.cookie_file,
                "target_slug": target_slug
            })
            username, password = self._current_credentials
            self._initialize_cookie_file(username, password)
            
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
        userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0'
    }});
    const page = await context.newPage();
    
    const allAscents = [];
    const categories = ['sportclimbing', 'bouldering'];
    
    for (const category of categories) {{
        const categoryUrl = 'https://www.8a.nu/user/{target_slug}/' + category;
        await page.goto(categoryUrl, {{ timeout: 60000, waitUntil: 'domcontentloaded' }});
        await new Promise(resolve => setTimeout(resolve, 5000));
        
        let pageIndex = 0;
        let hasMorePages = true;
        
        while (hasMorePages) {{
            await new Promise(resolve => setTimeout(resolve, {self.MIN_DELAY * 1000}));
            
            const apiUrl = 'https://www.8a.nu/unificationAPI/ascent/v1/web/users/{target_slug}/ascents' +
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
            
            const response = await page.evaluate(async (url) => {{
                const res = await fetch(url, {{
                    method: 'GET',
                    headers: {{
                        'Accept': 'application/json',
                        'Referer': window.location.href,
                        'X-Requested-With': 'XMLHttpRequest'
                    }},
                    credentials: 'include'
                }});
                return {{ status: res.status, body: await res.text() }};
            }}, apiUrl);
            
            if (response.status === 429) {{
                throw new Error('Rate limit exceeded');
            }}
            
            if (response.status === 401 || response.status === 403) {{
                throw new Error('Authentication failed');
            }}
            
            let data = JSON.parse(response.body);
            const ascents = data.ascents || [];
            if (ascents.length === 0) {{
                hasMorePages = false;
                break;
            }}
            
            ascents.forEach(ascent => {{
                ascent.platform = 'eight_a';
                ascent.discipline = ascent.category === 0 ? 'sport' : 'boulder';
                delete ascent.category;
                allAscents.push(ascent);
            }});
            
            pageIndex++;
        }}
    }}
    
    console.log(JSON.stringify({{ 
        ascents: allAscents,
        totalItems: allAscents.length,
        pageIndex: 0
    }}));
    await browser.close();
}})();
""")
            
            proxy = self._get_random_proxy()
            try:
                output = self._run_script(script_path, proxy)
                data = self._extract_json(output)
                all_ascents = data.get("ascents", [])
                
                # Add detailed logging of raw data structure
                if all_ascents:
                    sample_ascent = all_ascents[0]
                    logger.info(
                        "Raw 8a.nu data structure",
                        extra={
                            "target_slug": target_slug,
                            "ascent_count": len(all_ascents),
                            "sample_ascent_keys": list(sample_ascent.keys()),
                            "sample_ascent": sample_ascent,
                            "categories": list(set(a.get('discipline', '') for a in all_ascents))
                        }
                    )
                else:
                    logger.warning(
                        "No ascents found in raw data",
                        extra={
                            "target_slug": target_slug,
                            "raw_data": data
                        }
                    )
                
                if not all_ascents:
                    raise ScrapingError("Failed to retrieve any ascents")
                    
                # Reset rate limit tracking on success
                self._reset_rate_limit()
                    
                logger.info(f"Successfully retrieved ascents", extra={
                    "target_slug": target_slug,
                    "ascent_count": len(all_ascents),
                    "categories": list(set(a.get('discipline', '') for a in all_ascents))
                })
                
                return {
                    "ascents": all_ascents,
                    "totalItems": len(all_ascents),
                    "pageIndex": 0,
                    "user_slug": target_slug
                }
            except ScrapingError as e:
                if "Rate limit exceeded" in str(e):
                    if self._rate_limit_retries < self.RETRY_ATTEMPTS:
                        self._handle_rate_limit()
                        # Retry the request
                        output = self._run_script(script_path, proxy)
                        data = self._extract_json(output)
                        all_ascents = data.get("ascents", [])
                        
                        if not all_ascents:
                            raise ScrapingError("Failed to retrieve any ascents after rate limit backoff")
                            
                        logger.info(f"Successfully retrieved ascents after rate limit backoff", extra={
                            "target_slug": target_slug,
                            "ascent_count": len(all_ascents),
                            "rate_limit_retries": self._rate_limit_retries,
                            "final_delay": self._current_delay
                        })
                        
                        return {
                            "ascents": all_ascents,
                            "totalItems": len(all_ascents),
                            "pageIndex": 0,
                            "user_slug": target_slug
                        }
                    else:
                        logger.error(f"Max rate limit retries exceeded", extra={
                            "max_attempts": self.RETRY_ATTEMPTS,
                            "target_slug": target_slug,
                            "final_delay": self._current_delay
                        })
                        raise ScrapingError(f"Max rate limit retries exceeded after {self.RETRY_ATTEMPTS} attempts")
                elif "Authentication failed" in str(e):
                    if self._auth_retries < self.RETRY_ATTEMPTS:
                        self._auth_retries += 1
                        logger.info(f"Session expired, re-authenticating", extra={
                            "attempt": self._auth_retries,
                            "max_attempts": self.RETRY_ATTEMPTS,
                            "target_slug": target_slug
                        })
                        # Re-authenticate with stored credentials
                        username, password = self._current_credentials
                        self._initialize_cookie_file(username, password)  # Re-initialize cookie file
                        # Retry the request
                        output = self._run_script(script_path, proxy)
                        data = self._extract_json(output)
                        all_ascents = data.get("ascents", [])
                        
                        if not all_ascents:
                            raise ScrapingError("Failed to retrieve any ascents after re-authentication")
                            
                        logger.info(f"Successfully retrieved ascents after re-authentication", extra={
                            "target_slug": target_slug,
                            "ascent_count": len(all_ascents),
                            "auth_retries": self._auth_retries
                        })
                        
                        return {
                            "ascents": all_ascents,
                            "totalItems": len(all_ascents),
                            "pageIndex": 0,
                            "user_slug": target_slug
                        }
                    else:
                        logger.error(f"Max authentication retries exceeded", extra={
                            "max_attempts": self.RETRY_ATTEMPTS,
                            "target_slug": target_slug
                        })
                        raise ScrapingError(f"Max authentication retries exceeded after {self.RETRY_ATTEMPTS} attempts")
                raise
            
        except Exception as e:
            logger.error("Ascent retrieval failed", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc(),
                "target_slug": target_slug
            })
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