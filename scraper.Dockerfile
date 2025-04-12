# File: scraper.Dockerfile (Updated to use Chromium)

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Chromium and WebDriverManager
# Combine updates and installs, clean up layers
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Basic utils needed
    wget \
    gnupg \
    ca-certificates \
    unzip \
    # Install Chromium and the corresponding driver from standard Debian repos
    chromium \
    chromium-driver \
    # Add common dependencies often needed by browsers/selenium
    libglib2.0-0 \
    libnss3 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libexpat1 \
    libgbm1 \
    libgcc1 \
    libstdc++6 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libxrender1 \
    libxtst6 \
    lsb-release \
    xdg-utils \
    fonts-liberation \
    # Clean up APT cache
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY scraper_requirements.txt .
RUN pip install --no-cache-dir -r scraper_requirements.txt

COPY score_masters_pool_db_v1.py .

# Ensure the directory for the volume mount exists
RUN mkdir -p /app/data

# Run the scraper script in its loop when the container starts
CMD ["python", "score_masters_pool_db_v1.py"]