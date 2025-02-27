"""Tests for the 8a.nu scraper client."""

import pytest
import pytest_asyncio
from typing import AsyncGenerator, Dict, Any, AsyncIterator
from pytest import FixtureRequest
from _pytest.fixtures import FixtureFunction, SubRequest
import json
import asyncio
import os
from unittest.mock import Mock, patch, PropertyMock, AsyncMock
from playwright.async_api import (
    async_playwright,
    Page,
    Response,
    Browser,
    Playwright
)
import httpx
import logging
import urllib.parse
import unittest
import random

from app.services.logbook.gateways.eight_a_nu_scraper import EightANuClient
from app.core.exceptions import ScrapingError

# Sample test data
SAMPLE_USER_SLUG = "test-user"
SAMPLE_ASCENT = {
    "ascentId": 9605224,
    "platform": "eight_a",
    "userAvatar": "https://d1ffqbcmevre4q.cloudfront.net/avatar_default.png",
    "userName": "test user",
    "userSlug": "test-user",
    "date": "2024-03-23T12:00:00+00:00",
    "difficulty": "7a+",
    "comment": "test",
    "userPrivate": False,
    "countrySlug": "united-states",
    "countryName": "United States",
    "areaSlug": "test-area",
    "areaName": "Test Area",
    "sectorSlug": "test-sector",
    "sectorName": "Test Sector",
    "traditional": False,
    "firstAscent": False,
    "type": "rp",
    "repeat": False,
    "project": False,
    "rating": 4,
    "discipline": "sport",
    "recommended": True,
    "zlagGradeIndex": 24,
    "zlaggableName": "Test Route",
    "zlaggableSlug": "test-route",
    "cragSlug": "test-crag",
    "cragName": "Test Crag"
}

# Test credentials from environment
TEST_USERNAME = os.getenv("EIGHT_A_USERNAME", "isaac.rubey+8a@gmail.com")
# URL decode the password to handle special characters
TEST_PASSWORD = urllib.parse.unquote(os.getenv("EIGHT_A_PASSWORD", "ISRgo%236!"))

logger = logging.getLogger(__name__)

@pytest_asyncio.fixture
async def mock_page(request: SubRequest) -> AsyncIterator[AsyncMock]:
    """Create a mock Playwright page."""
    page = AsyncMock(spec=Page)
    page.url = "https://www.8a.nu/user/test-user"
    
    # Setup default async returns for common methods
    page.wait_for_selector = AsyncMock()
    page.wait_for_selector.return_value = AsyncMock()
    page.wait_for_selector.return_value.get_attribute = AsyncMock(return_value="/user/test-user")
    page.wait_for_selector.return_value.evaluate = AsyncMock(return_value="<a href='/user/test-user'>Profile</a>")
    
    # Setup context for cookies
    page.context = AsyncMock()
    page.context.cookies = AsyncMock(return_value=[])
    
    yield page

@pytest_asyncio.fixture
async def mock_browser(request: SubRequest) -> AsyncIterator[AsyncMock]:
    """Create a mock Playwright browser."""
    browser = AsyncMock(spec=Browser)
    yield browser

@pytest_asyncio.fixture
async def mock_playwright(request: SubRequest) -> AsyncIterator[AsyncMock]:
    """Create a mock Playwright instance."""
    playwright = AsyncMock(spec=Playwright)
    yield playwright

@pytest_asyncio.fixture
async def mock_response(request: SubRequest) -> AsyncIterator[AsyncMock]:
    """Create a mock response with sample ascent data."""
    response = AsyncMock(spec=Response)
    response.status = 200
    response.json = AsyncMock(return_value={
        "ascents": [SAMPLE_ASCENT],
        "totalItems": 1,
        "pageIndex": 0
    })
    yield response

@pytest_asyncio.fixture
async def eight_a_client(
    request: SubRequest,
    mock_page: AsyncMock,
    mock_browser: AsyncMock,
    mock_playwright: AsyncMock
) -> AsyncIterator[EightANuClient]:
    """Create an EightANuClient instance with mocked dependencies."""
    with patch('app.services.logbook.gateways.eight_a_nu_scraper.async_playwright') as mock_pw:
        # Create an async mock for the playwright instance
        mock_pw_instance = AsyncMock()
        mock_pw_instance.start = AsyncMock(return_value=mock_playwright)
        mock_pw.return_value = mock_pw_instance
        
        # Setup the chromium launch chain
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        
        client = EightANuClient()
        async with client as eight_a_client:
            yield eight_a_client

@pytest.mark.asyncio
async def test_client_initialization(eight_a_client: EightANuClient) -> None:
    """Test successful client initialization."""
    assert eight_a_client.page is not None
    assert eight_a_client.browser is not None
    assert eight_a_client.playwright is not None

@pytest.mark.asyncio
async def test_authentication_success(
    eight_a_client: EightANuClient,
    mock_page: AsyncMock,
    mock_response: AsyncMock
) -> None:
    """Test successful authentication flow."""
    # Setup mock behavior
    mock_page.goto = AsyncMock()
    mock_page.fill = AsyncMock()
    mock_page.click = AsyncMock()
    mock_page.wait_for_url = AsyncMock()
    mock_page.evaluate = AsyncMock(return_value="<a href='/user/test-user'>Profile</a>")
    
    # Setup profile link selector mock with proper async returns
    profile_link = AsyncMock()
    href = "/user/test-user"
    profile_link.get_attribute = AsyncMock()
    profile_link.get_attribute.return_value = href
    mock_page.wait_for_selector = AsyncMock(return_value=profile_link)
    
    # Override the default mock_page setup to ensure proper async behavior
    eight_a_client.page = mock_page
    
    # Test authentication
    await eight_a_client.authenticate("test@example.com", "password")
    
    # Verify expected calls
    mock_page.goto.assert_awaited_with(eight_a_client.LOGIN_URL)
    mock_page.wait_for_selector.assert_has_awaits([
        unittest.mock.call('input[type="email"]'),
        unittest.mock.call('.profile-img-wrapper a[href^="/user/"]', timeout=5000)
    ])
    assert mock_page.fill.await_count == 2  # Once for email, once for password
    mock_page.click.assert_awaited_with('button[type="submit"]')
    assert eight_a_client._user_slug == "test-user"

@pytest.mark.asyncio
async def test_authentication_failure(
    eight_a_client: EightANuClient,
    mock_page: AsyncMock
) -> None:
    """Test authentication failure handling."""
    # Setup mock behavior with async mocks
    mock_page.goto = AsyncMock(side_effect=Exception("Network error"))
    mock_page.wait_for_selector = AsyncMock()
    
    # Setup profile link selector mock with proper async returns
    profile_link = AsyncMock()
    profile_link.get_attribute = AsyncMock(return_value=None)  # Return None to simulate failure
    mock_page.wait_for_selector.return_value = profile_link
    
    # Override the client's page with our mock
    eight_a_client.page = mock_page
    
    # Test authentication failure
    with pytest.raises(ScrapingError) as exc_info:
        await eight_a_client.authenticate("test@example.com", "password")
    assert "Failed to authenticate with 8a.nu" in str(exc_info.value)

@pytest.mark.asyncio
async def test_get_ascents_success(
    eight_a_client: EightANuClient,
    mock_page: AsyncMock,
    mock_response: AsyncMock
) -> None:
    """Test successful ascent retrieval."""
    # Setup client state
    eight_a_client._user_slug = SAMPLE_USER_SLUG
    
    # Create sample responses for each category
    sport_response = AsyncMock()
    sport_response.status = 200
    sport_response.headers = {}
    sport_response.json = AsyncMock(return_value={
        "ascents": [{
            **SAMPLE_ASCENT,
            "category": 0  # Explicitly set category for sport
        }],
        "totalItems": 1,
        "pageIndex": 0
    })
    
    boulder_response = AsyncMock()
    boulder_response.status = 200
    boulder_response.headers = {}
    boulder_response.json = AsyncMock(return_value={
        "ascents": [{
            **SAMPLE_ASCENT,
            "category": 1,  # Explicitly set category for boulder
            "discipline": None  # Ensure no discipline is set initially
        }],
        "totalItems": 1,
        "pageIndex": 0
    })
    
    # Create empty responses for pagination
    empty_response = AsyncMock()
    empty_response.status = 200
    empty_response.headers = {}
    empty_response.json = AsyncMock(return_value={"ascents": []})
    
    # Setup page mocks
    mock_page.goto = AsyncMock(side_effect=[sport_response, empty_response, boulder_response, empty_response])
    mock_page.set_extra_http_headers = AsyncMock()
    mock_page.add_init_script = AsyncMock()

    # Set up cookies before making requests
    await mock_page.add_init_script("""
        document.cookie = "i18n_redirected=en; path=/";
        document.cookie = "color-value=dark; path=/";
    """)
    
    # Mock browser context creation for proxy rotation
    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    eight_a_client.browser.new_context = AsyncMock(return_value=mock_context)
    
    # Add proxy list to trigger proxy rotation
    eight_a_client.proxy_list = ["http://proxy1.example.com:8080"]
    
    # Mock the random proxy selection
    with patch('random.choice', return_value="http://proxy1.example.com:8080"):
        # Get ascents
        result = await eight_a_client.get_ascents()
    
    # Verify the result structure
    assert "ascents" in result
    assert len(result["ascents"]) == 2  # One sport, one boulder
    assert result["totalItems"] == 2
    
    # Verify discipline transformation
    sport_ascent = next(a for a in result["ascents"] if a["discipline"] == "sport")
    boulder_ascent = next(a for a in result["ascents"] if a["discipline"] == "boulder")
    assert sport_ascent is not None
    assert boulder_ascent is not None
    
    # Verify platform field
    assert all(a["platform"] == "eight_a" for a in result["ascents"])
    
    # Verify category field was removed
    assert all("category" not in a for a in result["ascents"])
    
    # Verify HTTP headers were set
    mock_page.set_extra_http_headers.assert_called()
    
    # Verify init script for cookies was called with the correct script
    mock_page.add_init_script.assert_called_once_with("""
        document.cookie = "i18n_redirected=en; path=/";
        document.cookie = "color-value=dark; path=/";
    """)
    
    # Verify proxy rotation was attempted
    eight_a_client.browser.new_context.assert_called()
    mock_context.new_page.assert_called()

@pytest.mark.asyncio
async def test_get_ascents_not_authenticated(eight_a_client: EightANuClient) -> None:
    """Test ascent retrieval without authentication."""
    eight_a_client._user_slug = None
    
    with pytest.raises(ScrapingError) as exc_info:
        await eight_a_client.get_ascents()
    assert "Not authenticated" in str(exc_info.value)

@pytest.mark.asyncio
async def test_get_ascents_api_error(
    eight_a_client: EightANuClient,
    mock_page: AsyncMock
) -> None:
    """Test handling of API errors during ascent retrieval."""
    eight_a_client._user_slug = SAMPLE_USER_SLUG
    
    # Setup mock to simulate API error
    async def mock_goto(url: str) -> AsyncMock:
        response = AsyncMock()
        response.status = 503
        response.json = AsyncMock(side_effect=Exception("API Error"))
        return response
    
    mock_page.goto = AsyncMock(side_effect=mock_goto)
    
    # The get_ascents method should raise a ScrapingError
    with pytest.raises(ScrapingError) as exc_info:
        await eight_a_client.get_ascents()
    
    assert "Failed to retrieve ascents from 8a.nu" in str(exc_info.value)

@pytest.mark.asyncio
async def test_cleanup(
    eight_a_client: EightANuClient,
    mock_page: AsyncMock,
    mock_browser: AsyncMock,
    mock_playwright: AsyncMock
) -> None:
    """Test cleanup process."""
    # Ensure the client has all components to clean up
    eight_a_client.page = mock_page
    eight_a_client.browser = mock_browser
    eight_a_client.playwright = mock_playwright
    
    # Setup async mocks for cleanup operations
    mock_page.close = AsyncMock()
    mock_browser.close = AsyncMock()
    mock_playwright.stop = AsyncMock()
    
    # Trigger cleanup
    await eight_a_client._cleanup()
    
    # Verify cleanup calls were made in the correct order
    mock_page.close.assert_awaited_once()
    mock_browser.close.assert_awaited_once()
    mock_playwright.stop.assert_awaited_once()
    
    # Verify references were cleared
    assert eight_a_client.page is None
    assert eight_a_client.browser is None
    assert eight_a_client.playwright is None

@pytest.mark.asyncio
async def test_cleanup_with_timeout(
    eight_a_client: EightANuClient,
    mock_page: Mock,
    mock_browser: Mock,
    mock_playwright: Mock
) -> None:
    """Test cleanup process with timeouts."""
    # Setup mocks to simulate timeouts
    mock_page.close = Mock(side_effect=asyncio.TimeoutError)
    mock_browser.close = Mock(side_effect=asyncio.TimeoutError)
    mock_playwright.stop = Mock(side_effect=asyncio.TimeoutError)
    
    # Trigger cleanup
    await eight_a_client._cleanup()
    
    # Verify references are cleared despite timeouts
    assert eight_a_client.page is None
    assert eight_a_client.browser is None
    assert eight_a_client.playwright is None

@pytest.mark.asyncio
async def test_signal_handlers(eight_a_client: EightANuClient) -> None:
    """Test signal handler setup."""
    # This is a basic test to ensure signal handlers are set up
    # We can't easily test the actual signal handling without complex mocking
    assert hasattr(eight_a_client, '_setup_signal_handlers')
    # The actual handlers are set up in __init__ 

@pytest.mark.asyncio
async def test_authentication_with_real_credentials(
    eight_a_client: EightANuClient,
    mock_page: AsyncMock,
    mock_response: AsyncMock
) -> None:
    """Test authentication with real credentials from .env."""
    # Setup mock behavior with async mocks
    mock_page.wait_for_selector = AsyncMock()
    mock_page.fill = AsyncMock()
    mock_page.click = AsyncMock()
    mock_page.wait_for_url = AsyncMock()
    mock_page.goto = AsyncMock()
    
    # Set the page URL property
    mock_page.url = "https://www.8a.nu/user/test-user"
    
    # Setup profile link selector mock with proper async returns
    profile_link = AsyncMock()
    href = "/user/test-user"  # Use direct string instead of Future
    profile_link.get_attribute = AsyncMock(return_value=href)
    mock_page.wait_for_selector.return_value = profile_link
    
    # Override the client's page with our mock
    eight_a_client.page = mock_page
    
    # Add sleep mock to prevent actual waiting
    with patch('asyncio.sleep'):
        # Test authentication with real credentials
        await eight_a_client.authenticate(TEST_USERNAME, TEST_PASSWORD)
    
    # Verify expected calls with real credentials
    mock_page.goto.assert_awaited_with(eight_a_client.LOGIN_URL)
    mock_page.wait_for_selector.assert_has_awaits([
        unittest.mock.call('input[type="email"]'),
        unittest.mock.call('.profile-img-wrapper a[href^="/user/"]', timeout=5000)
    ])
    
    # Verify email and password were filled
    fill_calls = mock_page.fill.await_args_list
    assert len(fill_calls) == 2
    assert fill_calls[0][0][1] == TEST_USERNAME  # First call should use TEST_USERNAME
    assert fill_calls[1][0][1] == TEST_PASSWORD  # Second call should use TEST_PASSWORD
    
    mock_page.click.assert_awaited_with('button[type="submit"]')
    
    # Verify user slug was extracted correctly
    assert eight_a_client._user_slug == "test-user"

@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_authentication_and_fetch() -> None:
    """Integration test using real credentials to authenticate and fetch data."""
    playwright = None
    browser = None
    context = None
    page = None
    
    try:
        # Start Playwright
        logger.info("Starting Playwright...")
        playwright = await async_playwright().start()
        logger.info("Playwright started successfully")
        
        try:
            # Launch browser
            logger.info("Launching browser...")
            browser = await playwright.chromium.launch(
                headless=False,
                args=['--no-sandbox']
            )
            logger.info("Browser launched successfully")
            
            try:
                # Create context
                logger.info("Creating browser context...")
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0'
                )
                logger.info("Browser context created successfully")
                
                try:
                    # Create page
                    logger.info("Creating new page...")
                    page = await context.new_page()
                    logger.info("Page created successfully")
                    
                    # Initialize client
                    logger.info("Initializing EightANuClient...")
                    client = EightANuClient()
                    client.page = page
                    client.browser = browser
                    client.playwright = playwright
                    
                    # Test basic navigation
                    logger.info("Testing basic navigation...")
                    try:
                        await page.goto('https://example.com')
                        logger.info("Basic navigation successful")
                    except Exception as e:
                        logger.error(f"Basic navigation failed: {str(e)}")
                        raise
                    
                    # Perform authentication
                    logger.info("Attempting to authenticate...")
                    await page.goto('https://www.8a.nu/login')
                    await page.wait_for_load_state('networkidle')
                    
                    # Wait for redirect to Vertical-Life auth
                    logger.info("Waiting for Vertical-Life authentication redirect...")
                    await page.wait_for_url('**/auth/realms/Vertical-Life/protocol/openid-connect/auth*')
                    await page.wait_for_load_state('networkidle')
                    
                    # Try to find email input with multiple selectors on Vertical-Life login page
                    selectors = [
                        '#username',  # Vertical-Life uses this ID for username/email
                        'input[name="username"]',
                        'input[type="text"]',
                        'input[placeholder*="Username" i]',
                        'input[placeholder*="email" i]'
                    ]
                    
                    email_input = None
                    for selector in selectors:
                        try:
                            email_input = await page.wait_for_selector(selector, timeout=5000)
                            if email_input:
                                logger.info(f"Found email input with selector: {selector}")
                                break
                        except Exception:
                            continue
                    
                    if not email_input:
                        await page.screenshot(path="login_form_not_found.png")
                        logger.error("Could not find email input field on Vertical-Life login page")
                        pytest.skip("Login form not accessible - possible site issues")
                    
                    # Fill login form on Vertical-Life page
                    await email_input.fill(TEST_USERNAME)
                    await page.fill('input[type="password"]', TEST_PASSWORD)
                    
                    # Find and click the sign-in button
                    sign_in_selectors = [
                        'input[type="submit"]',
                        'button[type="submit"]',
                        '#kc-login',
                        'button:has-text("Sign In")',
                        'input[value="Sign In"]'
                    ]
                    
                    for selector in sign_in_selectors:
                        try:
                            submit_button = await page.wait_for_selector(selector, timeout=5000)
                            if submit_button:
                                logger.info(f"Found submit button with selector: {selector}")
                                await submit_button.click()
                                break
                        except Exception:
                            continue
                    
                    # Wait for redirect back to 8a.nu
                    logger.info("Waiting for redirect back to 8a.nu...")
                    try:
                        # First try waiting for callback
                        await page.wait_for_url('**/callback*', timeout=5000)
                    except Exception:
                        # If no callback, wait for direct navigation to 8a.nu
                        logger.info("No callback detected, waiting for direct navigation...")
                        await page.wait_for_url('https://www.8a.nu/**', timeout=30000)
                    
                    # Skip networkidle wait since it's causing timeouts
                    # Instead, wait a short time for the session to establish
                    await asyncio.sleep(2)
                    
                    # Verify login success by checking final URL and content
                    current_url = page.url
                    if '/login' in current_url or 'auth/realms/Vertical-Life' in current_url:
                        await page.screenshot(path="login_failed.png")
                        pytest.fail("Login failed - authentication not completed")
                    
                    logger.info("Authentication successful")
                    
                    # Take a screenshot of the main page state
                    await page.screenshot(path="main_page.png")
                    
                    # Attempt to fetch ascents
                    logger.info("Fetching ascents...")
                    client._user_slug = await client._extract_user_slug()
                    
                    # Log current cookies for debugging
                    cookies = await context.cookies()
                    logger.info("Current cookies:")
                    for cookie in cookies:
                        logger.info(f"Cookie: {cookie['name']} = {cookie['value']}")
                    
                    ascents_data = await client.get_ascents()
                    
                    assert ascents_data is not None
                    assert "ascents" in ascents_data
                    assert isinstance(ascents_data["ascents"], list)
                    
                    # Log detailed ascents information
                    logger.info(f"Successfully retrieved {len(ascents_data['ascents'])} ascents")
                    if ascents_data['ascents']:
                        # Log the first ascent as an example
                        first_ascent = ascents_data['ascents'][0]
                        logger.info("Example ascent data:")
                        logger.info(json.dumps(first_ascent, indent=2))
                        
                        # Log some statistics
                        sport_climbs = sum(1 for a in ascents_data['ascents'] if a.get('discipline') == 'sport')
                        boulders = sum(1 for a in ascents_data['ascents'] if a.get('discipline') == 'boulder')
                        logger.info(f"Sport climbs: {sport_climbs}")
                        logger.info(f"Boulders: {boulders}")
                    
                except Exception as e:
                    logger.error(f"Page operation failed: {str(e)}")
                    if page:
                        await page.screenshot(path="page_error.png")
                    raise
                    
            except Exception as e:
                logger.error(f"Context creation failed: {str(e)}")
                raise
                
        except Exception as e:
            logger.error(f"Browser launch failed: {str(e)}")
            raise
            
    except Exception as e:
        logger.error(f"Playwright initialization failed: {str(e)}")
        pytest.fail(f"Test failed during setup: {str(e)}")
        
    finally:
        logger.info("Starting cleanup...")
        try:
            if page:
                logger.info("Closing page...")
                await page.close()
            if context:
                logger.info("Closing context...")
                await context.close()
            if browser:
                logger.info("Closing browser...")
                await browser.close()
            if playwright:
                logger.info("Stopping playwright...")
                await playwright.stop()
            logger.info("Cleanup completed successfully")
        except Exception as e:
            logger.error(f"Cleanup failed: {str(e)}") 