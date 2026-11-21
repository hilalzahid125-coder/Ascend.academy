-- Step 20: Teacher feedback becomes its own staff-admin permission.
-- Previously the /admin/feedback screens were gated by the "students" grant.
-- Grant the new explicit permission once to every staff admin who could
-- already open those screens, so no one silently loses access. Later changes
-- made by the Super Admin in Admin team are respected (this migration runs once).
UPDATE ascend.users
SET admin_permissions = (admin_permissions::jsonb || '"feedback"'::jsonb)::text
WHERE role = 'admin'
  AND admin_level = 'staff'
  AND admin_permissions IS NOT NULL
  AND admin_permissions::jsonb ? 'students'
  AND NOT (admin_permissions::jsonb ? 'feedback');
