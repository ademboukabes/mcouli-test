ALTER TABLE public.staff_users
DROP COLUMN password;
ALTER TABLE public.staff_users
ADD COLUMN discord_id VARCHAR(255) NOT NULL;