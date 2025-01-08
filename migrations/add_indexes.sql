-- Add indexes for UserTicks table
CREATE INDEX IF NOT EXISTS idx_user_ticks_username ON user_ticks(username);
CREATE INDEX IF NOT EXISTS idx_user_ticks_tick_date ON user_ticks(tick_date);

-- Add indexes for SportPyramid table
CREATE INDEX IF NOT EXISTS idx_sport_pyramid_username ON sport_pyramid(username);
CREATE INDEX IF NOT EXISTS idx_sport_pyramid_tick_date ON sport_pyramid(tick_date);

-- Add indexes for TradPyramid table
CREATE INDEX IF NOT EXISTS idx_trad_pyramid_username ON trad_pyramid(username);
CREATE INDEX IF NOT EXISTS idx_trad_pyramid_tick_date ON trad_pyramid(tick_date);

-- Add indexes for BoulderPyramid table
CREATE INDEX IF NOT EXISTS idx_boulder_pyramid_username ON boulder_pyramid(username);
CREATE INDEX IF NOT EXISTS idx_boulder_pyramid_tick_date ON boulder_pyramid(tick_date);
