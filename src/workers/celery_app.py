import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

# Get Redis URL from environment
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app = Celery(
    "stateaffair",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["src.workers.tasks"]
)

from celery.schedules import crontab

# Configuration
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600, # 1 hour max
)

# Scheduled tasks
app.conf.beat_schedule = {
    'auto-discover-every-hour': {
        'task': 'src.workers.tasks.auto_discover_new_videos_task',
        'schedule': crontab(minute=0),  # Every hour at :00
    },
}

if __name__ == "__main__":
    app.start()

