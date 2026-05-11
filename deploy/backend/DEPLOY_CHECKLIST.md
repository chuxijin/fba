# FBA Deployment Checklist

## Current Environment Split

- Local dev:
  `backend/.env`
- Test server:
  project path `/www/wwwroot/fba-test`
  API domain `https://api-test.yzxj.vip`
  FastAPI port `8001`
- Production server:
  API domain `https://api.yzxj.vip`

## Before Releasing

- Confirm test mini program points to `https://api-test.yzxj.vip`
- Confirm production mini program points to `https://api.yzxj.vip`
- Confirm test backend `DATABASE_SCHEMA='fba_test'`
- Confirm production backend `DATABASE_SCHEMA='fba'`
- Confirm test Redis DB is different from production
- Confirm test RabbitMQ uses:
  `CELERY_RABBITMQ_USERNAME='fba_test'`
  `CELERY_RABBITMQ_VHOST='fba_test'`
- Confirm production RabbitMQ uses:
  `CELERY_RABBITMQ_USERNAME='fba_prod'`
  `CELERY_RABBITMQ_VHOST='fba_prod'`
- Confirm `CREATE EXTENSION vector` has already been executed in both databases
- Confirm Supervisor processes are all `RUNNING`
- Confirm Nginx / BT reverse proxy:
  `api-test.yzxj.vip -> 127.0.0.1:8001`
  `api.yzxj.vip -> 127.0.0.1:8080`

## Storage Isolation

- Best practice:
  test and production use different buckets
- Acceptable current practice:
  use the same bucket, but different prefixes

Recommended values:

- Test:
  `STORAGE_KEY_PREFIX='test/'`
- Production:
  `STORAGE_KEY_PREFIX=''`
  or `STORAGE_KEY_PREFIX='prod/'`

If test and production share one bucket, they must not share the same prefix.

## Smoke Test

- Login works
- Home category tree works
- Bank list works
- Practice list works
- Submit practice works
- Avatar upload works
- Any async feature that depends on Celery works

## Useful Commands

Test backend:

```bash
cd /www/wwwroot/fba-test
uv run fba run --host 127.0.0.1 --port 8001 --no-reload --workers 1
```

Test Celery worker:

```bash
cd /www/wwwroot/fba-test
/www/wwwroot/fba-test/.venv/bin/celery -A backend.app.task.celery worker -P gevent -c 100 --loglevel=INFO
```

Test Celery beat:

```bash
cd /www/wwwroot/fba-test
/www/wwwroot/fba-test/.venv/bin/celery -A backend.app.task.celery beat --loglevel=INFO
```

Check RabbitMQ test queues:

```bash
rabbitmqctl list_queues -p fba_test name messages consumers
```

Check Supervisor:

```bash
supervisorctl status fba_test:
supervisorctl status fba:
```
