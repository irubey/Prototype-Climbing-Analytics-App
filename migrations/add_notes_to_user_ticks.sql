-- Add notes column to user_ticks table
ALTER TABLE user_ticks
ADD COLUMN notes TEXT;

-- Add an index on the notes column for better query performance
CREATE INDEX idx_user_ticks_notes ON user_ticks(notes); 