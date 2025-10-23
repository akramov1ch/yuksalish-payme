#!/bin/sh

# Xatolik yuz berganda skriptni to'xtatish
set -e

echo "Running database migrations..."
# DATABASE_URL .env faylidan olinadi
# YECHIM: To'g'ri yo'lni ko'rsatish
migrate -path /app/migrations -database "$DATABASE_URL" -verbose up

echo "Migrations complete. Starting the application..."
# Asosiy dasturni ishga tushirish
/app/payme