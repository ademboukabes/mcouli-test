ALTER TABLE public.staff_users DROP COLUMN discord_id;
ALTER TABLE public.staff_users ADD COLUMN password VARCHAR(255) NOT NULL ;
