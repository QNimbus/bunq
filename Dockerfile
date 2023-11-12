# Use an official Python runtime as a parent image
FROM python:slim

# Set the working directory in the container to /app
WORKDIR /app

# Copy requirements.txt into the container at /app
COPY requirements.txt /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . /app

# Upgrade pip
RUN pip install --upgrade pip

# Make scripts executable
RUN chmod +x /app/scripts/start_chisel.sh

VOLUME /app/conf /app/data

# Environment variables
ENV PYTHONWARNINGS=ignore
ENV LOGL_LEVEL=INFO
ENV PRODUCTION=True
ENV GUNICORN_WORKERS=1
ENV GUNICORN_TIMEOUT=5
ENV GUNICORN_PORT=5000
ENV ALLOWED_IPS=

# Run bunq callback server
CMD [ "/bin/sh", "-c", "gunicorn --workers=${GUNICORN_WORKERS} --timeout=${GUNICORN_TIMEOUT} --bind=0.0.0.0:${GUNICORN_PORT} \"server:create_server()\"" ]
