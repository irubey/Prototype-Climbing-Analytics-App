Overview of LogbookOrchestrator

The LogbookOrchestrator is the central coordinator for processing climbing logbook data. It manages the flow from raw data retrieval to database persistence, leveraging specialized clients, processors, and services. Its primary responsibilities include:

    Fetching raw data from external sources (Mountain Project CSV or 8a.nu JSON).
    Normalizing and processing the data into a standardized format.
    Classifying climbing-specific attributes (e.g., discipline, send status).
    Building database entities (UserTicks, PerformancePyramid, Tag).
    Committing the processed data to the database.

The class is initialized with an AsyncSession (for database operations) and optionally a DatabaseService. It also sets up helper services like GradeService, ClimbClassifier, and PyramidBuilder, and uses a ThreadPoolExecutor for synchronous tasks (e.g., 8a.nu scraping).
Data Flow: Step-by-Step

1. Entry Point: process_logbook_data

   Trigger: The flow begins when an external caller (e.g., an API endpoint like connect_logbook) invokes process_logbook_data with a user_id, logbook_type, and credentials (e.g., profile_url for Mountain Project).
   Example call: await orchestrator.process_logbook_data(user_id, LogbookType.MOUNTAIN_PROJECT, profile_url="https://www.mountainproject.com/user/123")
   Action: This method acts as a router, directing the request to the appropriate processing method based on logbook_type:
   process_mountain_project_ticks for Mountain Project.
   process_eight_a_nu_ticks for 8a.nu.
   Data: No data transformation occurs here; it’s a dispatch point.
   Output: The method returns a tuple of (List[UserTicks], List[PerformancePyramid], List[Tag]) after processing completes.

2. Data Retrieval: process_mountain_project_ticks

   Input: user_id: UUID, profile_url: str.
   Action: This method fetches raw data from Mountain Project.
   Client: Uses MountainProjectCSVClient (async HTTP client).
   Process:
   Opens an async context with async with MountainProjectCSVClient() as client:.
   Calls await client.fetch_user_ticks(profile_url), which:
   Constructs a CSV URL (profile_url + "/tick-export").
   Sends an HTTP GET request with httpx.AsyncClient.
   Parses the response into a pd.DataFrame using pd.read_csv.
   Renames columns (e.g., "Date" → "tick_date", "Route" → "route_name").
   Data: Raw CSV data as a pd.DataFrame with columns like tick_date, route_name, route_grade, location, etc.
   Example row: {"tick_date": "2023-01-15", "route_name": "The Nose", "route_grade": "5.9", "location": "Yosemite > El Capitan"}.
   Next Step: Passes the raw_df to \_process_ticks.
   8a.nu Difference: For 8a.nu, process_eight_a_nu_ticks uses EightANuScraper (synchronous) via a ThreadPoolExecutor to fetch JSON data, converting it to a pd.DataFrame.

3. Central Processing: \_process_ticks

   Input: user_id: UUID, logbook_type: LogbookType, raw_df: pd.DataFrame.
   Action: This is the core processing pipeline, shared by both Mountain Project and 8a.nu. It orchestrates:
   Normalization: Calls \_normalize_data.
   Processing: Calls \_process_data.
   Entity Building: Calls \_build_entities.
   Database Commit: Calls \_commit_to_database.
   Output: Returns (ticks, pyramids, tags) after all steps complete.

4. Normalization: \_normalize_data

   Input: raw_df: pd.DataFrame, logbook_type: LogbookType, user_id: UUID.
   Action: Normalizes the raw data into a format closer to the UserTicks schema.
   Processor Selection:
   Mountain Project: Uses MountainProjectCSVProcessor.
   8a.nu: Uses EightANuProcessor.
   Mountain Project Example:
   Calls MountainProjectCSVProcessor.process_raw_data(raw_df).
   Actions:
   Validates required columns (route_name, route_grade, tick_date).
   Creates a new standardized_df with UserTicks fields.
   Maps columns (e.g., route_stars → route_quality normalized to 0-1 scale).
   Processes locations (splits >-separated strings, e.g., "Yosemite > El Capitan" → location: "El Capitan, Yosemite").
   Sets defaults (e.g., logbook_type = MOUNTAIN_PROJECT, user_id).
   Cleans NaN values for database compatibility.
   Data: A pd.DataFrame with standardized columns (e.g., route_name, tick_date, route_grade, location, lead_style).
   Example: {"route_name": "The Nose", "tick_date": "2023-01-15", "route_grade": "5.9", "location": "El Capitan, Yosemite", "logbook_type": "mountain_project"}.
   8a.nu Difference: EightANuProcessor maps JSON fields (e.g., zlaggableName → route_name, date → tick_date), converts grades (French/Font to YDS/V-scale), and derives location from cragName and areaName.

5. Processing: \_process_data

   Input: normalized*df: pd.DataFrame.
   Action: Enriches the data with climbing-specific classifications and metrics.
   Steps:
   Grade Processing (\_process_grades):
   Converts route_grade to binned_code using GradeService.convert_grades_to_codes.
   Maps codes back to binned_grade (e.g., "5.9" → code 9 → "5.9").
   Example: route_grade="5.10a" → binned_code=10, binned_grade="5.10a".
   Classification (using ClimbClassifier):
   discipline: Classifies as SPORT, TRAD, or BOULDER based on route_type or notes.
   send_bool: Determines if it’s a send (e.g., "Onsight" → True, "Project" → False).
   length_category: Based on length (e.g., "Short", "Medium", "Long").
   season_category: Based on tick_date (e.g., "Winter").
   Max Grades (\_calculate_max_grades):
   Tracks running max binned_code per discipline over time (e.g., cur_max_rp_sport).
   Example: After a 5.10a sport send, cur_max_rp_sport = 10.
   Crux Characteristics:
   crux_angle: Predicts from notes (e.g., "#overhang" → OVERHANG).
   crux_energy: Predicts from notes (e.g., "#endurance" → ENDURANCE).
   Difficulty Category (\_calculate_difficulty_category):
   Compares binned_code to cur_max*\* (e.g., 5.10a vs. max 5.9 → "Project").
   Data: Enhanced pd.DataFrame with columns like discipline, send_bool, cur_max_rp_sport, difficulty_category.
   Example: {"route_name": "The Nose", "tick_date": "2023-01-15", "route_grade": "5.9", "discipline": "TRAD", "send_bool": True, "cur_max_rp_trad": 9, "difficulty_category": "Base Volume"}.

6. Entity Building: \_build_entities

   Input: processed_df: pd.DataFrame, user_id: UUID.
   Action: Converts the processed DataFrame into database-ready entities.
   Steps:
   Filters processed_df to valid UserTicks columns (e.g., excludes temp columns like style).
   Cleans NaN values (e.g., strings → None, floats → None).
   Converts rows to a list of dictionaries (ticks_data).
   Extracts unique tags from a tag column (if present; typically empty in this version).
   Stores processed_df temporarily for PyramidBuilder (not used here as pyramids is empty).
   Data:
   ticks_data: List of dicts matching UserTicks (e.g., [{"route_name": "The Nose", "tick_date": "2023-01-15", ...}]).
   pyramid_data: Empty list ([])—pyramid building is deferred.
   tag_data: List of unique tags (e.g., [] if no tags).
   Output: (ticks_data, [], tag_data).

7. Database Commit: \_commit_to_database

   Input: ticks_data: List[Dict], pyramid_data: List[Dict], tag_data: List[str], user_id: UUID, logbook_type: LogbookType.
   Action: Persists entities to the database using DatabaseService.
   Steps:
   Opens a transaction with async with self.db.begin():.
   Ticks: await self.db_service.save_user_ticks(ticks_data, user_id):
   Creates UserTicks objects, sets user_id and created_at, adds to session.
   Flushes to generate IDs.
   Pyramids: await self.db_service.save_performance_pyramid(pyramid_data, user_id):
   Skipped (empty list).
   Tags: await self.db_service.save_tags(tag_data, [tick.id for tick in ticks]):
   Fetches UserTicks with selectinload(UserTicks.tags).
   Creates or reuses Tag objects, associates with ticks.
   Timestamp: await self.db_service.update_sync_timestamp(user_id, logbook_type):
   Updates mtn_project_last_sync to current time.
   Data:
   Database rows in user_ticks, tags, user_ticks_tags (junction table), and users (timestamp).
   Example: user_ticks row: {"id": 1, "user_id": "uuid", "route_name": "The Nose", ...}.
   Commit: Transaction commits automatically on success.

8. Return and Completion

   Output: \_process_ticks returns (ticks, pyramids, tags)—the persisted UserTicks objects, an empty PerformancePyramid list, and any Tag objects.
   Caller: The endpoint receives this tuple and can use it (though connect_logbook currently discards it, returning a status message).

Mountain Project vs. 8a.nu Differences

    Data Source:
        Mountain Project: CSV via HTTP (MountainProjectCSVClient).
        8a.nu: JSON via Playwright scraping (EightANuScraper), run synchronously in a thread.
    Normalization:
        Mountain Project: Maps CSV columns directly, minimal grade conversion (YDS-based).
        8a.nu: Converts French/Font grades to YDS/V-scale, derives location from crag/area.
    Fields:
        Mountain Project: Richer metadata (e.g., length, pitches).
        8a.nu: More route characteristics (e.g., isRoof, isEndurance) used in notes.

Visual Data Flow
text
[API: connect_logbook]
↓ (user_id, profile_url)
[process_logbook_data]
↓ (routes to process_mountain_project_ticks)
[process_mountain_project_ticks]
↓ (fetch raw_df)
[MountainProjectCSVClient.fetch_user_ticks]
↓ (raw_df: CSV DataFrame)
[_process_ticks]
↓ (raw_df)
[_normalize_data]
↓ (normalized_df)
[_process_data]
↓ (processed_df: enriched)
[_build_entities]
↓ (ticks_data, [], tag_data)
[_commit_to_database]
↓ (persists to DB)
[DatabaseService]
→ user_ticks, tags, users tables
[Return]
→ (ticks, pyramids, tags) back to caller
Key Interactions

    External Clients: MountainProjectCSVClient (async) and EightANuScraper (sync via executor).
    Processors: MountainProjectCSVProcessor and EightANuProcessor standardize data.
    Services: GradeService for grade conversions, ClimbClassifier for classifications, DatabaseService for persistence.
    Database: AsyncSession ensures atomic commits.

This flow ensures raw climbing data is fetched, transformed, enriched, and stored efficiently, with robust error handling and logging throughout.
