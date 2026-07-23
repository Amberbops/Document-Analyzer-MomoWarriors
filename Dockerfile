FROM python:3.11-slim

# Install nginx
RUN apt-get update && \
    apt-get install -y nginx && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend
COPY app ./app

# Copy frontend
COPY frontend /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/sites-available/default

EXPOSE 80
EXPOSE 8000

CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port 8000 & nginx -g 'daemon off;'"
