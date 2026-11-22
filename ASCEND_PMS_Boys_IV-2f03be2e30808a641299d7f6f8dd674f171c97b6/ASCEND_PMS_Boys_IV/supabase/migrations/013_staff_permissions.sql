SET LOCAL search_path = ascend, pg_catalog;
-- Class management and leaderboards were historically open to every staff
-- admin. Preserve those existing capabilities explicitly, once. New teaching
-- access must be granted by the Super Admin.
DO $$
DECLARE staff RECORD; permissions jsonb;
BEGIN
  FOR staff IN SELECT id, admin_permissions FROM users WHERE role='admin' AND admin_level='staff' LOOP
    BEGIN
      permissions := CASE WHEN COALESCE(staff.admin_permissions,'')='' THEN NULL ELSE staff.admin_permissions::jsonb END;
      IF permissions IS NULL OR jsonb_typeof(permissions) <> 'array' THEN
        permissions := '["students","challenges","achievements","rewards","announcements","activity"]'::jsonb;
      END IF;
    EXCEPTION WHEN others THEN
      permissions := '["students","challenges","achievements","rewards","announcements","activity"]'::jsonb;
    END;
    IF NOT permissions ? 'classes' THEN permissions := permissions || '["classes"]'::jsonb; END IF;
    IF NOT permissions ? 'leaderboards' THEN permissions := permissions || '["leaderboards"]'::jsonb; END IF;
    UPDATE users SET admin_permissions=permissions::text WHERE id=staff.id;
  END LOOP;
END $$;
