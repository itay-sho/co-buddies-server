web: daphne co_buddies.asgi:application --port $PORT --bind 0.0.0.0
release: python manage.py migrate
worker: python manage.py runworker matchmaking-task db-operations-task pn-task