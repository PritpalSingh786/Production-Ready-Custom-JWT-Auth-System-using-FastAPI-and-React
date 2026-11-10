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

# Rebuild images first then start services (use after code changes)
# docker compose up -d --build

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