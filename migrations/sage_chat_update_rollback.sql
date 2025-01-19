BEGIN;

DROP TRIGGER IF EXISTS update_climber_summary_timestamp ON climber_summary;
DROP FUNCTION IF EXISTS update_current_info_timestamp();
DROP TABLE IF EXISTS climber_summary;

DROP INDEX IF EXISTS idx_user_ticks_lookup;
DROP INDEX IF EXISTS idx_sport_pyramid_lookup;
DROP INDEX IF EXISTS idx_boulder_pyramid_userid;
DROP INDEX IF EXISTS idx_sport_pyramid_userid;
DROP INDEX IF EXISTS idx_trad_pyramid_userid;
DROP INDEX IF EXISTS idx_user_ticks_userid;
DROP INDEX IF EXISTS idx_boulder_pyramid_route_name;
DROP INDEX IF EXISTS idx_sport_pyramid_route_name;
DROP INDEX IF EXISTS idx_trad_pyramid_route_name;
DROP INDEX IF EXISTS idx_climber_summary_username;

ALTER TABLE user_ticks 
    ALTER COLUMN discipline TYPE VARCHAR(255),
    DROP COLUMN IF EXISTS userId,
    DROP COLUMN IF EXISTS user_profile_url,
    DROP COLUMN IF EXISTS route_stars,
    DROP COLUMN IF EXISTS user_stars,
    DROP COLUMN IF EXISTS created_at,
    DROP COLUMN IF EXISTS notes;

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

DROP TYPE IF EXISTS climbing_discipline;
DROP TYPE IF EXISTS route_characteristic;
DROP TYPE IF EXISTS climbing_style;
DROP TYPE IF EXISTS sleep_score;
DROP TYPE IF EXISTS nutrition_score;
DROP TYPE IF EXISTS session_length;
DROP TYPE IF EXISTS hold_type;

COMMIT;