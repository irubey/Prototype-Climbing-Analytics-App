-- Add location_raw column to user_ticks
ALTER TABLE user_ticks ADD COLUMN location_raw VARCHAR(255);

-- Update location_raw with existing location data
UPDATE user_ticks 
SET location_raw = location; 