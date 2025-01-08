-- Add compound index for efficient tick lookups
CREATE INDEX IF NOT EXISTS idx_user_ticks_lookup 
ON user_ticks(username, route_name, tick_date);

-- Add compound indexes for pyramids for consistent performance
CREATE INDEX IF NOT EXISTS idx_sport_pyramid_lookup 
ON sport_pyramid(username, route_name, tick_date);

CREATE INDEX IF NOT EXISTS idx_trad_pyramid_lookup 
ON trad_pyramid(username, route_name, tick_date);

CREATE INDEX IF NOT EXISTS idx_boulder_pyramid_lookup 
ON boulder_pyramid(username, route_name, tick_date); 