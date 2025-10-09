# Use official Python image
FROM python:3.11-slim

# Install system dependencies required for swisseph
RUN apt-get update && apt-get install -y \
    build-essential \
    libsqlite3-0 \
    libsqlite3-dev \
    libswisseph-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port (Railway uses dynamic port via $PORT)
EXPOSE 8000

# Start FastAPI app
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
