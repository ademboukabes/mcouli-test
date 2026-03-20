ALTER TABLE public.audit_events DROP CONSTRAINT IF EXISTS audit_events_user_id_fkey;
DROP INDEX IF EXISTS idx_audit_events_event_type;
DROP INDEX IF EXISTS idx_audit_events_user_id;
DROP TABLE IF EXISTS public.audit_events;
DROP TYPE IF EXISTS public.audit_event_type;
