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

# Make port 8443 available to the world outside this container (internal port)
# Gunicorn will bind to this port
EXPOSE 8443

# Define environment variable (optional, good practice)
ENV FLASK_APP=server:app

# Ensure the directory for the volume mount exists
RUN mkdir -p /app/data

# Run server.py when the container launches using Gunicorn
# Bind to 0.0.0.0 to accept connections from outside the container (within Docker network)
CMD ["gunicorn", "--bind", "0.0.0.0:8443", "server:app"]