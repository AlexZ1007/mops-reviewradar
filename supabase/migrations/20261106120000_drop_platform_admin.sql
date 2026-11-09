-- Remove the platform admin super-role. Access is decided only by project_members.role.
ALTER TABLE public.profiles DROP COLUMN IF EXISTS is_admin;
