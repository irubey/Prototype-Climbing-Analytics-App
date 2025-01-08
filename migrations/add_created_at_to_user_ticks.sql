-- Add created_at column to user_ticks table
ALTER TABLE user_ticks ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Update existing records to have current timestamp
UPDATE user_ticks SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL; 