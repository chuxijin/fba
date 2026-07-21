BEGIN;

ALTER TABLE public.study_challenge_level
    DROP CONSTRAINT IF EXISTS ck_challenge_level_stage;

UPDATE public.study_challenge_level
SET
    stage = 'stage_1',
    display_config = CASE
        WHEN display_config IS NULL THEN jsonb_build_object('weather_stage', 'stage_1')
        ELSE jsonb_set(display_config::jsonb, '{weather_stage}', '"stage_1"'::jsonb, true)
    END
WHERE challenge_key = 'data_analysis'
  AND stage = 'easy';

ALTER TABLE public.study_challenge_level
    ADD CONSTRAINT ck_challenge_level_stage
    CHECK (stage IN ('stage_1', 'stage_2', 'stage_3', 'stage_4'));

COMMIT;
