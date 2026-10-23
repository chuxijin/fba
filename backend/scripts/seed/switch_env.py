with open('backend/.env', 'r', encoding='utf-8') as f:
    text = f.read()

replacements = {
    "DATABASE_HOST='100.80.0.126'": "DATABASE_HOST='212.64.23.13'",
    "DATABASE_PORT=5432": "DATABASE_PORT=8100",
    "DATABASE_USER='postgres'": "DATABASE_USER='yas'",
    "REDIS_HOST='100.80.0.126'": "REDIS_HOST='212.64.23.13'",
    "REDIS_DATABASE=3": "REDIS_DATABASE=1",
    "CELERY_RABBITMQ_HOST='100.80.0.126'": "CELERY_RABBITMQ_HOST='212.64.23.13'",
    "CELERY_RABBITMQ_USERNAME='guest'": "CELERY_RABBITMQ_USERNAME='fba_prod'",
    "CELERY_RABBITMQ_PASSWORD='guest'": "CELERY_RABBITMQ_PASSWORD='20100703Jlj.'\nCELERY_RABBITMQ_VHOST='fba_prod'",
    "CELERY_BROKER_REDIS_DATABASE=3": "CELERY_BROKER_REDIS_DATABASE=2",
    "CELERY_BACKEND_REDIS_DATABASE=4": "CELERY_BACKEND_REDIS_DATABASE=3",
}

for k, v in replacements.items():
    if k in text:
        text = text.replace(k, v)
        print(f"Replaced: {k} -> {v}")
    else:
        print(f"Warning: Not found {k}")

with open('backend/.env', 'w', encoding='utf-8') as f:
    f.write(text)
print("Updated backend/.env successfully!")
