-- Add tick_id column to sport_pyramid
ALTER TABLE sport_pyramid ADD COLUMN tick_id INTEGER;

-- Add tick_id column to trad_pyramid
ALTER TABLE trad_pyramid ADD COLUMN tick_id INTEGER;

-- Add tick_id column to boulder_pyramid
ALTER TABLE boulder_pyramid ADD COLUMN tick_id INTEGER;

-- Update tick_ids in sport_pyramid
UPDATE sport_pyramid sp
SET tick_id = (
    SELECT ut.id 
    FROM user_ticks ut 
    WHERE ut.username = sp.username 
    AND ut.route_name = sp.route_name 
    AND ut.tick_date = sp.tick_date
);

-- Update tick_ids in trad_pyramid
UPDATE trad_pyramid tp
SET tick_id = (
    SELECT ut.id 
    FROM user_ticks ut 
    WHERE ut.username = tp.username 
    AND ut.route_name = tp.route_name 
    AND ut.tick_date = tp.tick_date
);

-- Update tick_ids in boulder_pyramid
UPDATE boulder_pyramid bp
SET tick_id = (
    SELECT ut.id 
    FROM user_ticks ut 
    WHERE ut.username = bp.username 
    AND ut.route_name = bp.route_name 
    AND ut.tick_date = bp.tick_date
); 