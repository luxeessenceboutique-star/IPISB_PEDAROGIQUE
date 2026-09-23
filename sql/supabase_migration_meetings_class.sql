-- Add class_id to meetings so a meeting can be assigned to a specific class
ALTER TABLE meetings
  ADD COLUMN IF NOT EXISTS class_id UUID REFERENCES classes(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_meetings_class_id ON meetings(class_id);
