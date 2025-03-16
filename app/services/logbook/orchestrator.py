"""
Logbook orchestration service.

This module provides functionality for:
- Coordinating logbook data processing
- Managing data flow between external sources and database
- Handling data transformations and classifications
- Orchestrating performance analysis
"""

# Standard library imports
from typing import Dict, List, Tuple, Optional
from uuid import UUID
import traceback
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Third-party imports
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

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
                    username=credentials.get('username'),
                    password=credentials.get('password')
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
        normalized_df = await self._normalize_data(raw_df, logbook_type, user_id)
        processed_df = await self._process_data(normalized_df)
        ticks, pyramids, tags = await self._build_entities(processed_df, user_id)
        await self._commit_to_database(ticks, pyramids, tags, user_id, logbook_type, profile_url)
        logger.info(f"{logbook_type.value} sync completed", extra={
            "user_id": str(user_id),
            "total_ticks": len(ticks),
            "total_pyramids": len(pyramids),
            "total_tags": len(tags)
        })
        return ticks, pyramids, tags

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

    async def process_eight_a_nu_ticks(self, user_id: UUID, username: str, password: str) -> Tuple[List[UserTicks], List[PerformancePyramid], List[Tag]]:
        """Process 8a.nu ticks using synchronous client in a thread."""
        try:
            loop = asyncio.get_running_loop()
            # Fetch data synchronously and get the slug
            user_slug, raw_df = await loop.run_in_executor(
                self.executor,
                self._fetch_eight_a_nu_data_sync,
                username,
                password
            )
            
            # Construct the profile URL
            profile_url = f"https://www.8a.nu/user/{user_slug}"
            logger.info(f"Constructed 8a.nu profile URL: {profile_url}", extra={"user_id": str(user_id)})
            
            # Pass the profile_url to _process_ticks
            return await self._process_ticks(user_id, LogbookType.EIGHT_A_NU, raw_df, profile_url=profile_url)
        except Exception as e:
            logger.error("8a.nu processing failed", extra={
                "user_id": str(user_id),
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            raise DataSourceError(f"Error processing 8a.nu data: {str(e)}")

    def _fetch_eight_a_nu_data_sync(self, username: str, password: str) -> Tuple[str, pd.DataFrame]:
        """Fetch 8a.nu data using the Playwright CLI client and return the user_slug and DataFrame."""
        logger.info("Fetching 8a.nu data using Playwright CLI client")
        with EightANuScraper() as client:
            user_slug = client.authenticate(username, password)
            data = client.get_ascents()
            return user_slug, pd.DataFrame(data.get("ascents", []))

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
            
            # Now process classifications using the processed grades 
            #length_category is processed first because it is used in the discipline classification
            #discipline is processed next because it is used in the send classification
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
    ) -> Tuple[List[UserTicks], List[PerformancePyramid], List[Tag]]:
        """Build database entities from processed data"""
        # Initialize tag tracking variables
        tags_by_tick = {}  # Initialize empty dictionary
        tag_data = []      # Initialize empty list
        
        logger.debug("Starting entity building", extra={
            "columns": df.columns.tolist(),
            "has_tags_column": 'tags' in df.columns,
            "row_count": len(df)
        })

        # Define valid columns from UserTicks model
        valid_columns = {
            'route_name', 'tick_date', 'route_grade', 'binned_grade', 'binned_code',
            'length', 'pitches', 'location', 'location_raw', 'lead_style',
            'cur_max_sport', 'cur_max_trad', 'cur_max_boulder', 'cur_max_tr', 'cur_max_alpine', 'cur_max_winter_ice', 'cur_max_aid', 'cur_max_mixed',
            'difficulty_category', 'discipline', 'send_bool', 'length_category',
            'season_category', 'route_url', 'notes', 'route_quality',
            'user_quality', 'logbook_type'
        }
        
        if 'discipline' in df.columns:
            df['discipline'] = df['discipline'].apply(
                lambda x: x.lower() if pd.notna(x) and isinstance(x, str) else x
            )
            
        # Filter DataFrame to only include valid columns that exist
        valid_existing_columns = [col for col in df.columns if col in valid_columns]
        filtered_df = df[valid_existing_columns].copy()
        
        # Clean any remaining NaN values
        for col in filtered_df.columns:
            if filtered_df[col].dtype == 'object' or filtered_df[col].dtype == 'string':
                filtered_df.loc[:, col] = filtered_df[col].astype(object).where(pd.notna(filtered_df[col]), None)
            elif filtered_df[col].dtype == 'float':
                filtered_df.loc[:, col] = filtered_df[col].where(pd.notna(filtered_df[col]), None)
        
        # Process tags if present
        if 'tags' in df.columns:
            logger.debug("Processing tags column", extra={
                "sample_tags": df['tags'].head().tolist(),
                "total_rows": len(df),
                "rows_with_tags": df['tags'].notna().sum()
            })
            
            # Flatten tags from lists into a set of unique strings
            unique_tags = set()
            
            # Process tags for each tick
            for idx, row in df.iterrows():
                tags = row.get('tags')
                tick_tags = []
                
                try:
                    if isinstance(tags, (list, pd.Series)) and len(tags) > 0:
                        # Handle list or Series of tags
                        tick_tags = [tag for tag in tags if tag and pd.notna(tag)]
                    elif isinstance(tags, str) and tags:
                        # Handle single string tag
                        tick_tags = [tags]
                        
                    if tick_tags:
                        # Store standardized tags for this tick
                        standardized_tick_tags = [
                            self.STANDARDIZED_TAG_MAPPING.get(tag, tag)
                            for tag in tick_tags
                            if tag in self.STANDARDIZED_TAG_MAPPING  # Only keep known tags
                        ]
                        if standardized_tick_tags:  # Only store if we have valid tags
                            tags_by_tick[idx] = standardized_tick_tags
                            unique_tags.update(standardized_tick_tags)
                            
                except Exception as e:
                    logger.warning(f"Error processing tags for row {idx}", extra={
                        "error": str(e),
                        "raw_tags": tags
                    })
                    continue
            
            # Create final tag data list
            tag_data = list(unique_tags)
            
            logger.info("Tag processing complete", extra={
                "unique_tags": list(unique_tags),
                "ticks_with_tags": len(tags_by_tick),
                "total_tags": len(tag_data)
            })
        else:
            logger.warning("No tags column found in DataFrame")
        
        # Convert filtered DataFrame rows to dictionaries for ticks
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
        
        return ticks_data, [], tag_data

    async def _commit_to_database(self, ticks_data: List[Dict], pyramid_data: List[Dict], tag_data: List[str], user_id: UUID, logbook_type: LogbookType, profile_url: Optional[str] = None):
        try:
            async with self.db.begin():  # Transaction scope
                ticks = await self.db_service.save_user_ticks(ticks_data, user_id)
                pyramids = await self.db_service.save_performance_pyramid(pyramid_data, user_id)
                tags = await self.db_service.save_tags(tag_data, [tick.id for tick in ticks])
                await self.db_service.update_sync_timestamp(user_id, logbook_type, profile_url)
            # Commit happens automatically on successful exit
        except Exception as e:
            logger.error("Database commit failed", extra={"user_id": str(user_id), "error": str(e)})
            raise

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
