"""
Logbook orchestration service.

This module provides functionality for:
- Coordinating logbook data processing
- Managing data flow between external sources and database
- Handling data transformations and classifications
- Orchestrating performance analysis
"""

# Standard library imports
from typing import Dict, List, Tuple, Optional, Union
from uuid import UUID
import traceback
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, date
import random

# Third-party imports
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import HttpUrl

# Application imports
from app.core.logging import logger
from app.core.exceptions import DataSourceError
from app.models import (
    UserTicks,
    PerformancePyramid,
    Tag,

)
from app.models.enums import (
    LogbookType
)
from app.services.utils.grade_service import (
    GradeService,
)
from app.services.logbook.gateways.mp_csv_client import (
    MountainProjectCSVClient
)
from app.services.logbook.gateways.eight_a_nu_scraper import EightANuScraper
from app.services.logbook.processing.mp_csv_processor import (
    MountainProjectCSVProcessor
)
from app.services.logbook.processing.eight_a_nu_processor import (
    EightANuProcessor
)
from app.services.logbook.climb_classifier import ClimbClassifier
from app.services.logbook.pyramid_builder import PyramidBuilder
from app.services.logbook.database_service import DatabaseService
from app.services.logbook.gateways.eight_a_nu_scraper import AccountManager, ScrapingError

class LogbookOrchestrator:
    """Orchestrates the flow of climbing logbook data from source to database"""
    
    def __init__(self, db: AsyncSession, db_service: Optional[DatabaseService] = None):
        """Initialize orchestrator with required services and database session"""
        logger.info("Initializing LogbookOrchestrator")
        self.db = db
        self.grade_service = GradeService.get_instance()
        self.classifier = ClimbClassifier()
        self.pyramid_builder = PyramidBuilder()
        self.db_service = db_service or DatabaseService(db)
        self.executor = ThreadPoolExecutor(max_workers=2)  # Allow 2 concurrent syncs
        logger.debug("LogbookOrchestrator services initialized")

    STANDARDIZED_TAG_MAPPING = {
        'firstAscent': 'First Ascent',
        'chipped': 'Chipped Route',
        'withKneepad': 'Used Kneepad',
        'badAnchor': 'Bad Anchor',
        'badBolts': 'Bad Bolts',
        'highFirstBolt': 'High First Bolt',
        'looseRock': 'Loose Rock',
        'badClippingPosition': 'Bad Clipping Position',
        'isHard': 'Hard for Grade',
        'isSoft': 'Soft for Grade',
        'isBoltedByMe': 'Bolted by Me',
        'isOverhang': 'Overhang',
        'isVertical': 'Vertical',
        'isSlab': 'Slab',
        'isRoof': 'Roof',
        'isAthletic': 'Athletic',
        'isEndurance': 'Endurance',
        'isCrimpy': 'Crimpy',
        'isCruxy': 'Cruxy',
        'isSloper': 'Slopers',
        'isTechnical': 'Technical',
        'isDanger': 'Dangerous',
        # Feature Tags:
        'arete': 'Arete',
        'corner': 'Corner',
        
        #Hold Types:
        'pinch': 'Pinch',
        'crimp': 'Crimp',
        'sloper': 'Sloper',
        'jug': 'Jug',
        'pocket': 'Pocket',
        'crack': 'Crack',

        #positions
        'gaston': 'Gaston',
        'heelhook': 'Heelhook',
        'sidepull': 'Sidepull',
        'undercling': 'Undercling',
        'dropknee': 'Dropknee',
        'flag': 'Flag',
        'crossthrough': 'Crossthrough',
        'batHang': 'Bat Hang',
    }


    async def process_logbook_data(
        self,
        user_id: UUID,
        logbook_type: LogbookType,
        **credentials
    ) -> Tuple[List[UserTicks], List[PerformancePyramid], List[Tag]]:
        """
        Main entry point for processing logbook data from any source.
        Routes to specific processing methods based on logbook type.
        """
        logger.info(f"Processing {logbook_type.value} logbook data", extra={"user_id": str(user_id)})
        
        try:
            if logbook_type == LogbookType.MOUNTAIN_PROJECT:
                return await self.process_mountain_project_ticks(
                    user_id=user_id,
                    profile_url=credentials.get('profile_url')
                )
            elif logbook_type == LogbookType.EIGHT_A_NU:
                return await self.process_eight_a_nu_ticks(
                    user_id=user_id,
                    profile_url=credentials.get('profile_url')
                )
            else:
                raise DataSourceError(f"Unsupported logbook type: {logbook_type}")
        except Exception as e:
            logger.error(f"{logbook_type.value} processing failed", extra={
                "user_id": str(user_id),
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            raise DataSourceError(f"Error processing {logbook_type.value} data: {str(e)}")

    async def _process_ticks(
        self,
        user_id: UUID,
        logbook_type: LogbookType,
        raw_df: pd.DataFrame,
        profile_url: Optional[str] = None
    ) -> Tuple[List[UserTicks], List[PerformancePyramid], List[Tag]]:
        """Centralized processing logic for all logbook types."""
        # Step 1: Normalize and process data
        normalized_df = await self._normalize_data(raw_df, logbook_type, user_id)
        processed_df = await self._process_data(normalized_df)

        # Step 2: Build initial entities (ticks and tags)
        ticks_data, _, tag_data = await self._build_entities(processed_df, user_id)

        # Step 3: Persist and build pyramids
        ticks, pyramids, tags = await self._persist_and_analyze(
            user_id, 
            ticks_data, 
            tag_data, 
            processed_df,  # Pass the processed DataFrame for pyramid building
            logbook_type, 
            profile_url
        )

        # Step 4: Update sync timestamp after successful processing
        await self.db_service.update_sync_timestamp(
            user_id=user_id,
            logbook_type=logbook_type,
            profile_url=profile_url
        )

        logger.info(f"{logbook_type.value} sync completed", extra={
            "user_id": str(user_id),
            "total_ticks": len(ticks),
            "total_pyramids": len(pyramids),
            "total_tags": len(tags)
        })
        return ticks, pyramids, tags

    async def _persist_and_analyze(
        self,
        user_id: UUID,
        ticks_data: List[Dict],
        tag_data: List[str],
        processed_df: pd.DataFrame,
        logbook_type: LogbookType,
        profile_url: Optional[str] = None
    ) -> Tuple[List[UserTicks], List[PerformancePyramid], List[Tag]]:
        """
        Persist ticks, build pyramids, and save all entities within a single transaction.
        
        Args:
            user_id: User identifier
            ticks_data: List of tick dictionaries to save
            tag_data: List of tag strings to save
            processed_df: Original processed DataFrame with all required columns
            logbook_type: Type of logbook being processed
            profile_url: Optional URL of the user's profile
            
        Returns:
            Tuple of (saved ticks, saved pyramids, saved tags)
        """
        try:
            # Get existing ticks for deduplication
            stmt = select(UserTicks).where(UserTicks.user_id == user_id)
            result = await self.db.execute(stmt)
            existing_ticks = result.scalars().all()
            
            # Create a set of existing route_name + tick_date combinations
            existing_combinations = {
                (tick.route_name, 
                 tick.tick_date.isoformat() if isinstance(tick.tick_date, (date, datetime)) 
                 else tick.tick_date.date().isoformat() if tick.tick_date 
                 else None)
                for tick in existing_ticks
            }
            
            # Filter processed_df to only include new unique ticks
            processed_df = processed_df.copy()
            
            # Handle NaN values and ensure consistent datetime format
            processed_df['tick_date'] = pd.to_datetime(processed_df['tick_date'], utc=True)
            processed_df['tick_date_str'] = processed_df['tick_date'].dt.date.apply(
                lambda x: x.isoformat() if pd.notna(x) else None
            )
            
            # Replace NaN with None in route_name to ensure consistent comparison
            processed_df['route_name'] = processed_df['route_name'].where(pd.notna(processed_df['route_name']), None)
            
            processed_df['combination'] = list(zip(processed_df['route_name'], processed_df['tick_date_str']))
            
            # Filter out existing combinations
            processed_df = processed_df[~processed_df['combination'].isin(existing_combinations)]
            processed_df = processed_df.drop(['tick_date_str', 'combination'], axis=1)
            
            if processed_df.empty:
                logger.info("No new ticks to process")
                return [], [], []
            
            # Reset index for consistent alignment
            processed_df = processed_df.reset_index(drop=True)
            
            # Filter ticks_data to match processed_df
            filtered_ticks_data = [
                tick for tick in ticks_data 
                if (tick['route_name'], tick['tick_date'].isoformat() if isinstance(tick['tick_date'], (datetime, pd.Timestamp)) else None) 
                not in existing_combinations
            ]
            
            # Save ticks and get IDs
            ticks = await self.db_service.save_user_ticks(filtered_ticks_data, user_id)
            
            if not ticks:
                logger.info("No new ticks saved")
                return [], [], []
            
            # Directly assign tick IDs to processed_df
            processed_df['id'] = [tick.id for tick in ticks]
            
            # Build pyramids using only the new unique ticks
            try:
                # Ensure all required columns are present
                required_columns = {
                    'id', 'discipline', 'binned_code', 'send_bool', 
                    'tick_date', 'route_name', 'location', 'pitches', 
                    'length_category', 'notes', 'tags'
                }
                missing_columns = required_columns - set(processed_df.columns)
                if missing_columns:
                    logger.warning("Missing columns for pyramid building", extra={
                        "missing_columns": list(missing_columns)
                    })
                
                # Get all user ticks for complete pyramid building
                all_user_ticks = await self.db_service.get_user_ticks(user_id)
                all_ticks_df = pd.DataFrame([tick.__dict__ for tick in all_user_ticks])
                
                # Combine existing and new ticks for pyramid building
                combined_df = pd.concat([all_ticks_df, processed_df], ignore_index=True)
                combined_df = combined_df.drop_duplicates(subset=['route_name', 'tick_date'], keep='last')
                
                # Clean up existing pyramid data before rebuilding
                await self.db_service.cleanup_performance_pyramid(user_id)
                
                pyramid_data = await self.pyramid_builder.build_performance_pyramid(combined_df, user_id)
                pyramids = await self.db_service.save_performance_pyramid(pyramid_data, user_id)
                logger.info("Performance pyramid data built and saved", extra={
                    "pyramid_entries": len(pyramid_data)
                })
            except Exception as e:
                logger.error("Failed to build/save performance pyramid", extra={
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "available_columns": list(processed_df.columns)
                })
                raise DataSourceError(f"Error building performance pyramid: {str(e)}")

            # Save tags
            tags = await self.db_service.save_tags(tag_data, [tick.id for tick in ticks])
            
            # Update sync timestamp after successful processing
            await self.db_service.update_sync_timestamp(
                user_id=user_id,
                logbook_type=logbook_type,
                profile_url=profile_url
            )
            
            return ticks, pyramids, tags
            
        except Exception as e:
            logger.error("Error in persist and analyze", extra={
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            raise DataSourceError(f"Error persisting and analyzing data: {str(e)}")

    async def process_mountain_project_ticks(self, user_id: UUID, profile_url: str):
        """Process Mountain Project ticks."""
        try:
            async with MountainProjectCSVClient() as client:
                raw_df = await client.fetch_user_ticks(profile_url)
            return await self._process_ticks(user_id, LogbookType.MOUNTAIN_PROJECT, raw_df, profile_url=profile_url)
        except Exception as e:
            logger.error("Mountain Project processing failed", extra={
                "user_id": str(user_id),
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            raise DataSourceError(f"Error processing Mountain Project data: {str(e)}")

    async def process_eight_a_nu_ticks(self, user_id: UUID, profile_url: Union[str, HttpUrl]) -> Tuple[List[UserTicks], List[PerformancePyramid], List[Tag]]:
        """Process 8a.nu ticks using synchronous client in a thread with rotating accounts."""
        try:
            # Convert HttpUrl to string if needed
            profile_url_str = str(profile_url) if isinstance(profile_url, HttpUrl) else profile_url
            
            # Extract target_slug from profile_url
            target_slug = profile_url_str.split('/user/')[-1].split('/')[0]
            if not target_slug:
                raise DataSourceError("Invalid 8a.nu profile URL")

            logger.info("Starting 8a.nu processing", extra={
                "user_id": str(user_id),
                "profile_url": profile_url_str,
                "target_slug": target_slug
            })

            # Initialize account manager
            account_manager = AccountManager()
            failed_accounts = set()  # Track failed accounts
            
            # Try with each account until successful or all accounts exhausted
            for attempt in range(len(account_manager.accounts)):
                try:
                    # Get a random account that hasn't failed yet
                    available_accounts = [i for i in range(len(account_manager.accounts)) if i not in failed_accounts]
                    if not available_accounts:
                        raise DataSourceError("All accounts have failed")
                        
                    index = random.choice(available_accounts)
                    username, password = account_manager.accounts[index]
                    cookie_file = account_manager.cookie_files[index]
                    
                    logger.info("Trying account", extra={
                        "user_id": str(user_id),
                        "account_index": index,
                        "attempt": attempt + 1,
                        "total_attempts": len(account_manager.accounts)
                    })
                    
                    loop = asyncio.get_running_loop()
                    # Fetch data synchronously using the selected account
                    raw_df = await loop.run_in_executor(
                        self.executor,
                        self._fetch_eight_a_nu_data_sync,
                        username,
                        password,
                        cookie_file,
                        target_slug
                    )
                    
                    logger.info(f"Successfully fetched 8a.nu data for {target_slug}", extra={
                        "user_id": str(user_id),
                        "account_index": index,
                        "row_count": len(raw_df)
                    })
                    
                    # Pass the profile_url to _process_ticks
                    return await self._process_ticks(user_id, LogbookType.EIGHT_A_NU, raw_df, profile_url=profile_url_str)
                    
                except ScrapingError as e:
                    logger.warning(f"Failed to fetch data with account {index}", extra={
                        "user_id": str(user_id),
                        "error": str(e),
                        "attempt": attempt + 1
                    })
                    failed_accounts.add(index)
                    if len(failed_accounts) == len(account_manager.accounts):
                        raise DataSourceError(f"Failed to fetch 8a.nu data after trying all accounts: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error("8a.nu processing failed", extra={
                "user_id": str(user_id),
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            raise DataSourceError(f"Error processing 8a.nu data: {str(e)}")

    def _fetch_eight_a_nu_data_sync(self, username: str, password: str, cookie_file: str, target_slug: str) -> pd.DataFrame:
        """Fetch 8a.nu data using the Playwright CLI client and return DataFrame."""
        logger.info("Fetching 8a.nu data using Playwright CLI client", extra={
            "username": username[:3] + "***",  # Log partial username for security
            "cookie_file": cookie_file,
            "target_slug": target_slug
        })
        try:
            with EightANuScraper(cookie_file=cookie_file) as client:
                # Authenticate with the account
                client.authenticate(username, password)
                # Get ascents for the target slug
                data = client.get_ascents(target_slug)
                return pd.DataFrame(data.get("ascents", []))
        except Exception as e:
            logger.error("Failed to fetch 8a.nu data", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc(),
                "target_slug": target_slug
            })
            raise

    async def _fetch_mountain_project_data(self, profile_url: str) -> pd.DataFrame:
        """Fetch Mountain Project data using async client."""
        async with MountainProjectCSVClient() as client:
            return await client.fetch_user_ticks(profile_url)

    async def _normalize_data(self, raw_df: pd.DataFrame, logbook_type: LogbookType, user_id: UUID) -> pd.DataFrame:
        """Normalize data using appropriate processor"""
        if logbook_type == LogbookType.MOUNTAIN_PROJECT:
            processor = MountainProjectCSVProcessor(user_id)
            return processor.process_raw_data(raw_df)
        elif logbook_type == LogbookType.EIGHT_A_NU:
            processor = EightANuProcessor(user_id)
            return await processor.process_raw_data(raw_df)
        else:
            raise ValueError(f"Unsupported logbook type: {logbook_type}")

    async def _process_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process classifications and grades"""
        logger.info("Starting data processing and classification", extra={
            "total_rows": len(df)
        })
        
        try:
            # Initialize classifier
            classifier = ClimbClassifier()
            
            # Process grades first without requiring discipline
            df = await self._process_grades(df)
            
            # Check if this is 8a.nu data (has logbook_type column)
            is_eight_a_nu = 'logbook_type' in df.columns and df['logbook_type'].iloc[0] == LogbookType.EIGHT_A_NU
            
            if is_eight_a_nu:
                # For 8a.nu, only process season category
                df['season_category'] = classifier.classify_season(df)
            else:
                # For other logbook types, process all classifications
                df['length_category'] = classifier.classify_length(df)
                df['discipline'] = classifier.classify_discipline(df)
                df['send_bool'] = classifier.classify_sends(df)
                df['season_category'] = classifier.classify_season(df)
            
            # Calculate max grades after discipline is set
            df = await self._calculate_max_grades(df)
            
            # Process crux characteristics
            df['crux_angle'] = df['notes'].apply(classifier.predict_crux_angle)
            df['crux_energy'] = df['notes'].apply(classifier.predict_crux_energy)
            
            # Calculate difficulty categories last since it depends on all previous processing
            df['difficulty_category'] = await self._calculate_difficulty_category(df)
            
            logger.info("Data processing and classification completed", extra={
                "disciplines": df['discipline'].value_counts().to_dict(),
                "send_rate": f"{(df['send_bool'].sum() / len(df)) * 100:.1f}%",
                "difficulty_categories": df['difficulty_category'].value_counts().to_dict()
            })
            
            return df
            
        except Exception as e:
            logger.error("Error in data processing", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc()
            })
            raise DataSourceError(f"Error processing data: {str(e)}")

    async def _build_entities(
        self,
        df: pd.DataFrame,
        user_id: UUID
    ) -> Tuple[List[Dict], List[Dict], List[str]]:
        """Build initial entities (ticks and tags) from processed data."""
        tags_by_tick = {}
        tag_data = []
        
        logger.debug("Starting entity building", extra={
            "columns": df.columns.tolist(),
            "has_tags_column": 'tags' in df.columns,
            "row_count": len(df)
        })

        valid_columns = {
            'route_name', 'tick_date', 'route_grade', 'binned_grade', 'binned_code',
            'length', 'pitches', 'location', 'location_raw', 'lead_style',
            'cur_max_sport', 'cur_max_trad', 'cur_max_boulder', 'cur_max_tr', 'cur_max_alpine', 
            'cur_max_winter_ice', 'cur_max_aid', 'cur_max_mixed', 'difficulty_category', 
            'discipline', 'send_bool', 'length_category', 'season_category', 'route_url', 
            'notes', 'route_quality', 'user_quality', 'logbook_type'
        }
        
        if 'discipline' in df.columns:
            df['discipline'] = df['discipline'].apply(
                lambda x: x.lower() if pd.notna(x) and isinstance(x, str) else x
            )
            
        valid_existing_columns = [col for col in df.columns if col in valid_columns]
        filtered_df = df[valid_existing_columns].copy()
        
        for col in filtered_df.columns:
            if filtered_df[col].dtype == 'object' or filtered_df[col].dtype == 'string':
                filtered_df.loc[:, col] = filtered_df[col].astype(object).where(pd.notna(filtered_df[col]), None)
            elif filtered_df[col].dtype == 'float':
                filtered_df.loc[:, col] = filtered_df[col].where(pd.notna(filtered_df[col]), None)
        
        if 'tags' in df.columns:
            logger.debug("Processing tags column", extra={
                "sample_tags": df['tags'].head().tolist(),
                "total_rows": len(df),
                "rows_with_tags": df['tags'].notna().sum()
            })
            unique_tags = set()
            for idx, row in df.iterrows():
                tags = row.get('tags')
                tick_tags = []
                try:
                    if isinstance(tags, (list, pd.Series)) and len(tags) > 0:
                        tick_tags = [tag for tag in tags if tag and pd.notna(tag)]
                    elif isinstance(tags, str) and tags:
                        tick_tags = [tags]
                    if tick_tags:
                        standardized_tick_tags = [
                            self.STANDARDIZED_TAG_MAPPING.get(tag, tag)
                            for tag in tick_tags
                            if tag in self.STANDARDIZED_TAG_MAPPING
                        ]
                        if standardized_tick_tags:
                            tags_by_tick[idx] = standardized_tick_tags
                            unique_tags.update(standardized_tick_tags)
                except Exception as e:
                    logger.warning(f"Error processing tags for row {idx}", extra={
                        "error": str(e),
                        "raw_tags": tags
                    })
                    continue
            tag_data = list(unique_tags)
            logger.info("Tag processing complete", extra={
                "unique_tags": list(unique_tags),
                "ticks_with_tags": len(tags_by_tick),
                "total_tags": len(tag_data)
            })
        else:
            logger.warning("No tags column found in DataFrame")
        
        ticks_data = []
        for idx, row in filtered_df.iterrows():
            tick_dict = row.to_dict()
            if idx in tags_by_tick:
                tick_dict['_tags_list'] = tags_by_tick[idx]
            ticks_data.append(tick_dict)
            
        logger.info("Entity building complete", extra={
            "ticks_created": len(ticks_data),
            "ticks_with_tags": len([t for t in ticks_data if '_tags_list' in t]),
            "total_tags": len(tag_data)
        })
        
        # Return empty list for pyramid_data as it will be built after ticks are saved
        return ticks_data, [], tag_data

    async def _process_grades(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process grades and calculate grade-related metrics"""
        logger.debug("Processing grades and metrics")
        try:
            # Process grades in batches
            grades = df['route_grade'].tolist()
            
            # Convert grades to codes first, without requiring discipline
            df['binned_code'] = await self.grade_service.convert_grades_to_codes(
                grades=grades,
                discipline=None  # Don't require discipline for initial conversion
            )
            
            # Get binned grades in batches
            codes = df['binned_code'].tolist()
            binned_grades = []
            
            BATCH_SIZE = 100
            for i in range(0, len(codes), BATCH_SIZE):
                batch = codes[i:i + BATCH_SIZE]
                batch_grades = [
                    self.grade_service.get_grade_from_code(code)
                    for code in batch
                ]
                binned_grades.extend(batch_grades)
            
            df['binned_grade'] = binned_grades
            
            # Handle user grades if present
            if 'user_grade' in df.columns:
                user_grades = df['user_grade'].fillna(df['route_grade']).tolist()
                df['user_binned_code'] = await self.grade_service.convert_grades_to_codes(
                    grades=user_grades,
                    discipline=None
                )
            
            return df
            
        except Exception as e:
            logger.error(f"Error processing grades: {str(e)}")
            raise DataSourceError(f"Error processing grades: {str(e)}")

    async def _calculate_max_grades(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate maximum grades for each discipline over time"""
        # Sort by date to ensure proper progression
        df = df.sort_values('tick_date')
        
        # Initialize max grade columns
        df['cur_max_sport'] = 0
        df['cur_max_trad'] = 0
        df['cur_max_boulder'] = 0
        df['cur_max_tr'] = 0
        df['cur_max_alpine'] = 0
        df['cur_max_winter_ice'] = 0
        df['cur_max_aid'] = 0
        df['cur_max_mixed'] = 0
        
        # Initialize running max values
        max_sport = 0
        max_boulder = 0
        max_trad = 0
        max_tr = 0
        max_alpine = 0
        max_winter_ice = 0
        max_aid = 0
        max_mixed = 0

        # Calculate running max values for each row
        for idx in df.index:
            # Get current row values
            discipline = df.at[idx, 'discipline']
            is_send = df.at[idx, 'send_bool']
            grade_code = df.at[idx, 'binned_code']
            
            # Update max values based on sends
            if is_send:
                if discipline == 'sport':
                    max_sport = max(max_sport, grade_code)
                elif discipline == 'boulder':
                    if grade_code >= 101:  # Only count boulder grades
                        max_boulder = max(max_boulder, grade_code)
                elif discipline == 'trad':
                    if grade_code < 101:  # Only count route grades
                        max_trad = max(max_trad, grade_code)
                elif discipline == 'tr':
                    if grade_code < 101:  # Only count route grades
                        max_tr = max(max_tr, grade_code)
                elif discipline == 'alpine':
                    if grade_code < 101:  # Only count route grades
                        max_alpine = max(max_alpine, grade_code)
                elif discipline == 'winter_ice':
                    if grade_code < 101:  # Only count route grades
                        max_winter_ice = max(max_winter_ice, grade_code)
                elif discipline == 'aid':
                    if grade_code < 101:  # Only count route grades
                        max_aid = max(max_aid, grade_code)
                elif discipline == 'mixed':
                    if grade_code < 101:  # Only count route grades
                        max_mixed = max(max_mixed, grade_code)
            
            # Set current max values for the row
            df.at[idx, 'cur_max_sport'] = max_sport
            df.at[idx, 'cur_max_boulder'] = max_boulder
            df.at[idx, 'cur_max_trad'] = max_trad
            df.at[idx, 'cur_max_tr'] = max_tr
            df.at[idx, 'cur_max_alpine'] = max_alpine
            df.at[idx, 'cur_max_winter_ice'] = max_winter_ice
            df.at[idx, 'cur_max_aid'] = max_aid
            df.at[idx, 'cur_max_mixed'] = max_mixed
        
        return df

    async def _calculate_difficulty_category(self, df: pd.DataFrame) -> pd.Series:
        """Calculate difficulty category based on max grades"""
        def difficulty_bins(row):
            discipline = row['discipline']
            binned_code = row['binned_code']
            
            max_grade_cols = {
                'sport': 'cur_max_sport',
                'trad': 'cur_max_trad',
                'boulder': 'cur_max_boulder',
                'tr': 'cur_max_tr',
                'alpine': 'cur_max_alpine',
                'winter_ice': 'cur_max_winter_ice',
                'aid': 'cur_max_aid',
                'mixed': 'cur_max_mixed'
            }
            
            if discipline not in max_grade_cols:
                return 'Other'
                
            cur_max = row[max_grade_cols[discipline]]
            
            # Handle boulder vs route grade ranges
            if discipline == 'boulder':
                if binned_code < 101:  # If current tick is not a boulder grade
                    return 'Other'
                if cur_max < 101:  # If no previous boulder sends
                    return 'Project'
            else:  # Sport/Trad
                if binned_code >= 101 or cur_max >= 101:  # If either grade is a boulder grade
                    return 'Other'
            
            # Calculate relative difficulty and apply consistent categorization
            grade_diff = binned_code - cur_max
            
            if grade_diff > 0:
                return 'Project'
            elif grade_diff == 0:
                return 'Project'
            elif grade_diff == -1:
                return 'Tier 2'
            elif grade_diff == -2:
                return 'Tier 3'
            elif grade_diff == -3:
                return 'Tier 4'
            else:
                return 'Base Volume'
        
        return df.apply(difficulty_bins, axis=1)
