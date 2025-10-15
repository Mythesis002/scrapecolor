# Use Selenium standalone Chrome image (Chrome already installed!)
FROM selenium/standalone-chrome:120.0-chromedriver-120.0

# Switch to root to install Python packages
USER root

# Install Python 3 and pip
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# Copy application
COPY scraper_clean.py .

# Set environment variables
ENV HEADLESS=true
ENV SCRAPE_INTERVAL=270
ENV PYTHONUNBUFFERED=1

# Run as root (required for Chrome in container)
USER root

# Start the scraper
CMD ["python3", "-u", "scraper_clean.py"]
