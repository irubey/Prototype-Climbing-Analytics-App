#!/bin/bash

# Load environment variables from .env file
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
if [ -f "${SCRIPT_DIR}/../../.env" ]; then
    source "${SCRIPT_DIR}/../../.env"
fi

# Set database credentials from environment variables
export PGPASSWORD=$DB_PASSWORD

# Output file
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
OUTPUT_FILE="db_metrics_${TIMESTAMP}.txt"

echo "SendSage Database Metrics Report - $(date)" > $OUTPUT_FILE
echo "----------------------------------------" >> $OUTPUT_FILE

# Processing Volume
echo -e "\nProcessing Volume (Last 7 Days):" >> $OUTPUT_FILE
psql -h $DB_HOST -U $DB_USER $DB_NAME "sslmode=require" -c "
WITH metrics AS (
    SELECT 
        (SELECT COUNT(*) FROM user_ticks) as total_records,
        (SELECT COUNT(*) FROM sport_pyramid) as sport_records,
        (SELECT COUNT(*) FROM trad_pyramid) as trad_records,
        (SELECT COUNT(*) FROM boulder_pyramid) as boulder_records
)
SELECT 
    'Total Records Processed: ' || total_records as total_records,
    'Average Processing Rate: ' || ROUND(total_records::numeric / 7, 2) || ' records/day' as processing_rate,
    'Total Datapoints Processed: ' || (
        -- User_ticks (19 meaningful columns)
        (total_records * 19) + 
        -- Pyramid tables (18 meaningful columns each)
        ((sport_records + trad_records + boulder_records) * 18)
    ) as total_datapoints
FROM metrics;
" >> $OUTPUT_FILE

# User Adoption
echo -e "\nUser Adoption Metrics:" >> $OUTPUT_FILE
psql -h $DB_HOST -U $DB_USER $DB_NAME "sslmode=require" -c "
SELECT 
    'Total Users Onboarded: ' || COUNT(DISTINCT username) as total_users,
    'Average Records per User: ' || ROUND(COUNT(*)::numeric / COUNT(DISTINCT username), 2) as avg_records_per_user
FROM user_ticks;
" >> $OUTPUT_FILE

# Data Distribution by Discipline
echo -e "\nProcessed Data Distribution:" >> $OUTPUT_FILE
psql -h $DB_HOST -U $DB_USER $DB_NAME "sslmode=require" -c "
SELECT 
    discipline, 
    COUNT(*) as records_processed,
    ROUND(COUNT(*)::numeric / COUNT(DISTINCT username), 2) as avg_per_user,
    ROUND(COUNT(*)::numeric * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM user_ticks 
WHERE discipline IS NOT NULL
GROUP BY discipline
ORDER BY records_processed DESC;
" >> $OUTPUT_FILE

# Historical Range Coverage
echo -e "\nHistorical Data Coverage:" >> $OUTPUT_FILE
psql -h $DB_HOST -U $DB_USER $DB_NAME "sslmode=require" -c "
SELECT 
    MIN(tick_date) as earliest_record,
    MAX(tick_date) as latest_record,
    COUNT(DISTINCT tick_date) as unique_dates,
    COUNT(DISTINCT username) || ' users spanning ' || 
    (MAX(tick_date) - MIN(tick_date))::varchar || ' of climbing history' as coverage_summary
FROM user_ticks;
" >> $OUTPUT_FILE

# Top Users by Volume
echo -e "\nTop Users by Processing Volume:" >> $OUTPUT_FILE
psql -h $DB_HOST -U $DB_USER $DB_NAME "sslmode=require" -c "
SELECT 
    username,
    COUNT(*) as records_processed,
    ROUND(COUNT(*)::numeric * 100.0 / (SELECT COUNT(*) FROM user_ticks), 2) as percent_of_total,
    MAX(tick_date) - MIN(tick_date) as history_span
FROM user_ticks
GROUP BY username
ORDER BY records_processed DESC
LIMIT 5;
" >> $OUTPUT_FILE

echo "Metrics saved to $OUTPUT_FILE"