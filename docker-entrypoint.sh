#!/bin/bash

# Start Gunicorn with the environment variables (or default values)
echo "Starting Gunicorn..."
exec gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8000 &
#uvicorn $UVICORN_APP --host $UVICORN_HOST --port $UVICORN_PORT --timeout-keep-alive $UVICORN_TIMEOUT &

# Start Nginx
echo "Starting Nginx..."
/etc/init.d/nginx start

# Keep the container running
tail -f /dev/null
