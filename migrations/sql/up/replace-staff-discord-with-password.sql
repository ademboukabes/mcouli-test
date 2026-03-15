ALTER TABLE public.staff_users ADD COLUMN password VARCHAR(255);

UPDATE public.staff_users
SET password = '$2b$12$ryQOrgtbfma5pQjN8/J2Q.D2sb4NUytTuiCr6YvKk/mDhqIWp9ZPO'
WHERE password IS NULL;

ALTER TABLE public.staff_users
ALTER COLUMN password SET NOT NULL;

ALTER TABLE public.staff_users
DROP COLUMN discord_id;
