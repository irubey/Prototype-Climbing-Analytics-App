-- Add userId to all pyramid tables
ALTER TABLE boulder_pyramid ADD COLUMN IF NOT EXISTS userId BIGINT;
ALTER TABLE sport_pyramid ADD COLUMN IF NOT EXISTS userId BIGINT;
ALTER TABLE trad_pyramid ADD COLUMN IF NOT EXISTS userId BIGINT;

-- Add new columns to user_ticks
ALTER TABLE user_ticks ADD COLUMN IF NOT EXISTS userId BIGINT;
ALTER TABLE user_ticks ADD COLUMN IF NOT EXISTS user_profile_url VARCHAR(255);
ALTER TABLE user_ticks ADD COLUMN IF NOT EXISTS route_stars FLOAT;
ALTER TABLE user_ticks ADD COLUMN IF NOT EXISTS user_stars FLOAT;

-- Create climber_summary table
CREATE TABLE IF NOT EXISTS climber_summary (
    userId BIGINT PRIMARY KEY,
    username VARCHAR(255),
    
    -- Core progression metrics
    highest_sport_grade_tried VARCHAR(255),
    highest_trad_grade_tried VARCHAR(255),
    highest_boulder_grade_tried VARCHAR(255),
    total_climbs INTEGER,
    favorite_discipline VARCHAR(50),
    years_climbing_outside INTEGER,
    preferred_crag_last_year VARCHAR(255),
    
    -- Training context
    training_frequency VARCHAR(50),
    typical_session_length VARCHAR(50),
    has_hangboard BOOLEAN,
    has_home_wall BOOLEAN,
    
    -- Performance metrics
    highest_grade_sport_sent_clean_on_lead VARCHAR(255),
    highest_grade_sport_sent_clean_on_top VARCHAR(255),
    highest_grade_trad_sent_clean_on_lead VARCHAR(255),
    highest_grade_trad_sent_clean_on_top VARCHAR(255),
    highest_grade_boulder_sent_clean VARCHAR(255),
    onsight_grade_sport VARCHAR(255),
    onsight_grade_trad VARCHAR(255),
    flash_grade_boulder VARCHAR(255),
    
    -- Grade Pyramids (stored as JSON strings)
    grade_pyramid_sport JSONB,
    grade_pyramid_trad JSONB,
    grade_pyramid_boulder JSONB,
    
    -- Injury history and limitations
    current_injuries TEXT,
    injury_history TEXT,
    physical_limitations TEXT,
    
    -- Goals and preferences
    climbing_goals TEXT,
    preferred_climbing_days VARCHAR(255),
    max_travel_distance INTEGER,
    willing_to_train_indoors BOOLEAN,
    
    -- Recent activity
    sends_last_30_days INTEGER,
    current_projects JSONB,
    
    -- Style preferences
    favorite_angle VARCHAR(50),
    favorite_hold_types VARCHAR(50),
    weakest_style VARCHAR(50),
    strongest_style VARCHAR(50),
    favorite_energy_type VARCHAR(50),
    
    -- Favorite Routes
    recent_favorite_routes JSONB,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_climber_summary_userid ON climber_summary(userId);
CREATE INDEX IF NOT EXISTS idx_boulder_pyramid_userid ON boulder_pyramid(userId);
CREATE INDEX IF NOT EXISTS idx_sport_pyramid_userid ON sport_pyramid(userId);
CREATE INDEX IF NOT EXISTS idx_trad_pyramid_userid ON trad_pyramid(userId);
CREATE INDEX IF NOT EXISTS idx_user_ticks_userid ON user_ticks(userId);

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_climber_summary_updated_at
    BEFORE UPDATE ON climber_summary
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Alter existing userId columns to BIGINT if they exist
DO $$ 
BEGIN
    -- Alter existing columns to BIGINT
    ALTER TABLE boulder_pyramid ALTER COLUMN userId TYPE BIGINT;
    ALTER TABLE sport_pyramid ALTER COLUMN userId TYPE BIGINT;
    ALTER TABLE trad_pyramid ALTER COLUMN userId TYPE BIGINT;
    ALTER TABLE user_ticks ALTER COLUMN userId TYPE BIGINT;
    ALTER TABLE climber_summary ALTER COLUMN userId TYPE BIGINT;
EXCEPTION
    WHEN undefined_column THEN 
        NULL;  -- Ignore if column doesn't exist
END $$;

-- Update lead_style enum type
DO $$
BEGIN
    -- Drop all existing enum types
    DROP TYPE IF EXISTS leadstyle CASCADE;
    DROP TYPE IF EXISTS climbingdiscipline CASCADE;
    DROP TYPE IF EXISTS trainingfrequency CASCADE;
    DROP TYPE IF EXISTS sessionlength CASCADE;
    DROP TYPE IF EXISTS climbingstyle CASCADE;
    DROP TYPE IF EXISTS routecharacteristic CASCADE;
    DROP TYPE IF EXISTS holdtype CASCADE;
    
    -- Create all enum types with correct values
    CREATE TYPE leadstyle AS ENUM ('Redpoint', 'Fell/Hung', 'Flash', 'Onsight', 'Pinkpoint');
    CREATE TYPE climbingdiscipline AS ENUM ('tr', 'boulder', 'sport', 'trad', 'mixed', 'winter_ice', 'aid');
    CREATE TYPE trainingfrequency AS ENUM ('Never', 'Occasionally', 'Once a week', 'Twice a week', 'Three or more times a week');
    CREATE TYPE sessionlength AS ENUM ('Less than 1 hour', '1-2 hours', '2-3 hours', '3-4 hours', '4+ hours');
    CREATE TYPE climbingstyle AS ENUM ('Slab', 'Vertical', 'Overhang', 'Roof');
    CREATE TYPE routecharacteristic AS ENUM ('Power', 'Power Endurance', 'Endurance', 'Technique');
    CREATE TYPE holdtype AS ENUM ('Crimps', 'Slopers', 'Pockets', 'Pinches', 'Cracks');
    
    -- Add columns back to tables
    -- Sport Pyramid
    ALTER TABLE sport_pyramid ADD COLUMN IF NOT EXISTS lead_style leadstyle;
    ALTER TABLE sport_pyramid ADD COLUMN IF NOT EXISTS discipline climbingdiscipline;
    ALTER TABLE sport_pyramid ADD COLUMN IF NOT EXISTS route_characteristic routecharacteristic;
    ALTER TABLE sport_pyramid ADD COLUMN IF NOT EXISTS route_style climbingstyle;
    
    -- Trad Pyramid
    ALTER TABLE trad_pyramid ADD COLUMN IF NOT EXISTS lead_style leadstyle;
    ALTER TABLE trad_pyramid ADD COLUMN IF NOT EXISTS discipline climbingdiscipline;
    ALTER TABLE trad_pyramid ADD COLUMN IF NOT EXISTS route_characteristic routecharacteristic;
    ALTER TABLE trad_pyramid ADD COLUMN IF NOT EXISTS route_style climbingstyle;
    
    -- Boulder Pyramid
    ALTER TABLE boulder_pyramid ADD COLUMN IF NOT EXISTS lead_style leadstyle;
    ALTER TABLE boulder_pyramid ADD COLUMN IF NOT EXISTS discipline climbingdiscipline;
    ALTER TABLE boulder_pyramid ADD COLUMN IF NOT EXISTS route_characteristic routecharacteristic;
    ALTER TABLE boulder_pyramid ADD COLUMN IF NOT EXISTS route_style climbingstyle;
    
    -- User Ticks
    ALTER TABLE user_ticks ADD COLUMN IF NOT EXISTS lead_style leadstyle;
    ALTER TABLE user_ticks ADD COLUMN IF NOT EXISTS discipline climbingdiscipline;
    
    -- Climber Summary
    ALTER TABLE climber_summary ADD COLUMN IF NOT EXISTS favorite_discipline climbingdiscipline;
    ALTER TABLE climber_summary ADD COLUMN IF NOT EXISTS training_frequency trainingfrequency;
    ALTER TABLE climber_summary ADD COLUMN IF NOT EXISTS typical_session_length sessionlength;
    ALTER TABLE climber_summary ADD COLUMN IF NOT EXISTS favorite_angle climbingstyle;
    ALTER TABLE climber_summary ADD COLUMN IF NOT EXISTS favorite_hold_types holdtype;
    ALTER TABLE climber_summary ADD COLUMN IF NOT EXISTS weakest_style climbingstyle;
    ALTER TABLE climber_summary ADD COLUMN IF NOT EXISTS strongest_style climbingstyle;
    ALTER TABLE climber_summary ADD COLUMN IF NOT EXISTS favorite_energy_type routecharacteristic;

    -- Set default values where appropriate
    UPDATE sport_pyramid SET discipline = 'sport' WHERE discipline IS NULL;
    UPDATE trad_pyramid SET discipline = 'trad' WHERE discipline IS NULL;
    UPDATE boulder_pyramid SET discipline = 'boulder' WHERE discipline IS NULL;
END $$;

-- Change favorite_style to favorite_discipline
ALTER TABLE climber_summary RENAME COLUMN favorite_discipline TO favorite_style;

-- If the column doesn't exist yet, add it with the correct name
ALTER TABLE climber_summary ADD COLUMN IF NOT EXISTS favorite_style climbingdiscipline;
