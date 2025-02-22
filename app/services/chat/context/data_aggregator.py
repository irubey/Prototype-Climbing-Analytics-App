from typing import Dict, List, Optional, Union
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from sqlalchemy import text
from uuid import UUID
from app.core.exceptions import DatabaseError
from io import StringIO

class DataAggregator:
    """
    Aggregates climber data from various sources including ClimberContext, UserTicks,
    PerformancePyramid, ChatHistory, and user uploads.
    """
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.supported_upload_formats = {'csv', 'json', 'txt'}

    async def fetch_climber_context(self, user_id: Union[int, UUID, str]) -> Dict:
        """
        Fetches climber profile, goals, and preferences.
        
        Args:
            user_id: User ID as UUID, string, or integer
            
        Returns:
            Dictionary containing climber context or empty dict if not found
            
        Raises:
            DatabaseError: If there's an error executing the query
        """
        try:
            # Convert user_id to UUID if it's not already
            if isinstance(user_id, str):
                user_id = UUID(user_id)
            elif isinstance(user_id, int):
                # For testing purposes, create a deterministic UUID from int
                user_id = UUID(int=user_id, version=4)
            
            query = text("""
                SELECT * FROM climber_context 
                WHERE user_id = :user_id
            """)
            result = await self.db_session.execute(query, {'user_id': user_id})
            row = result.first()
            if row is None:
                return {}
            return dict(row._mapping)
        except (ValueError, TypeError) as e:
            raise DatabaseError(f"Invalid user_id format: {str(e)}")
        except Exception as e:
            raise DatabaseError(f"Error fetching climber context: {str(e)}")

    async def fetch_recent_ticks(self, user_id: Union[int, UUID, str], days: int = 30) -> List[Dict]:
        """
        Fetches recent climbs within specified timeframe.
        
        Args:
            user_id: User ID as UUID, string, or integer
            days: Number of days to look back
            
        Returns:
            List of dictionaries containing recent ticks
        """
        try:
            if isinstance(user_id, str):
                user_id = UUID(user_id)
            elif isinstance(user_id, int):
                user_id = UUID(int=user_id, version=4)
            
            cutoff_date = datetime.now() - timedelta(days=days)
            query = text("""
                SELECT 
                    tick_date,
                    route_name,
                    route_grade,
                    send_bool,
                    created_at
                FROM user_ticks 
                WHERE user_id = :user_id 
                AND tick_date >= :cutoff_date 
                ORDER BY tick_date DESC
            """)
            result = await self.db_session.execute(
                query, 
                {'user_id': user_id, 'cutoff_date': cutoff_date}
            )
            rows = result.fetchall()
            return [dict(row._mapping) for row in rows]
        except (ValueError, TypeError) as e:
            raise DatabaseError(f"Invalid user_id format: {str(e)}")
        except Exception as e:
            raise DatabaseError(f"Error fetching recent ticks: {str(e)}")

    async def fetch_performance_metrics(self, user_id: Union[int, UUID, str]) -> Dict:
        """
        Fetches performance pyramid data including grades and styles.
        
        Args:
            user_id: User ID as UUID, string, or integer
            
        Returns:
            Dictionary containing performance metrics or empty dict if not found
        """
        try:
            if isinstance(user_id, str):
                user_id = UUID(user_id)
            elif isinstance(user_id, int):
                user_id = UUID(int=user_id, version=4)
            
            query = text("""
                SELECT * FROM performance_pyramid 
                WHERE user_id = :user_id
            """)
            result = await self.db_session.execute(query, {'user_id': user_id})
            row = result.first()
            if row is None:
                return {}
            return dict(row._mapping)
        except (ValueError, TypeError) as e:
            raise DatabaseError(f"Invalid user_id format: {str(e)}")
        except Exception as e:
            raise DatabaseError(f"Error fetching performance metrics: {str(e)}")

    async def fetch_chat_history(
        self, 
        user_id: Union[int, UUID, str], 
        conversation_id: Optional[int] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Fetches recent chat history for context continuity.
        
        Args:
            user_id: User ID as UUID, string, or integer
            conversation_id: Optional conversation ID
            limit: Maximum number of messages to return
            
        Returns:
            List of chat messages
        """
        try:
            if isinstance(user_id, str):
                user_id = UUID(user_id)
            elif isinstance(user_id, int):
                user_id = UUID(int=user_id, version=4)
            
            base_query = """
                SELECT * FROM chat_history 
                WHERE user_id = :user_id
                {conversation_filter}
                ORDER BY created_at DESC 
                LIMIT :limit
            """
            
            params = {'user_id': user_id, 'limit': limit}
            conversation_filter = ""
            
            if conversation_id:
                conversation_filter = "AND conversation_id = :conversation_id"
                params['conversation_id'] = str(conversation_id)  # Convert to string
            
            query = text(base_query.format(conversation_filter=conversation_filter))
            result = await self.db_session.execute(query, params)
            rows = result.fetchall()
            return [dict(row._mapping) for row in rows]
        except (ValueError, TypeError) as e:
            raise DatabaseError(f"Invalid user_id format: {str(e)}")
        except Exception as e:
            raise DatabaseError(f"Error fetching chat history: {str(e)}")

    def parse_upload(self, file_content: str, file_format: str) -> List[Dict]:
        """
        Parses uploaded files into structured data.
        
        Args:
            file_content: String content of the uploaded file
            file_format: Format of the file ('csv', 'json', or 'txt')
            
        Returns:
            List of dictionaries containing parsed data
            
        Raises:
            ValueError: If file format is unsupported or content is invalid
        """
        if file_format not in self.supported_upload_formats:
            raise ValueError(f"Unsupported file format: {file_format}")

        try:
            if file_format == 'csv':
                df = pd.read_csv(StringIO(file_content))
                required_columns = {'date', 'route', 'grade'}
                if not all(col in df.columns for col in required_columns):
                    missing = required_columns - set(df.columns)
                    raise ValueError(f"Missing required columns: {missing}")
                return df.to_dict('records')

            elif file_format == 'json':
                data = pd.read_json(StringIO(file_content))
                return data.to_dict('records')

            else:  # txt format
                # Assuming tab-separated values with headers
                df = pd.read_csv(StringIO(file_content), sep='\t')
                return df.to_dict('records')

        except Exception as e:
            raise ValueError(f"Error parsing {file_format} file: {str(e)}")

    def deduplicate_entries(
        self, 
        existing_data: List[Dict], 
        new_data: List[Dict],
        timestamp_field: str = 'date'
    ) -> List[Dict]:
        """
        Deduplicates entries based on timestamp, keeping the latest version.
        
        Args:
            existing_data: List of existing entries
            new_data: List of new entries to merge
            timestamp_field: Field name containing the timestamp
            
        Returns:
            Deduplicated list of entries
        """
        # Handle empty data case
        if not existing_data and not new_data:
            return []

        # Convert lists to DataFrames for easier manipulation
        existing_df = pd.DataFrame(existing_data)
        new_df = pd.DataFrame(new_data)

        # If either DataFrame is empty, return the non-empty one
        if existing_df.empty and not new_df.empty:
            return new_data
        if new_df.empty and not existing_df.empty:
            return existing_data

        # Combine DataFrames and sort by timestamp
        combined_df = pd.concat([existing_df, new_df])
        combined_df[timestamp_field] = pd.to_datetime(combined_df[timestamp_field])
        
        # Sort by timestamp and drop duplicates, keeping only the latest version
        deduplicated_df = (combined_df
            .sort_values(timestamp_field, ascending=False)  # Sort descending to keep latest
            .drop_duplicates(subset=['route'], keep='first')  # Keep first since we sorted descending
            .sort_values(timestamp_field)  # Sort ascending for final output
        )
        
        # Convert timestamps back to string format
        deduplicated_df[timestamp_field] = deduplicated_df[timestamp_field].dt.strftime('%Y-%m-%d')
        
        return deduplicated_df.to_dict('records')

    async def aggregate_all_data(
        self, 
        user_id: Union[int, UUID, str],
        conversation_id: Optional[int] = None
    ) -> Dict:
        """
        Aggregates all climber data into a unified format.
        
        Args:
            user_id: User ID as UUID, string, or integer
            conversation_id: Optional conversation ID for chat history
            
        Returns:
            Dictionary containing all aggregated data
        """
        try:
            if isinstance(user_id, str):
                user_id = UUID(user_id)
            elif isinstance(user_id, int):
                user_id = UUID(int=user_id, version=4)
            
            # Fetch all data concurrently
            context = await self.fetch_climber_context(user_id)
            recent_ticks = await self.fetch_recent_ticks(user_id)
            performance = await self.fetch_performance_metrics(user_id)
            chat_history = await self.fetch_chat_history(user_id, conversation_id)

            return {
                "climber_context": context,
                "recent_ticks": recent_ticks,
                "performance_metrics": performance,
                "chat_history": chat_history,
                "uploads": []  # Placeholder for uploaded data
            }
        except (ValueError, TypeError) as e:
            raise DatabaseError(f"Invalid user_id format: {str(e)}")
        except Exception as e:
            raise DatabaseError(f"Error aggregating data: {str(e)}")
