"""
External service fixtures for testing.

This module provides fixtures for mocking external service integrations,
including OpenAI, Mountain Project API, and other third-party services.
"""

import pytest
import pytest_asyncio
from typing import AsyncGenerator, Dict, Any, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch
import json
from pathlib import Path

from app.tests.config import test_settings


@pytest_asyncio.fixture
async def mock_openai() -> AsyncGenerator[AsyncMock, None]:
    """
    Provide a mocked OpenAI client for testing.
    
    This fixture creates a mock of the OpenAI client that can be
    configured by tests to return specific responses.
    """
    mock_client = AsyncMock()
    
    # Mock the chat completion method
    chat_completion_response = MagicMock()
    chat_completion_response.choices = [MagicMock()]
    chat_completion_response.choices[0].message.content = "This is a mock response from OpenAI."
    chat_completion_response.usage.prompt_tokens = 150
    chat_completion_response.usage.completion_tokens = 50
    chat_completion_response.usage.total_tokens = 200
    mock_client.chat.completions.create.return_value = chat_completion_response
    
    # Mock the embeddings method
    embedding_response = MagicMock()
    embedding_response.data = [{"embedding": [0.1] * 1536}]
    mock_client.embeddings.create.return_value = embedding_response
    
    with patch("openai.AsyncClient", return_value=mock_client):
        yield mock_client


@pytest_asyncio.fixture
async def mock_weather_api() -> AsyncGenerator[AsyncMock, None]:
    """
    Provide a mocked weather API client for testing.
    
    This fixture creates a mock of a weather API client that returns
    preconfigured weather data.
    """
    mock_client = AsyncMock()
    
    # Configure default response for get_forecast
    mock_client.get_forecast.return_value = {
        "location": {
            "name": "Boulder",
            "region": "Colorado",
            "country": "USA",
            "lat": 40.0,
            "lon": -105.3,
            "localtime": "2023-07-15 14:30"
        },
        "current": {
            "temp_c": 28.5,
            "temp_f": 83.3,
            "condition": {
                "text": "Partly cloudy",
                "icon": "//cdn.weatherapi.com/weather/64x64/day/116.png"
            },
            "wind_mph": 5.6,
            "wind_kph": 9.0,
            "precip_mm": 0.0,
            "humidity": 25,
            "uv": 7.0
        },
        "forecast": {
            "forecastday": [
                {
                    "date": "2023-07-15",
                    "day": {
                        "maxtemp_c": 32.5,
                        "maxtemp_f": 90.5,
                        "mintemp_c": 15.2,
                        "mintemp_f": 59.4,
                        "condition": {
                            "text": "Sunny",
                            "icon": "//cdn.weatherapi.com/weather/64x64/day/113.png"
                        },
                        "daily_chance_of_rain": 0,
                        "daily_chance_of_snow": 0
                    },
                    "astro": {
                        "sunrise": "05:45 AM",
                        "sunset": "08:30 PM"
                    },
                    "hour": []
                }
            ]
        }
    }
    
    yield mock_client


@pytest_asyncio.fixture
async def mock_mp_client() -> AsyncGenerator[AsyncMock, None]:
    """
    Provide a mocked Mountain Project client for testing.
    
    This fixture creates a mock of the Mountain Project client
    that returns preconfigured climbing data.
    """
    mock_client = AsyncMock()
    
    # Configure default response for get_ticks
    mock_client.get_ticks.return_value = [
        {
            "route_id": "1234",
            "route_name": "Test Route",
            "date": "2023-05-15",
            "style": "Lead",
            "lead_style": "Onsight",
            "route_type": "Sport",
            "grade": "5.10a",
            "stars": 3,
            "pitches": 1,
            "notes": "Great climb!"
        },
        {
            "route_id": "5678",
            "route_name": "Another Test Route",
            "date": "2023-05-14",
            "style": "TR",
            "lead_style": None,
            "route_type": "Sport",
            "grade": "5.11b",
            "stars": 4,
            "pitches": 1,
            "notes": ""
        }
    ]
    
    # Configure default response for get_routes
    mock_client.get_routes.return_value = [
        {
            "id": "1234",
            "name": "Test Route",
            "type": "Sport",
            "rating": "5.10a",
            "stars": 3.0,
            "starVotes": 100,
            "pitches": 1,
            "location": ["Colorado", "Boulder", "Flatirons"],
            "url": "https://www.mountainproject.com/route/1234",
            "longitude": -105.292,
            "latitude": 39.992
        },
        {
            "id": "5678",
            "name": "Another Test Route",
            "type": "Sport",
            "rating": "5.11b",
            "stars": 4.0,
            "starVotes": 200,
            "pitches": 1,
            "location": ["Colorado", "Boulder", "Flatirons"],
            "url": "https://www.mountainproject.com/route/5678",
            "longitude": -105.293,
            "latitude": 39.993
        }
    ]
    
    # Configure default response for get_user_info
    mock_client.get_user_info.return_value = {
        "username": "TestUser",
        "member_since": "2018-01-15",
        "location": "Boulder, CO",
        "favorite_areas": ["Flatirons", "Eldorado Canyon", "Boulder Canyon"],
        "total_ticks": 250
    }
    
    with patch("app.services.clients.mountain_project.MPClient", return_value=mock_client):
        yield mock_client


@pytest_asyncio.fixture
async def mock_eight_a_nu_client() -> AsyncGenerator[AsyncMock, None]:
    """
    Provide a mocked 8a.nu client for testing.
    
    This fixture creates a mock of the 8a.nu client that returns
    preconfigured bouldering data.
    """
    mock_client = AsyncMock()
    
    # Configure default response for get_ascents
    mock_client.get_ascents.return_value = [
        {
            "climb_id": "boulder_1",
            "name": "Test Boulder Problem",
            "grade": "V5",
            "date": "2023-06-01",
            "style": "Flash",
            "area": "Bishop",
            "subarea": "Buttermilks",
            "notes": "Amazing problem!"
        },
        {
            "climb_id": "boulder_2",
            "name": "Another Test Problem",
            "grade": "V7",
            "date": "2023-05-20",
            "style": "Send",
            "area": "Joe's Valley",
            "subarea": "New Joe's",
            "notes": "Crimpy and technical"
        }
    ]
    
    # Configure default response for get_user_profile
    mock_client.get_user_profile.return_value = {
        "username": "boulderTester",
        "member_since": "2019-03-10",
        "location": "Boulder, CO",
        "top_grade": "V8",
        "total_ascents": 120
    }
    
    yield mock_client


@pytest_asyncio.fixture
async def mock_stripe_client() -> AsyncGenerator[MagicMock, None]:
    """
    Provide a mocked Stripe client for testing.
    
    This fixture creates a mock of the Stripe client that can be
    configured by tests to return specific values for payment processing.
    """
    mock_client = MagicMock()
    
    # Configure default response for Customer creation
    mock_client.Customer.create.return_value = {
        "id": "cus_mock123456",
        "email": "test@example.com",
        "name": "Test User",
        "created": 1625097600,
        "subscriptions": {"data": []}
    }
    
    # Configure default response for Subscription creation
    mock_client.Subscription.create.return_value = {
        "id": "sub_mock123456",
        "customer": "cus_mock123456",
        "status": "active",
        "current_period_end": 1627776000,
        "current_period_start": 1625097600,
        "items": {
            "data": [
                {
                    "id": "si_mock123456",
                    "price": {
                        "id": "price_mock123456",
                        "product": "prod_mock123456"
                    },
                    "quantity": 1
                }
            ]
        }
    }
    
    # Configure default response for PaymentMethod attachment
    mock_client.PaymentMethod.attach.return_value = {
        "id": "pm_mock123456",
        "type": "card",
        "card": {
            "brand": "visa",
            "exp_month": 12,
            "exp_year": 2025,
            "last4": "4242"
        },
        "customer": "cus_mock123456"
    }
    
    # Configure webhook event construction
    mock_client.Webhook.construct_event.return_value = {
        "id": "evt_mock123456",
        "type": "customer.subscription.created",
        "data": {
            "object": {
                "id": "sub_mock123456",
                "customer": "cus_mock123456",
                "status": "active"
            }
        }
    }
    
    with patch("stripe.Customer", mock_client.Customer), \
         patch("stripe.Subscription", mock_client.Subscription), \
         patch("stripe.PaymentMethod", mock_client.PaymentMethod), \
         patch("stripe.Webhook", mock_client.Webhook):
        yield mock_client 