# Deprecated package

`backend/plugin/agents` is no longer an installed FBA plugin. Its package marker was removed so the plugin loader does not discover its API routes or ORM models.

The active grading platform is `backend/plugin/agent` and Shenlun grading only accepts `question_bank_v2` attempts.

The remaining files are retained temporarily for the independent AI question-generation Celery task and historical task-table compatibility. They must not be used by new grading or coaching code.
