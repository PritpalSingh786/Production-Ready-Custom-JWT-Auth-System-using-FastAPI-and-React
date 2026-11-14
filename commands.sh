# alembic revision --autogenerate -m "Initial migration"

# alembic upgrade head

# uvicorn app.main:app --reload

# nano alembic.ini
'''
Please ensure that sqlalchemy.url is left blank 
in alembic.ini, because we have configured env.py 
to set the database URL dynamically from the 
environment variables.
'''

# docker compose exec web alembic revision --autogenerate -m "Initial migration"

# docker compose exec web alembic upgrade head

# docker compose logs -f web    
# Show live logs (prints, API requests, errors) of the web container in real-time.

# docker stop quote_video_web-web-1
# docker ps
# docker rm -f pgadmin
'''

**`@shared_task`**
*   **Good:** It’s like a "guest pass." Any Celery app in your 
project can use it.
*   **Bad:** Because it doesn’t belong to a specific app, it 
gets confused when trying to find your Redis server, which causes 
the "Connection refused" error.

**`@celery_worker.task`**
*   **Good:** It’s like a "VIP pass." It knows exactly which 
app it belongs to and connects straight to your Redis server 
without any confusion. 
*   **Bad:** It is locked to that one specific app. You can't easily 
use it in a different Celery app later.

**My advice:** For your project right now, use `@celery_worker.task`. 
It is simple, direct, and just works!

'''


# Go to project directory - where your docker-compose.yml is located
cd ~/Desktop/microservices-graphql

# Start all services in background (detached mode)
docker compose up -d

# Rebuild images first then start services (use after code changes)
docker compose up -d --build

# Stop all services (containers removed, data volume remains)
docker compose down

# Stop all services AND delete volumes (database data will be deleted - careful!)
docker compose down -v

# Show status of running services
docker compose ps

# Restart all services
docker compose restart

# Stop only auth service
docker compose stop auth_service

# Start stopped auth service again
docker compose start auth_service

# Show last 50 lines of logs from all services
docker compose logs --tail=50

# Show live logs from all services (real-time follow, press Ctrl+C to stop)
docker compose logs -f

# Show last 50 lines of logs from auth service only
docker compose logs auth_service --tail=50

# Show last 50 lines of logs from blog service only
docker compose logs blog_service --tail=50

# Show last 50 lines of logs from API gateway only
docker compose logs api_gateway --tail=50

# Create migration files for users app in auth service (detects database schema changes)
docker compose exec auth_service python manage.py makemigrations users

# Apply all pending migrations in auth service (creates/updates database tables)
docker compose exec auth_service python manage.py migrate

# Create migration files for celery beat (for scheduled tasks)
docker compose exec auth_service python manage.py makemigrations django_celery_beat

# Apply celery beat migrations
docker compose exec auth_service python manage.py migrate

# Create migration files for blogs app in blog service
docker compose exec blog_service python manage.py makemigrations blogs

# Apply all pending migrations in blog service
docker compose exec blog_service python manage.py migrate

# Show which migrations have been applied in auth service
docker compose exec auth_service python manage.py showmigrations

# Login to PostgreSQL database (interactive shell)
docker compose exec postgres_auth psql -U postgres -d auth_db

# Show list of all tables in PostgreSQL
docker compose exec postgres_auth psql -U postgres -d auth_db -c "\dt"

# Show all data from users table
docker compose exec postgres_auth psql -U postgres -d auth_db -c "SELECT * FROM users_user;"

# Login to MongoDB (interactive shell)
docker compose exec mongo_blog mongosh

# Show all uploads from blog database
docker compose exec mongo_blog mongosh --eval "use blog_db; db.uploads.find().pretty()"

# Check auth service GraphQL endpoint (shows HTTP status code)
curl -s -o /dev/null -w "HTTP: %{http_code}\n" http://localhost:8000/graphql/auth/

# Register a new user via API
curl -X POST http://localhost:8000/graphql/auth/ -H "Content-Type: application/json" -d '{"query": "mutation { register(username: \"test\", email: \"test@test.com\", password: \"Test@123\") { success message } }"}'

# Login user and get accessToken
curl -X POST http://localhost:8000/graphql/auth/ -H "Content-Type: application/json" -d '{"query": "mutation { login(username: \"test\", password: \"Test@123\", platform: \"web\") { success accessToken } }"}'

# Search for "error" keyword in logs of all services
docker compose logs 2>&1 | grep -i error

# Search for "traceback" in auth service logs (for Python errors)
docker compose logs auth_service 2>&1 | grep -i traceback

# Show which application is using port 5432 (PostgreSQL)
sudo lsof -i :5432

# Show which application is using port 8000 (API Gateway)
sudo lsof -i :8000

# Delete unused Docker resources (images, containers, networks) - frees disk space
docker system prune -a

# Full reset - stop everything, delete volumes, rebuild and start
docker compose down -v && docker compose up -d --build

# Create Django superuser (for admin panel access)
docker compose exec auth_service python manage.py createsuperuser

# Open Django interactive shell (to run Python code)
docker compose exec auth_service python manage.py shell

# Open blog service Django interactive shell
docker compose exec blog_service python manage.py shell

# Take PostgreSQL database backup (saves to backup.sql file)
docker compose exec postgres_auth pg_dump -U postgres auth_db > backup.sql

# Show total count of uploads in blog database
docker compose exec mongo_blog mongosh --eval "use blog_db; db.uploads.countDocuments()"

# Ping Redis server - should return "PONG" if running
docker compose exec redis redis-cli ping

# Check if PostgreSQL server is ready
docker compose exec postgres_auth pg_isready -U postgres

# Ping MongoDB server - should return "ok: 1" if running
docker compose exec mongo_blog mongosh --eval "db.adminCommand('ping')"

# Show Docker compose services status in table format (name, status, ports)
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

# Search all containers for auth or blog related ones
docker ps -a | grep -E "auth|blog"

# Show last 30 lines of auth service container logs (auto-detects container ID)
docker logs $(docker ps -aq --filter "name=auth_service") --tail=30 2>/dev/null

# Show list of defined services in docker-compose.yml
docker compose config --services

# Start only databases (without app services)
docker compose up -d postgres_auth redis mongo_blog

# Run auth service once for migration (not in background)
docker compose run --rm auth_service python manage.py migrate

# Restart all services, wait 10 seconds, then show status
docker compose restart && sleep 10 && docker compose ps

# Monitor service status every 2 seconds (live)
watch -n 2 'docker compose ps'

# Show last 20 lines of live logs
docker compose logs -f --tail=20



Resolve Migrations Problem:- 
..........................


# 1. Stop everything
docker compose down

# 2. Delete all migrations
rm -f auth_service/users/migrations/0*.py
rm -rf auth_service/users/migrations/__pycache__

# 3. Drop and recreate database
docker compose up -d postgres_auth
sleep 5
docker compose exec postgres_auth psql -U postgres -c "DROP DATABASE IF EXISTS auth_db;"
docker compose exec postgres_auth psql -U postgres -c "CREATE DATABASE auth_db;"

# 4. Build and start auth service with migration command
docker compose build auth_service
docker compose run --rm auth_service python manage.py makemigrations users
docker compose run --rm auth_service python manage.py migrate users

# 5. Apply all migrations
docker compose run --rm auth_service python manage.py migrate

# 6. Now start normally
docker compose up -d auth_service
sleep 5
docker compose ps | grep auth

# for viewing structure 
tree -L 5

# for checking ip
docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' auth_service



#!/bin/bash

echo "========================================="
echo "🧪 Running All Tests"
echo "========================================="

echo ""
echo "📦 Auth Service Tests..."
docker compose exec auth_service python manage.py test users.tests --verbosity=2

echo ""
echo "📦 Blog Service Tests..."
docker compose exec blog_service python manage.py test blogs.tests --verbosity=2

echo ""
echo "📦 API Gateway Tests..."
docker compose exec api_gateway python manage.py test --verbosity=2

echo ""
echo "📦 Integration Tests..."
python tests/test_integration.py

echo ""
echo "========================================="
echo "✅ All tests completed!"
echo "========================================="



# Start Redis on port 6381
redis-server --port 6381 --daemonize yes

# Verify
redis-cli -p 6381 ping
# ✅ Should return: PONG


# Find what's using port 8000
sudo lsof -i :8000


# Kill process on port 8000
sudo kill -9 $(sudo lsof -t -i:8000)

