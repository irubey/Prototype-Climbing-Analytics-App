#!/bin/bash

# Get the directory where the script is located and the project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Create results directory if it doesn't exist
RESULTS_DIR="${SCRIPT_DIR}/results"
mkdir -p "$RESULTS_DIR"

# Set up output file in results directory
TIMESTAMP=$(date '+%Y-%m-%d_at_%H-%M-%S')
OUTPUT_FILE="${RESULTS_DIR}/db_metrics_${TIMESTAMP}.txt"

# Load environment variables from .env file
if [ -f "../../.env" ]; then
    source "../../.env"
fi

# Set database credentials from environment variables
export PGPASSWORD=$DB_PASSWORD

# Output file with readable name format
DATE_PART=$(date +"%Y-%m-%d")
TIME_PART=$(date +"%H-%M-%S")
OUTPUT_FILE="${RESULTS_DIR}/db_metrics_${DATE_PART}_at_${TIME_PART}.txt"

# Create connection string with SSL mode
CONN_STRING="host=$DB_HOST port=5432 dbname=$DB_NAME user=$DB_USER sslmode=require"

echo "Starting database metrics collection..."
echo "Database Metrics Report - Generated on $(date)" > "$OUTPUT_FILE"
echo "=================================================" >> "$OUTPUT_FILE"

# Processing Volume
echo -n "Processing volume metrics... "
echo -e "\nTotal Processing Volume:" >> "$OUTPUT_FILE"
psql "$CONN_STRING" -c "
WITH metrics AS (
    SELECT 
        (SELECT COUNT(*) FROM user_ticks) as total_records,
        (SELECT COUNT(*) FROM sport_pyramid) as sport_records,
        (SELECT COUNT(*) FROM trad_pyramid) as trad_records,
        (SELECT COUNT(*) FROM boulder_pyramid) as boulder_records,
        (SELECT COUNT(*) FROM user_ticks WHERE created_at >= NOW() - INTERVAL '7 days') as recent_records
)
SELECT 
    'All-Time Records Processed: ' || total_records as total_records,
    'Last 7 Days Processing: ' || recent_records as recent_records,
    'Daily Processing Rate (7d): ' || ROUND(recent_records::numeric / 7, 2) || ' records/day' as processing_rate,
    'Total Data Points (All Tables): ' || (
        -- User_ticks (19 meaningful columns)
        (total_records * 19) + 
        -- Pyramid tables (18 meaningful columns each)
        ((sport_records + trad_records + boulder_records) * 18)
    ) as total_datapoints
FROM metrics;
" >> "$OUTPUT_FILE"
echo "Done"

# Data Ingestion Metrics
echo -n "Analyzing ingestion patterns... "
echo -e "\nReal-time Ingestion Metrics (Last 24h):" >> "$OUTPUT_FILE"
psql "$CONN_STRING" -c "
WITH hourly_stats AS (
    SELECT 
        date_trunc('hour', created_at) as hour,
        COUNT(*) as records,
        COUNT(DISTINCT username) as unique_users
    FROM user_ticks
    WHERE created_at >= NOW() - INTERVAL '24 hours'
    GROUP BY hour
    ORDER BY hour DESC
)
SELECT 
    'Records Ingested (24h): ' || COALESCE(SUM(records), 0) as recent_ingestion,
    'Peak Hourly Ingestion: ' || COALESCE(MAX(records), 0) || ' records/hour' as peak_rate,
    'Average Hourly Ingestion: ' || COALESCE(ROUND(AVG(records), 2), 0) || ' records/hour' as avg_rate,
    'Unique Users (24h): ' || COUNT(DISTINCT unique_users) as active_users
FROM hourly_stats;
" >> "$OUTPUT_FILE"

echo -e "\nMost Recent Ingestion Details:" >> "$OUTPUT_FILE"
psql "$CONN_STRING" -c "
WITH absolute_latest AS (
    SELECT 
        MAX(created_at) as latest_upload,
        username as latest_user,
        COUNT(*) as upload_size
    FROM user_ticks
    GROUP BY username
    ORDER BY MAX(created_at) DESC
    LIMIT 1
),
recent_ingestion AS (
    SELECT 
        username,
        created_at,
        COUNT(*) OVER (PARTITION BY username) as batch_size,
        MIN(created_at) OVER (PARTITION BY username) as batch_start,
        MAX(created_at) OVER (PARTITION BY username) as batch_end,
        FIRST_VALUE(tick_date) OVER (PARTITION BY username ORDER BY created_at DESC) as most_recent_climb_date,
        ROW_NUMBER() OVER (ORDER BY created_at DESC) as rn
    FROM user_ticks
    WHERE created_at >= NOW() - INTERVAL '1 hour'
),
latest_stats AS (
    SELECT DISTINCT
        username,
        batch_size,
        batch_start,
        batch_end,
        most_recent_climb_date,
        EXTRACT(EPOCH FROM (batch_end - batch_start)) as batch_duration_seconds
    FROM recent_ingestion
    WHERE rn <= 50  -- Limit to most recent 50 records
),
summary_stats AS (
    SELECT 
        CASE 
            WHEN COUNT(*) = 0 THEN 
                (SELECT 'Latest Upload: ' || latest_user || ' (' || upload_size || ' records) ' || 
                        NOW() - latest_upload || ' ago' 
                 FROM absolute_latest)
            ELSE 'Latest Upload: ' || NOW() - MAX(batch_end) || ' ago'
        END as last_upload,
        CASE 
            WHEN COUNT(*) = 0 THEN 'No active upload sessions in the last hour'
            ELSE 'Recent Upload Sessions: ' || COUNT(DISTINCT username) || ' users'
        END as recent_users,
        CASE 
            WHEN COUNT(*) = 0 THEN NULL
            ELSE 'Largest Recent Batch: ' || MAX(batch_size) || ' records'
        END as max_batch,
        CASE 
            WHEN COUNT(*) = 0 THEN NULL
            ELSE 'Average Batch Size: ' || ROUND(AVG(batch_size), 1) || ' records'
        END as avg_batch,
        CASE 
            WHEN COUNT(*) = 0 THEN NULL
            WHEN AVG(batch_duration_seconds) < 1 THEN 'Average Processing Time: sub-second'
            ELSE 'Average Processing Time: ' || ROUND(AVG(batch_duration_seconds), 1) || ' seconds'
        END as avg_processing_time
    FROM latest_stats
)
SELECT 
    last_upload,
    recent_users,
    COALESCE(max_batch, 'N/A') as max_batch,
    COALESCE(avg_batch, 'N/A') as avg_batch,
    COALESCE(avg_processing_time, 'N/A') as avg_processing_time
FROM summary_stats;
" >> "$OUTPUT_FILE"

echo -e "\nRecent Upload Sessions (Last Hour):" >> "$OUTPUT_FILE"
psql "$CONN_STRING" -c "
WITH recent_uploads AS (
    SELECT DISTINCT ON (username)
        username,
        COUNT(*) OVER (PARTITION BY username) as records_uploaded,
        MIN(created_at) OVER (PARTITION BY username) as session_start,
        MAX(created_at) OVER (PARTITION BY username) as session_end,
        MIN(tick_date) OVER (PARTITION BY username) as earliest_climb,
        MAX(tick_date) OVER (PARTITION BY username) as latest_climb,
        (SELECT COUNT(DISTINCT discipline) 
         FROM user_ticks t2 
         WHERE t2.username = t1.username 
         AND t2.created_at >= NOW() - INTERVAL '1 hour') as disciplines_count,
        (SELECT STRING_AGG(DISTINCT discipline, ', ') 
         FROM user_ticks t2 
         WHERE t2.username = t1.username 
         AND t2.created_at >= NOW() - INTERVAL '1 hour') as disciplines_list
    FROM user_ticks t1
    WHERE created_at >= NOW() - INTERVAL '1 hour'
    ORDER BY username, created_at DESC
),
upload_summary AS (
    SELECT 
        COUNT(*) as total_sessions
    FROM recent_uploads
)
SELECT 
    CASE 
        WHEN (SELECT total_sessions FROM upload_summary) = 0 THEN 'No upload sessions in the last hour'
        ELSE r.username || ': ' || r.records_uploaded || ' records'
    END as upload_session,
    COALESCE(r.session_start::time(0) || ' to ' || r.session_end::time(0), 'N/A') as upload_time,
    COALESCE(r.earliest_climb || ' to ' || r.latest_climb, 'N/A') as climb_date_range,
    COALESCE(EXTRACT(EPOCH FROM (r.session_end - r.session_start))::integer || ' seconds', 'N/A') as processing_time,
    COALESCE(r.disciplines_count || ' disciplines (' || r.disciplines_list || ')', 'N/A') as upload_composition
FROM recent_uploads r
ORDER BY r.session_end DESC
LIMIT 5;
" >> "$OUTPUT_FILE"
echo "Done"

echo -n "Calculating data analysis timing... "
echo -e "\nTemporal Analysis:" >> "$OUTPUT_FILE"
psql "$CONN_STRING" -c "
WITH time_metrics AS (
    SELECT 
        -- Historical climbing metrics
        MIN(tick_date) as earliest_climb,
        MAX(tick_date) as latest_climb,
        -- Ingestion metrics
        MIN(created_at) as earliest_ingestion,
        MAX(created_at) as latest_ingestion,
        -- Upload delay analysis
        percentile_cont(0.5) WITHIN GROUP (ORDER BY created_at - tick_date) as median_upload_delay,
        AVG(created_at - tick_date) as avg_upload_delay,
        -- Recent activity
        COUNT(*) FILTER (WHERE tick_date >= NOW() - INTERVAL '30 days') as recent_climbs,
        COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '30 days') as recent_uploads
    FROM user_ticks
)
SELECT 
    -- Historical Timeline
    'Historical Range: ' || 
    earliest_climb || ' to ' || latest_climb || 
    ' (' || (latest_climb - earliest_climb) || ' span)' as climbing_history,
    
    -- Ingestion Timeline
    'Data Ingestion Period: ' ||
    earliest_ingestion || ' to ' || latest_ingestion ||
    ' (' || (latest_ingestion - earliest_ingestion) || ' span)' as ingestion_period,
    
    -- Upload Patterns
    'Typical Upload Delay: ' ||
    ROUND(EXTRACT(EPOCH FROM median_upload_delay)/86400, 1) || ' days (median), ' ||
    ROUND(EXTRACT(EPOCH FROM avg_upload_delay)/86400, 1) || ' days (mean)' as upload_patterns,
    
    -- Recent Activity
    'Last 30 Days Activity: ' ||
    recent_climbs || ' climbs logged, ' ||
    recent_uploads || ' new uploads' as recent_activity
FROM time_metrics;
" >> "$OUTPUT_FILE"

echo -e "\nUpload Delay Distribution:" >> "$OUTPUT_FILE"
psql "$CONN_STRING" -c "
WITH delay_buckets AS (
    SELECT 
        CASE 
            WHEN created_at - tick_date < INTERVAL '1 day' THEN 'Same day'
            WHEN created_at - tick_date < INTERVAL '7 days' THEN 'Within a week'
            WHEN created_at - tick_date < INTERVAL '30 days' THEN 'Within a month'
            WHEN created_at - tick_date < INTERVAL '90 days' THEN 'Within 3 months'
            WHEN created_at - tick_date < INTERVAL '365 days' THEN 'Within a year'
            ELSE 'Over a year'
        END as delay_category,
        COUNT(*) as count
    FROM user_ticks
    GROUP BY delay_category
)
SELECT 
    delay_category,
    count || ' records (' || 
    ROUND(100.0 * count / SUM(count) OVER (), 1) || '%)' as distribution
FROM delay_buckets
ORDER BY 
    CASE delay_category
        WHEN 'Same day' THEN 1
        WHEN 'Within a week' THEN 2
        WHEN 'Within a month' THEN 3
        WHEN 'Within 3 months' THEN 4
        WHEN 'Within a year' THEN 5
        ELSE 6
    END;
" >> "$OUTPUT_FILE"

# User Adoption with Enhanced Metrics
echo -n "Gathering user adoption metrics... "
echo -e "\nUser Engagement Metrics:" >> "$OUTPUT_FILE"
psql "$CONN_STRING" -c "
WITH user_stats AS (
    SELECT 
        COUNT(DISTINCT username) as total_users,
        COUNT(*) as total_records,
        COUNT(DISTINCT username) FILTER (WHERE created_at >= NOW() - INTERVAL '30 days') as active_users,
        COUNT(DISTINCT username) FILTER (WHERE created_at >= NOW() - INTERVAL '24 hours') as daily_active_users,
        COUNT(DISTINCT username) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days') as weekly_active_users
    FROM user_ticks
)
SELECT 
    'Total Users: ' || total_users as total_users,
    'Daily Active Users: ' || daily_active_users as daily_active,
    'Weekly Active Users: ' || weekly_active_users as weekly_active,
    'Monthly Active Users: ' || active_users as monthly_active,
    'Average Records per User: ' || ROUND(total_records::numeric / NULLIF(total_users, 0), 2) as avg_records_per_user,
    'Monthly Retention Rate: ' || 
    ROUND((active_users::numeric / NULLIF(total_users, 0)) * 100, 2) || '%' as monthly_retention,
    'Daily/Monthly Ratio: ' ||
    ROUND((daily_active_users::numeric / NULLIF(active_users, 0)) * 100, 2) || '%' as daily_engagement
FROM user_stats;
" >> "$OUTPUT_FILE"

# Data Quality Metrics
echo -e "\nData Quality Metrics:" >> "$OUTPUT_FILE"
psql "$CONN_STRING" -c "
WITH quality_metrics AS (
    SELECT 
        COUNT(*) as total_records,
        COUNT(*) FILTER (WHERE 
            route_name IS NOT NULL AND 
            route_grade IS NOT NULL AND 
            tick_date IS NOT NULL AND 
            discipline IS NOT NULL AND
            location IS NOT NULL
        ) as complete_records,
        COUNT(*) FILTER (WHERE notes IS NOT NULL AND LENGTH(TRIM(notes)) > 0) as records_with_notes,
        COUNT(*) FILTER (WHERE length IS NOT NULL) as records_with_length,
        COUNT(*) FILTER (WHERE pitches IS NOT NULL) as records_with_pitches
    FROM user_ticks
),
recent_quality AS (
    SELECT 
        DATE_TRUNC('day', created_at) as upload_date,
        COUNT(*) as daily_records,
        ROUND(100.0 * COUNT(*) FILTER (WHERE 
            route_name IS NOT NULL AND 
            route_grade IS NOT NULL AND 
            tick_date IS NOT NULL AND 
            discipline IS NOT NULL AND
            location IS NOT NULL
        ) / NULLIF(COUNT(*), 0), 2) as daily_completeness
    FROM user_ticks
    WHERE created_at >= NOW() - INTERVAL '7 days'
    GROUP BY DATE_TRUNC('day', created_at)
),
quality_summary AS (
    SELECT 
        'Overall Data Completeness: ' ||
        ROUND(100.0 * complete_records / NULLIF(total_records, 0), 2) || '%' as completeness_rate,
        'Records with Notes: ' ||
        ROUND(100.0 * records_with_notes / NULLIF(total_records, 0), 2) || '%' as notes_rate,
        'Length Data Coverage: ' ||
        ROUND(100.0 * records_with_length / NULLIF(total_records, 0), 2) || '%' as length_coverage,
        'Pitch Data Coverage: ' ||
        ROUND(100.0 * records_with_pitches / NULLIF(total_records, 0), 2) || '%' as pitch_coverage
    FROM quality_metrics
),
trend_summary AS (
    SELECT 
        'Recent Data Quality Trend (7 days): ' ||
        STRING_AGG(daily_completeness::text || '%', ' → ' ORDER BY upload_date) as quality_trend
    FROM recent_quality
)
SELECT 
    completeness_rate,
    notes_rate,
    length_coverage,
    pitch_coverage,
    COALESCE(quality_trend, 'No data in the last 7 days') as quality_trend
FROM quality_summary
CROSS JOIN trend_summary;
" >> "$OUTPUT_FILE"
echo "Done"

# Data Distribution by Discipline
echo -n "Analyzing discipline distribution... "
echo -e "\nClimbing Discipline Distribution:" >> "$OUTPUT_FILE"
psql "$CONN_STRING" -c "
WITH discipline_stats AS (
    SELECT 
        COALESCE(discipline, 'Unspecified') as discipline_type,
        COUNT(*) as record_count,
        COUNT(DISTINCT username) as unique_users
    FROM user_ticks 
    GROUP BY discipline
)
SELECT 
    discipline_type as discipline,
    record_count as total_records,
    unique_users as active_users,
    ROUND(record_count::numeric / unique_users, 2) as avg_records_per_user,
    ROUND(record_count::numeric * 100.0 / SUM(record_count) OVER (), 2) || '%' as volume_percentage
FROM discipline_stats
ORDER BY record_count DESC;
" >> "$OUTPUT_FILE"
echo "Done"

# Historical Range Coverage
echo -n "Computing historical coverage... "
echo -e "\nHistorical Data Coverage:" >> "$OUTPUT_FILE"
psql "$CONN_STRING" -c "
WITH coverage_stats AS (
    SELECT 
        MIN(tick_date) as first_date,
        MAX(tick_date) as last_date,
        COUNT(DISTINCT tick_date) as unique_dates,
        COUNT(DISTINCT username) as total_users,
        MAX(tick_date) - MIN(tick_date) as date_span,
        CASE 
            WHEN MAX(tick_date) = MIN(tick_date) THEN 1
            ELSE (EXTRACT(epoch FROM AGE(MAX(tick_date), MIN(tick_date)))/86400)::integer + 1
        END as days_span
    FROM user_ticks
)
SELECT 
    'First Recorded Date: ' || first_date as earliest_record,
    'Most Recent Date: ' || last_date as latest_record,
    'Unique Climbing Days: ' || unique_dates as active_days,
    'Historical Coverage: ' || 
    total_users || ' users across ' || 
    date_span || ' (' ||
    ROUND((unique_dates::numeric / NULLIF(days_span, 0) * 100), 2) || '% coverage)' as coverage_summary
FROM coverage_stats;
" >> "$OUTPUT_FILE"
echo "Done"

# Top Users by Volume
echo -n "Identifying top users by volume... "
echo -e "\nMost Active Users:" >> "$OUTPUT_FILE"
psql "$CONN_STRING" -c "
WITH user_metrics AS (
    SELECT 
        username,
        COUNT(*) as total_records,
        MAX(tick_date) - MIN(tick_date) as activity_span,
        CASE 
            WHEN MAX(tick_date) = MIN(tick_date) THEN COUNT(*)::numeric
            ELSE COUNT(*)::numeric / NULLIF((EXTRACT(epoch FROM AGE(MAX(tick_date), MIN(tick_date)))/86400)::integer + 1, 0)
        END as avg_daily_activity
    FROM user_ticks
    GROUP BY username
)
SELECT 
    username,
    total_records || ' records' as total_activity,
    ROUND(total_records::numeric * 100.0 / (SELECT COUNT(*) FROM user_ticks), 2) || '%' as total_contribution,
    activity_span as climbing_history_span,
    CASE 
        WHEN avg_daily_activity IS NULL THEN '1 day only'
        ELSE ROUND(avg_daily_activity, 2) || ' records/day'
    END as activity_rate
FROM user_metrics
ORDER BY total_records DESC
LIMIT 5;
" >> "$OUTPUT_FILE"
echo "Done"

# Notes Analysis
echo -n "Analyzing climbing notes patterns... "
echo -e "\nNotes Analysis:" >> "$OUTPUT_FILE"
psql "$CONN_STRING" -c "
WITH notes_stats AS (
    SELECT 
        discipline,
        COUNT(*) as total_ticks,
        COUNT(CASE WHEN notes IS NOT NULL AND notes != '' THEN 1 END) as ticks_with_notes,
        ROUND(AVG(LENGTH(notes)) FILTER (WHERE notes IS NOT NULL AND notes != ''), 2) as avg_note_length,
        COUNT(CASE WHEN notes ILIKE '%crux%' OR notes ILIKE '%beta%' THEN 1 END) as technical_notes,
        COUNT(CASE WHEN notes ILIKE '%first%' OR notes ILIKE '%onsight%' OR notes ILIKE '%flash%' THEN 1 END) as achievement_notes,
        COUNT(CASE WHEN notes ILIKE '%wet%' OR notes ILIKE '%cold%' OR notes ILIKE '%hot%' OR notes ILIKE '%conditions%' THEN 1 END) as condition_notes,
        COUNT(CASE WHEN notes ILIKE '%scary%' OR notes ILIKE '%dangerous%' OR notes ILIKE '%safe%' OR notes ILIKE '%sketch%' THEN 1 END) as safety_notes
    FROM user_ticks
    GROUP BY discipline
)
SELECT 
    COALESCE(discipline, 'Unspecified') as discipline,
    total_ticks || ' total climbs' as total_climbs,
    ticks_with_notes || ' (' || ROUND(100.0 * ticks_with_notes / NULLIF(total_ticks, 0), 1) || '%)' as climbs_with_notes,
    avg_note_length || ' chars' as avg_note_length,
    technical_notes || ' (' || ROUND(100.0 * technical_notes / NULLIF(ticks_with_notes, 0), 1) || '%)' as technical_beta_notes,
    achievement_notes || ' (' || ROUND(100.0 * achievement_notes / NULLIF(ticks_with_notes, 0), 1) || '%)' as achievement_notes,
    condition_notes || ' (' || ROUND(100.0 * condition_notes / NULLIF(ticks_with_notes, 0), 1) || '%)' as condition_notes,
    safety_notes || ' (' || ROUND(100.0 * safety_notes / NULLIF(ticks_with_notes, 0), 1) || '%)' as safety_notes
FROM notes_stats
ORDER BY total_ticks DESC;
" >> "$OUTPUT_FILE"

echo -e "\nMost Common Note Themes:" >> "$OUTPUT_FILE"
psql "$CONN_STRING" -c "
WITH common_words AS (
    SELECT 
        word,
        COUNT(*) as frequency,
        ROUND(AVG(LENGTH(notes)), 2) as avg_note_length,
        STRING_AGG(DISTINCT discipline, ', ') as disciplines
    FROM (
        SELECT 
            discipline,
            notes,
            regexp_split_to_table(
                lower(regexp_replace(notes, '[^a-zA-Z\s]', ' ', 'g')), 
                '\s+'
            ) as word
        FROM user_ticks
        WHERE notes IS NOT NULL AND notes != ''
    ) words
    WHERE length(word) > 3  -- Filter out short words
    AND word NOT IN ('with', 'that', 'this', 'then', 'from', 'have', 'were', 'when', 'what', 'your')  -- Common stop words
    GROUP BY word
    HAVING COUNT(*) > 5  -- Minimum frequency threshold
)
SELECT 
    word as theme,
    frequency || ' mentions' as occurrences,
    avg_note_length || ' chars' as avg_note_length,
    disciplines as found_in_disciplines
FROM common_words
ORDER BY frequency DESC
LIMIT 15;
" >> "$OUTPUT_FILE"
echo "Done"

echo "✓ Metrics collection complete! Results saved to $OUTPUT_FILE"