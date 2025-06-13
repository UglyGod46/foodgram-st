#!/bin/bash

echo "Waiting for postgres..."
while ! nc -z db 5432; do
  sleep 1
done
echo "PostgreSQL started"

python manage.py migrate

python manage.py collectstatic --no-input

echo "Loading ingredients..."
python manage.py load_data || echo "Failed to load ingredients"

echo "Creating superuser if not exists..."
python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.filter(username='admin').exists() or User.objects.create_superuser('admin', 'admin@example.com', 'admin')"

exec gunicorn foodgram.wsgi:application --bind 0.0.0.0:8000