FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FIRMWARE_EXECUTION_MODE=demo \
    WOKWI_CLI_PATH=wokwi-cli \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

WORKDIR /app

# Install required system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Install official Wokwi CLI for Linux
RUN curl -L https://wokwi.com/ci/install.sh | sh

# Verify Wokwi CLI installation
RUN wokwi-cli --version

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose port 8000
EXPOSE 8000

# Health check
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Launch FastAPI server
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
