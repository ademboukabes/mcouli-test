CREATE TYPE IF NOT EXISTS public.audit_event_type AS ENUM (
    'user.signup',
    'user.login',
    'user.logout',
    'upload_request.created',
    'upload_request.approved',
    'upload_request.rejected'
);

CREATE TABLE IF NOT EXISTS public.audit_events (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    event_type public.audit_event_type NOT NULL,
    user_id uuid,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_events_event_type ON public.audit_events USING btree (event_type);
CREATE INDEX IF NOT EXISTS idx_audit_events_user_id ON public.audit_events USING btree (user_id);

ALTER TABLE ONLY public.audit_events
    ADD CONSTRAINT audit_events_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.audit_events
    ADD CONSTRAINT audit_events_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;
