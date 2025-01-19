BEGIN;

-- Create all ENUM types
CREATE TYPE climbing_discipline AS ENUM (
    'tr', 'boulder', 'sport', 'trad', 'mixed', 'winter_ice', 'aid'
);

CREATE TYPE route_characteristic AS ENUM (
    'Power', 'Power Endurance', 'Endurance', 'Technique'
);

CREATE TYPE climbing_style AS ENUM (
    'Slab', 'Vertical', 'Overhang', 'Roof'
);

CREATE TYPE sleep_score AS ENUM (
    'Poor', 'Fair', 'Good', 'Excellent'
);

CREATE TYPE nutrition_score AS ENUM (
    'Poor', 'Fair', 'Good', 'Excellent'
);

CREATE TYPE session_length AS ENUM (
    'Less than 1 hour', '1-2 hours', '2-3 hours', '3-4 hours', '4+ hours'
);

CREATE TYPE hold_type AS ENUM (
    'Crimps', 'Slopers', 'Pockets', 'Pinches', 'Cracks'
);

-- Update binned_code_dict constraint
ALTER TABLE binned_code_dict 
    ALTER COLUMN binned_grade SET NOT NULL;

-- Clean up any invalid data before conversion
UPDATE boulder_pyramid SET discipline = NULL WHERE discipline NOT IN ('tr', 'boulder', 'sport', 'trad', 'mixed', 'winter_ice', 'aid');
UPDATE sport_pyramid SET discipline = NULL WHERE discipline NOT IN ('tr', 'boulder', 'sport', 'trad', 'mixed', 'winter_ice', 'aid');
UPDATE trad_pyramid SET discipline = NULL WHERE discipline NOT IN ('tr', 'boulder', 'sport', 'trad', 'mixed', 'winter_ice', 'aid');
UPDATE user_ticks SET discipline = NULL WHERE discipline NOT IN ('tr', 'boulder', 'sport', 'trad', 'mixed', 'winter_ice', 'aid');

-- Update boulder_pyramid table
ALTER TABLE boulder_pyramid 
    ADD COLUMN IF NOT EXISTS userId BIGINT,
    ALTER COLUMN discipline TYPE climbing_discipline USING discipline::climbing_discipline,
    ALTER COLUMN route_characteristic TYPE route_characteristic USING route_characteristic::route_characteristic,
    ALTER COLUMN route_style TYPE climbing_style USING route_style::climbing_style;

-- Update sport_pyramid table
ALTER TABLE sport_pyramid 
    ADD COLUMN IF NOT EXISTS userId BIGINT,
    ALTER COLUMN discipline TYPE climbing_discipline USING discipline::climbing_discipline,
    ALTER COLUMN route_characteristic TYPE route_characteristic USING route_characteristic::route_characteristic,
    ALTER COLUMN route_style TYPE climbing_style USING route_style::climbing_style;

-- Update trad_pyramid table
ALTER TABLE trad_pyramid 
    ADD COLUMN IF NOT EXISTS userId BIGINT,
    ALTER COLUMN discipline TYPE climbing_discipline USING discipline::climbing_discipline,
    ALTER COLUMN route_characteristic TYPE route_characteristic USING route_characteristic::route_characteristic,
    ALTER COLUMN route_style TYPE climbing_style USING route_style::climbing_style;

-- Update user_ticks table
ALTER TABLE user_ticks 
    ADD COLUMN IF NOT EXISTS userId BIGINT,
    ADD COLUMN IF NOT EXISTS user_profile_url VARCHAR(255),
    ADD COLUMN IF NOT EXISTS route_stars FLOAT,
    ADD COLUMN IF NOT EXISTS user_stars FLOAT,
    ALTER COLUMN discipline TYPE climbing_discipline USING discipline::climbing_discipline;

-- Create all indexes
CREATE INDEX IF NOT EXISTS idx_boulder_pyramid_userid ON boulder_pyramid(userId);
CREATE INDEX IF NOT EXISTS idx_sport_pyramid_userid ON sport_pyramid(userId);
CREATE INDEX IF NOT EXISTS idx_trad_pyramid_userid ON trad_pyramid(userId);
CREATE INDEX IF NOT EXISTS idx_user_ticks_userid ON user_ticks(userId);

CREATE INDEX IF NOT EXISTS idx_boulder_pyramid_username ON boulder_pyramid(username);
CREATE INDEX IF NOT EXISTS idx_sport_pyramid_username ON sport_pyramid(username);
CREATE INDEX IF NOT EXISTS idx_trad_pyramid_username ON trad_pyramid(username);
CREATE INDEX IF NOT EXISTS idx_user_ticks_username ON user_ticks(username);

CREATE INDEX IF NOT EXISTS idx_boulder_pyramid_tick_date ON boulder_pyramid(tick_date);
CREATE INDEX IF NOT EXISTS idx_sport_pyramid_tick_date ON sport_pyramid(tick_date);
CREATE INDEX IF NOT EXISTS idx_trad_pyramid_tick_date ON trad_pyramid(tick_date);
CREATE INDEX IF NOT EXISTS idx_user_ticks_tick_date ON user_ticks(tick_date);

CREATE INDEX IF NOT EXISTS idx_boulder_pyramid_route_name ON boulder_pyramid(route_name);
CREATE INDEX IF NOT EXISTS idx_sport_pyramid_route_name ON sport_pyramid(route_name);
CREATE INDEX IF NOT EXISTS idx_trad_pyramid_route_name ON trad_pyramid(route_name);

CREATE INDEX IF NOT EXISTS idx_boulder_pyramid_lookup ON boulder_pyramid(username, route_name, tick_date);
CREATE INDEX IF NOT EXISTS idx_sport_pyramid_lookup ON sport_pyramid(username, route_name, tick_date);
CREATE INDEX IF NOT EXISTS idx_trad_pyramid_lookup ON trad_pyramid(username, route_name, tick_date);
CREATE INDEX IF NOT EXISTS idx_user_ticks_lookup ON user_ticks(username, route_name, tick_date);

-- Create climber_summary table
CREATE TABLE IF NOT EXISTS climber_summary (
    userId BIGINT PRIMARY KEY,
    username VARCHAR(255),
    
    -- Core progression metrics
    highest_sport_grade_tried VARCHAR(255),
    highest_trad_grade_tried VARCHAR(255),
    highest_boulder_grade_tried VARCHAR(255),
    total_climbs INTEGER,
    favorite_discipline climbing_discipline,
    years_climbing_outside INTEGER,
    preferred_crag_last_year VARCHAR(255),
    
    -- Training context
    training_frequency VARCHAR(255),
    typical_session_length session_length,
    has_hangboard BOOLEAN,
    has_home_wall BOOLEAN,
    goes_to_gym BOOLEAN,
    
    -- Performance metrics
    highest_grade_sport_sent_clean_on_lead VARCHAR(255),
    highest_grade_tr_sent_clean VARCHAR(255),
    highest_grade_trad_sent_clean_on_lead VARCHAR(255),
    highest_grade_boulder_sent_clean VARCHAR(255),
    onsight_grade_sport VARCHAR(255),
    onsight_grade_trad VARCHAR(255),
    flash_grade_boulder VARCHAR(255),
    
    -- Grade Pyramids
    grade_pyramid_sport JSONB,
    grade_pyramid_trad JSONB,
    grade_pyramid_boulder JSONB,
    
    -- Injury history and limitations
    current_injuries TEXT,
    injury_history TEXT,
    physical_limitations TEXT,
    
    -- Goals and preferences
    climbing_goals TEXT,
    willing_to_train_indoors BOOLEAN,
    
    -- Recent activity
    sends_last_30_days INTEGER,
    current_projects JSONB,
    
    -- Style preferences
    favorite_angle climbing_style,
    favorite_hold_types hold_type,
    weakest_style climbing_style,
    strongest_style climbing_style,
    favorite_energy_type route_characteristic,
    
    -- Lifestyle
    sleep_score sleep_score,
    nutrition_score nutrition_score,
    
    -- Additional info
    recent_favorite_routes JSONB,
    additional_notes TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    current_info_as_of TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on username for climber_summary
CREATE INDEX IF NOT EXISTS idx_climber_summary_username ON climber_summary(username);

-- Create timestamp update trigger
CREATE OR REPLACE FUNCTION update_current_info_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.current_info_as_of = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_climber_summary_timestamp ON climber_summary;
CREATE TRIGGER update_climber_summary_timestamp
    BEFORE UPDATE ON climber_summary
    FOR EACH ROW
    EXECUTE FUNCTION update_current_info_timestamp();

COMMIT;

-- Rollback script
/*
BEGIN;

-- Drop triggers and functions
DROP TRIGGER IF EXISTS update_climber_summary_timestamp ON climber_summary;
DROP FUNCTION IF EXISTS update_current_info_timestamp();

-- Drop all indexes
DROP INDEX IF EXISTS idx_climber_summary_username;
DROP INDEX IF EXISTS idx_boulder_pyramid_userid;
DROP INDEX IF EXISTS idx_sport_pyramid_userid;
DROP INDEX IF EXISTS idx_trad_pyramid_userid;
DROP INDEX IF EXISTS idx_user_ticks_userid;
DROP INDEX IF EXISTS idx_boulder_pyramid_username;
DROP INDEX IF EXISTS idx_sport_pyramid_username;
DROP INDEX IF EXISTS idx_trad_pyramid_username;
DROP INDEX IF EXISTS idx_user_ticks_username;
DROP INDEX IF EXISTS idx_boulder_pyramid_tick_date;
DROP INDEX IF EXISTS idx_sport_pyramid_tick_date;
DROP INDEX IF EXISTS idx_trad_pyramid_tick_date;
DROP INDEX IF EXISTS idx_user_ticks_tick_date;
DROP INDEX IF EXISTS idx_boulder_pyramid_route_name;
DROP INDEX IF EXISTS idx_sport_pyramid_route_name;
DROP INDEX IF EXISTS idx_trad_pyramid_route_name;
DROP INDEX IF EXISTS idx_boulder_pyramid_lookup;
DROP INDEX IF EXISTS idx_sport_pyramid_lookup;
DROP INDEX IF EXISTS idx_trad_pyramid_lookup;
DROP INDEX IF EXISTS idx_user_ticks_lookup;

-- Drop new table
DROP TABLE IF EXISTS climber_summary;

-- Revert column changes
ALTER TABLE user_ticks 
    ALTER COLUMN discipline TYPE VARCHAR(255),
    DROP COLUMN IF EXISTS userId,
    DROP COLUMN IF EXISTS user_profile_url,
    DROP COLUMN IF EXISTS route_stars,
    DROP COLUMN IF EXISTS user_stars;

ALTER TABLE trad_pyramid 
    ALTER COLUMN discipline TYPE VARCHAR(255),
    ALTER COLUMN route_characteristic TYPE VARCHAR(255),
    ALTER COLUMN route_style TYPE VARCHAR(255),
    DROP COLUMN IF EXISTS userId;

ALTER TABLE sport_pyramid 
    ALTER COLUMN discipline TYPE VARCHAR(255),
    ALTER COLUMN route_characteristic TYPE VARCHAR(255),
    ALTER COLUMN route_style TYPE VARCHAR(255),
    DROP COLUMN IF EXISTS userId;

ALTER TABLE boulder_pyramid 
    ALTER COLUMN discipline TYPE VARCHAR(255),
    ALTER COLUMN route_characteristic TYPE VARCHAR(255),
    ALTER COLUMN route_style TYPE VARCHAR(255),
    DROP COLUMN IF EXISTS userId;

ALTER TABLE binned_code_dict 
    ALTER COLUMN binned_grade DROP NOT NULL;

-- Drop ENUM types
DROP TYPE IF EXISTS climbing_discipline;
DROP TYPE IF EXISTS route_characteristic;
DROP TYPE IF EXISTS climbing_style;
DROP TYPE IF EXISTS sleep_score;
DROP TYPE IF EXISTS nutrition_score;
DROP TYPE IF EXISTS session_length;
DROP TYPE IF EXISTS hold_type;

COMMIT;
*/