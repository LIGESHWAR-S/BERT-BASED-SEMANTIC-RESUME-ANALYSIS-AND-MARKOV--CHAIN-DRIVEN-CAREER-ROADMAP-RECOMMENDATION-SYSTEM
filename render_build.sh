#!/usr/bin/env bash
# exit on error
set -o errexit

echo "==> Installing dependencies..."
pip install -r requirements.txt

echo "==> Collecting static files..."
python manage.py collectstatic --noinput

echo "==> Running migrations..."
python manage.py migrate

echo "==> Seeding database..."
python seed_data.py

echo "==> Creating default superuser..."
python create_admin.py

echo "==> Build process completed successfully!"
