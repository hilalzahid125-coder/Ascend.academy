# ASCEND v1.4 QA

Verified before release:

- 16/16 automated regression tests passing
- SQLite `PRAGMA integrity_check` = `ok`
- SQLite foreign-key check = no violations
- CSRF token present on state-changing forms
- Student dashboard rendered at desktop and mobile widths
- Mobile drawer closes by outside tap and swipe-left
- Edge swipe-right opens the mobile drawer
- Student identity/profile images render circularly
- Student rank uses active students only
- Super Admin student deletion is denied to Staff Admins and cascades linked student data

This is a presentation/pilot quality pass and does not replace the existing database or automatically delete live student records.
