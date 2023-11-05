# Use an official Python runtime as a parent image
FROM python:slim

# Set the working directory in the container to /app
WORKDIR /app

# Copy requirements.txt into the container at /app
COPY requirements.txt /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install curl
# Remember to update and clean up the apt cache to keep the image small
RUN apt-get update && \
    apt-get install -y curl && \
    rm -rf /var/lib/apt/lists/*

# Install chisel
RUN curl https://i.jpillora.com/chisel! | bash

# Copy the current directory contents into the container at /app
COPY . /app

# Make scripts executable
RUN chmod +x /app/scripts/entrypoint.sh
RUN chmod +x /app/scripts/chisel.sh

# Upgrade pip
RUN pip install --upgrade pip

# Set the entrypoint script
ENTRYPOINT ["/app/scripts/entrypoint.sh"]

# Environment variables (replace with correct values)
ENV CHISEL_SERVER_URL="chisel-server:8080"
ENV CHISEL_SERVER_AUTH="username:password"
ENV CHISEL_SERVER_FINGERPRINT="sg2VOIq1TLXdXB1P05bAHFy7pv5njsgWX3fF0eOu22I="

# Make port 80 available to the world outside this container
EXPOSE 80

# Run app.py when the container launches
CMD ["python", "./app.py"]
