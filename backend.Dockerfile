# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY backend_requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r backend_requirements.txt

# Copy the current directory contents into the container at /app
COPY server.py .
# Note: We don't copy the DB file here, it will be mounted via volume

# Make port 8443 available (internal port Gunicorn binds to)
EXPOSE 8443

# Define environment variable (optional, good practice)
ENV FLASK_APP=server:app
# Ensure Python output isn't buffered (helps see logs immediately)
ENV PYTHONUNBUFFERED=1

# Ensure the directory for the volume mount exists
RUN mkdir -p /app/data

# Run server.py when the container launches using Gunicorn
# ADDED --preload flag
CMD ["gunicorn", "--bind", "0.0.0.0:8443", "--workers", "1", "--preload", "server:app"]