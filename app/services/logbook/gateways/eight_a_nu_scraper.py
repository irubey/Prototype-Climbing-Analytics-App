"""
8a.nu scraping service.

This module provides functionality for:
- Authenticating with 8a.nu
- Scraping climbing ascent data
- Processing user profiles
- Managing API interactions
"""

# Standard library imports
from typing import Optional, Dict, Any, List
import asyncio
import signal
import sys
import random
import urllib.parse

# Third-party imports
from playwright.async_api import (
    async_playwright,
    Browser,
    Page,
    Playwright
)

# Application imports
from app.core.logging import logger
from app.core.exceptions import ScrapingError

class EightANuClient:
    """Playwright-based client for 8a.nu that handles authentication and data retrieval."""
    
    BASE_URL = "https://www.8a.nu"
    LOGIN_URL = f"{BASE_URL}/login"
    ASCENTS_API_ENDPOINT = f"{BASE_URL}/unificationAPI/ascent/v1/web/users"
    
    def __init__(self, proxy_list: Optional[List[str]] = None):
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self._user_slug: Optional[str] = None
        self.playwright: Optional[Playwright] = None
        self.proxy_list = proxy_list or []
        self._setup_signal_handlers()
        
    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        if sys.platform != "win32":  # SIGTERM is not supported on Windows
            signal.signal(signal.SIGTERM, lambda *_: asyncio.create_task(self._cleanup()))
        signal.signal(signal.SIGINT, lambda *_: asyncio.create_task(self._cleanup()))
        
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
        
    async def __aenter__(self):
        """Async context manager entry with enhanced process management."""
        try:
            self.playwright = await async_playwright().start()
            
            # Get random proxy if available
            proxy_settings = self._get_random_proxy()
            
            # Launch browser with proxy if configured
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox'],
                proxy=proxy_settings if proxy_settings else None
            )
            
            # Create context with additional anti-bot settings
            context = await self.browser.new_context(
                viewport={'width': 1920 + random.randint(-50, 50), 'height': 1080 + random.randint(-50, 50)},
                user_agent=random.choice([
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/123.0"
                ]),
                locale="en-US,en;q=0.9",
                timezone_id="America/New_York"
            )
            
            self.page = await context.new_page()
            return self
            
        except Exception as e:
            await self._cleanup()
            raise ScrapingError(f"Failed to initialize browser: {str(e)}")
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with enhanced cleanup."""
        await self._cleanup()
            
    async def _cleanup(self):
        """Explicit cleanup method to ensure all processes are terminated."""
        try:
            if self.page:
                try:
                    await asyncio.wait_for(self.page.close(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("Timeout while closing page, proceeding with cleanup")
                self.page = None
                
            if self.browser:
                try:
                    await asyncio.wait_for(self.browser.close(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("Timeout while closing browser, proceeding with cleanup")
                self.browser = None
                
            if self.playwright:
                try:
                    await asyncio.wait_for(self.playwright.stop(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("Timeout while stopping playwright, proceeding with cleanup")
                self.playwright = None
                
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
        finally:
            # Ensure all references are cleared even if exceptions occur
            self.page = None
            self.browser = None
            self.playwright = None
            
    async def authenticate(self, username: str, password: str) -> None:
        """Authenticate with 8a.nu using provided credentials."""
        try:
            await self.page.goto(self.LOGIN_URL)
            
            # Wait for and fill login form
            await self.page.wait_for_selector('input[type="email"]')
            await self.page.fill('input[type="email"]', username)
            await self.page.fill('input[type="password"]', password)
            
            # Click login button and wait for navigation
            await self.page.click('button[type="submit"]')
            
            # Wait for successful login indication (redirect or specific element)
            await self.page.wait_for_url(f"{self.BASE_URL}/**")
            
            # Extract user slug from profile URL or API call
            self._user_slug = await self._extract_user_slug()
            
            logger.info("Successfully authenticated with 8a.nu")
            
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            raise ScrapingError(f"Failed to authenticate with 8a.nu: {str(e)}")
            
    async def _extract_user_slug(self) -> str:
        """Extract user slug from profile page or API response."""
        try:
            # After login, we should be redirected to the user's profile page
            # Wait a bit for the session to establish
            await asyncio.sleep(2)
            
            # First try to get it from the profile image wrapper
            try:
                profile_link = await self.page.wait_for_selector('.profile-img-wrapper a[href^="/user/"]', timeout=5000)
                if profile_link:
                    href = await profile_link.get_attribute('href')
                    logger.info(f"Found profile link with href: {href}")
                    if href and href.startswith('/user/'):
                        self._user_slug = href.split('/user/')[1].split('/')[0]
                        logger.info(f"Successfully extracted user slug: {self._user_slug}")
                        # Log the full element for debugging
                        element_html = await self.page.evaluate('(element) => element.outerHTML', profile_link)
                        logger.info(f"Found element HTML: {element_html}")
                        return self._user_slug
            except Exception as e:
                logger.warning(f"Could not extract slug from profile link: {str(e)}")
            
            # Try to get it from the URL as backup
            current_url = self.page.url
            if "/user/" in current_url:
                self._user_slug = current_url.split("/user/")[-1].split("/")[0]
                logger.info(f"Extracted user slug from URL: {self._user_slug}")
                return self._user_slug
            
            # If all attempts fail
            raise ScrapingError("Could not extract user slug from any source")
            
        except Exception as e:
            logger.error(f"Failed to extract user slug: {str(e)}")
            raise ScrapingError(f"Failed to extract user slug: {str(e)}")
        
    async def get_ascents(self) -> Dict[str, Any]:
        """Retrieve all ascents data from 8a.nu API for both sport climbing and bouldering."""
        if not self._user_slug:
            raise ScrapingError("Not authenticated. Call authenticate() first")
            
        try:
            all_ascents = []
            categories = ["sportclimbing", "bouldering"]
            success = False
            
            # Set required headers with randomized values
            await self.page.set_extra_http_headers({
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'no-cors',
                'Sec-Fetch-Site': 'same-origin',
                'TE': 'trailers'
            })
            
            # Set default cookies
            await self.page.add_init_script("""
                document.cookie = "i18n_redirected=en; path=/";
                document.cookie = "color-value=dark; path=/";
            """)
            
            for category in categories:
                page_index = 0
                while True:
                    try:
                        # Add random delay between requests (1-3 seconds)
                        await asyncio.sleep(random.uniform(1, 3))
                        
                        # Rotate proxy if available
                        if self.proxy_list:
                            proxy_settings = self._get_random_proxy()
                            if proxy_settings:
                                # Create new context with new proxy
                                context = await self.browser.new_context(
                                    proxy=proxy_settings,
                                    viewport={'width': 1920 + random.randint(-50, 50), 'height': 1080 + random.randint(-50, 50)},
                                    user_agent=random.choice([
                                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
                                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/123.0"
                                    ])
                                )
                                self.page = await context.new_page()
                        
                        # Construct API URL with current page index
                        api_url = f"{self.ASCENTS_API_ENDPOINT}/{self._user_slug}/ascents"
                        params = {
                            "category": category,
                            "pageIndex": page_index,
                            "pageSize": 50,
                            "sortField": "date_desc",
                            "timeFilter": 0,
                            "gradeFilter": 0,
                            "typeFilter": "",
                            "includeProjects": "false",
                            "searchQuery": "",
                            "showRepeats": "false",
                            "showDuplicates": "false"
                        }
                        
                        # Set the referer for this specific request
                        await self.page.set_extra_http_headers({
                            'Referer': f'{self.BASE_URL}/user/{self._user_slug}/{category}'
                        })
                        
                        # Make API request using Playwright with timeout
                        async with asyncio.timeout(30):  # 30 second timeout
                            response = await self.page.goto(
                                f"{api_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
                            )
                            
                            if not response:
                                raise ScrapingError("No response received from API")
                                
                            if response.status != 200:
                                logger.error(f"API request failed with status {response.status}")
                                logger.error(f"Response headers: {response.headers}")
                                logger.error(f"Current cookies: {await self.page.context.cookies()}")
                                raise ScrapingError(f"API request failed with status {response.status}")
                            
                            # Parse JSON response
                            data = await response.json()
                            page_ascents = data.get("ascents", [])
                            
                            # Break if no more ascents on this page
                            if not page_ascents:
                                logger.info(f"No more {category} ascents found after page {page_index}")
                                break
                            
                            # Add platform field and transform category to discipline for each ascent
                            for ascent in page_ascents:
                                ascent["platform"] = "eight_a"
                                # Transform category (0/1) to discipline (sport/boulder)
                                discipline = "sport" if ascent.get("category") == 0 else "boulder"
                                ascent["discipline"] = discipline
                                # Remove the original category field
                                ascent.pop("category", None)
                            
                            all_ascents.extend(page_ascents)
                            success = True  # Mark that we got at least some data
                            logger.info(f"Fetched {category} page {page_index}, got {len(page_ascents)} ascents")
                            
                            page_index += 1
                            
                    except asyncio.TimeoutError:
                        logger.error(f"Timeout while fetching page {page_index} for {category}")
                        break
                    except Exception as e:
                        logger.error(f"Error fetching page {page_index} for {category}: {str(e)}")
                        break
            
            if not success:
                raise ScrapingError("Failed to retrieve any ascents from 8a.nu")
            
            return {
                "ascents": all_ascents,
                "totalItems": len(all_ascents),
                "pageIndex": 0
            }
            
        except Exception as e:
            logger.error(f"Failed to retrieve ascents: {str(e)}")
            raise ScrapingError(f"Failed to retrieve ascents from 8a.nu: {str(e)}")

#TODO: Add Proxy List for Production
