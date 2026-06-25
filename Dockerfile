# Base image
FROM bom.ocir.io/bm2nhaouvzhw/baseimage-cholamandalam-com:python-3.11.6

WORKDIR /usr/src/app

# Copy application code
COPY . /usr/src/app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir gunicorn

# Install Nginx
RUN apt-get update && apt-get install -y nginx  vim && rm -rf /var/lib/apt/lists/*

# Copy Nginx site config (you must provide this file in your project root)
COPY default /etc/nginx/sites-available/default

# Expose ports
EXPOSE 80

# Start Nginx and Gunicorn with WSGI workers
CMD service nginx start && \
    gunicorn --bind 0.0.0.0:5000 --timeout 300 app:app

