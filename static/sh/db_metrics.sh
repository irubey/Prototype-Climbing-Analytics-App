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
        COUNT(*) as records
    FROM user_ticks
    WHERE created_at >= NOW() - INTERVAL '24 hours'
    GROUP BY hour
    ORDER BY hour DESC
)
SELECT 
    'Records Ingested (24h): ' || COALESCE(SUM(records), 0) as recent_ingestion,
    'Peak Hourly Ingestion: ' || COALESCE(MAX(records), 0) || ' records/hour' as peak_rate,
    'Average Hourly Ingestion: ' || COALESCE(ROUND(AVG(records), 2), 0) || ' records/hour' as avg_rate
FROM hourly_stats;
" >> "$OUTPUT_FILE"
echo "Done"

echo -n "Calculating data analysis timing... "
echo -e "\nData Analysis Timing:" >> "$OUTPUT_FILE"
psql "$CONN_STRING" -c "
SELECT 
    'Median Record Age: ' || 
    COALESCE(ROUND(EXTRACT(EPOCH FROM (
        percentile_cont(0.5) WITHIN GROUP (ORDER BY created_at - tick_date)
    ))/86400, 2), 0) || ' days' as median_age,
    'Average Record Age: ' || 
    COALESCE(ROUND(EXTRACT(EPOCH FROM (
        AVG(created_at - tick_date)
    ))/86400, 2), 0) || ' days' as avg_age,
    'Oldest Analyzed Record: ' ||
    COALESCE(MAX(created_at - tick_date), INTERVAL '0') || ' old' as oldest_record,
    'Most Recent Analysis: ' ||
    COALESCE(NOW() - MIN(created_at), INTERVAL '0') || ' ago' as latest_analysis
FROM user_ticks
WHERE created_at >= NOW() - INTERVAL '7 days';
" >> "$OUTPUT_FILE"
echo "Done"

# User Adoption
echo -n "Gathering user adoption metrics... "
echo -e "\nUser Engagement Metrics:" >> "$OUTPUT_FILE"
psql "$CONN_STRING" -c "
WITH user_stats AS (
    SELECT 
        COUNT(DISTINCT username) as total_users,
        COUNT(*) as total_records,
        COUNT(DISTINCT username) FILTER (WHERE created_at >= NOW() - INTERVAL '30 days') as active_users
    FROM user_ticks
)
SELECT 
    'Total Users: ' || total_users as total_users,
    'Monthly Active Users: ' || active_users as active_users,
    'Average Records per User: ' || ROUND(total_records::numeric / NULLIF(total_users, 0), 2) as avg_records_per_user,
    'User Retention Rate: ' || 
    ROUND((active_users::numeric / NULLIF(total_users, 0)) * 100, 2) || '%' as retention_rate
FROM user_stats;
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