DO $$ DECLARE v_system_id BIGINT; BEGIN
    SELECT id INTO v_system_id FROM fba.qbank_v2_knowledge_system WHERE code = 'kaoyan_politics' AND version = 'kaoyan' AND deleted = 0 LIMIT 1;
    FOR i IN 1..4 LOOP
        UPDATE fba.qbank_v2_knowledge_point kp
        SET path = COALESCE(
                (SELECT p.path || '.' || CAST(kp.id AS VARCHAR)
                   FROM fba.qbank_v2_knowledge_point p
                  WHERE p.id = kp.parent_id AND p.system_id = kp.system_id),
                CAST(kp.id AS VARCHAR)
            ),
            updated_time = NOW()
        WHERE kp.system_id = v_system_id
          AND kp.deleted = 0
          AND (
              kp.path IS NULL OR
              kp.path IS DISTINCT FROM COALESCE(
                  (SELECT p.path || '.' || CAST(kp.id AS VARCHAR)
                     FROM fba.qbank_v2_knowledge_point p
                    WHERE p.id = kp.parent_id AND p.system_id = kp.system_id),
                  CAST(kp.id AS VARCHAR)
              )
          );
    END LOOP;

    PERFORM setval(
        pg_get_serial_sequence('fba.qbank_v2_knowledge_point', 'id'),
        GREATEST(
            COALESCE((SELECT MAX(id) FROM fba.qbank_v2_knowledge_point), 1),
            COALESCE((SELECT last_value FROM fba.qbank_v2_knowledge_point_id_seq), 1)
        ),
        (SELECT COUNT(*) > 0 FROM fba.qbank_v2_knowledge_point)
    );
END $$;