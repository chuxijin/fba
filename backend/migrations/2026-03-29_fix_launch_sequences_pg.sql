BEGIN;

SELECT setval(
    pg_get_serial_sequence('sys_user', 'id'),
    GREATEST((SELECT COALESCE(MAX(id), 1) FROM sys_user), 1),
    true
);

SELECT setval(
    pg_get_serial_sequence('study_user_account', 'id'),
    GREATEST((SELECT COALESCE(MAX(id), 1) FROM study_user_account), 1),
    true
);

SELECT setval(
    pg_get_serial_sequence('actcode_batch', 'id'),
    GREATEST((SELECT COALESCE(MAX(id), 1) FROM actcode_batch), 1),
    true
);

SELECT setval(
    pg_get_serial_sequence('actcode', 'id'),
    GREATEST((SELECT COALESCE(MAX(id), 1) FROM actcode), 1),
    true
);

SELECT setval(
    pg_get_serial_sequence('actcode_usage', 'id'),
    GREATEST((SELECT COALESCE(MAX(id), 1) FROM actcode_usage), 1),
    true
);

SELECT setval(
    pg_get_serial_sequence('membership_user', 'id'),
    GREATEST((SELECT COALESCE(MAX(id), 1) FROM membership_user), 1),
    true
);

SELECT setval(
    pg_get_serial_sequence('membership_record', 'id'),
    GREATEST((SELECT COALESCE(MAX(id), 1) FROM membership_record), 1),
    true
);

COMMIT;
