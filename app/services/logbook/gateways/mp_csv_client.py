"""
Mountain Project CSV client service.

This module provides functionality for:
- Fetching user tick data from Mountain Project
- Processing CSV exports
- Managing HTTP interactions
- Data transformation and validation
"""

# Standard library imports
from io import StringIO
import traceback

# Third-party imports
import httpx
import pandas as pd

# Application imports
from app.core.logging import logger
from app.core.exceptions import DataSourceError

class MountainProjectCSVClient:
    """Asynchronous client for fetching Mountain Project CSV data"""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=45.0)  # 45 second timeout
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def fetch_user_ticks(self, profile_url: str) -> pd.DataFrame:
        """
        Asynchronously fetch and parse user ticks from Mountain Project
        
        Args:
            profile_url: The base profile URL for the user
            
        Returns:
            pd.DataFrame: Processed DataFrame containing user ticks
            
        Raises:
            DataSourceError: If there's an error fetching or parsing the CSV
        """
        try:
            # Construct CSV URL
            csv_url = f"{profile_url.rstrip('/')}/tick-export"
            logger.debug(
                "Fetching Mountain Project CSV data",
                extra={
                    "profile_url": profile_url,
                    "csv_url": csv_url
                }
            )
            
            # Fetch CSV data using the class's client
            response = await self.client.get(csv_url)
            response.raise_for_status()
            
            # Parse CSV with proper encoding and error handling
            data = StringIO(response.text)
            
            # Define expected columns with defaults
            expected_columns = {
                'Date': 'tick_date',
                'Route': 'route_name',
                'Rating': 'route_grade',
                'Your Rating': 'user_grade',
                'Notes': 'notes',
                'URL': 'route_url',
                'Pitches': 'pitches',
                'Location': 'location',
                'Style': 'style',
                'Lead Style': 'lead_style',
                'Route Type': 'route_type',
                'Length': 'length',
                'Rating Code': 'binned_code',
                'Avg Stars': 'route_stars',
                'Your Stars': 'user_stars'
            }
            
            # Read CSV with minimal required columns
            required_columns = ['Date', 'Route', 'Rating']
            df = pd.read_csv(
                data,
                sep=',',
                quotechar='"',
                escapechar='\\',
                on_bad_lines='skip'
            )
            
            # Drop rows where required fields are missing
            for col in required_columns:
                if col in df.columns:
                    df = df.dropna(subset=[col])
            
            # Rename existing columns and add missing ones with NaN values
            df = self._rename_columns(df)
            
            # Add any missing columns with NaN values
            for old_col, new_col in expected_columns.items():
                if new_col not in df.columns:
                    df[new_col] = pd.NA
            
            logger.info(
                "Successfully fetched Mountain Project ticks",
                extra={
                    "profile_url": profile_url,
                    "row_count": len(df)
                }
            )
            return df
            
        except httpx.TimeoutException as e:
            logger.error(
                "Timeout error fetching Mountain Project CSV",
                extra={
                    "profile_url": profile_url,
                    "error": str(e),
                    "traceback": traceback.format_exc()
                }
            )
            raise DataSourceError(f"Failed to fetch Mountain Project data: {str(e)}")
            
        except httpx.HTTPError as e:
            logger.error(
                "HTTP error fetching Mountain Project CSV",
                extra={
                    "profile_url": profile_url,
                    "error": str(e),
                    "status_code": getattr(e.response, 'status_code', None),
                    "traceback": traceback.format_exc()
                }
            )
            raise DataSourceError(f"Failed to fetch Mountain Project data: {str(e)}")
            
        except pd.errors.EmptyDataError:
            logger.error(
                "Empty CSV data received from Mountain Project",
                extra={
                    "profile_url": profile_url,
                    "traceback": traceback.format_exc()
                }
            )
            raise DataSourceError("Mountain Project returned empty data")
            
        except Exception as e:
            logger.error(
                "Unexpected error processing Mountain Project data",
                extra={
                    "profile_url": profile_url,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "traceback": traceback.format_exc()
                }
            )
            raise DataSourceError(f"Error processing Mountain Project data: {str(e)}")
    
    @staticmethod
    def _rename_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Rename DataFrame columns to match our schema"""
        column_mapping = {
            'Date': 'tick_date',
            'Route': 'route_name',
            'Rating': 'route_grade',
            'Your Rating': 'user_grade',
            'Notes': 'notes',
            'URL': 'route_url',
            'Pitches': 'pitches',
            'Location': 'location',
            'Style': 'style',
            'Lead Style': 'lead_style',
            'Route Type': 'route_type',
            'Length': 'length',
            'Rating Code': 'binned_code',
            'Avg Stars': 'route_stars',
            'Your Stars': 'user_stars'
        }
        return df.rename(columns=column_mapping)
