DROP INDEX IF EXISTS idx_events_status;
DROP INDEX IF EXISTS idx_events_event_date;
DROP INDEX IF EXISTS idx_events_created_by;

DROP TABLE IF EXISTS events;
DROP TYPE IF EXISTS event_status;
