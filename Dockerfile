# Use official Python image
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    libsqlite3-0 \
    libsqlite3-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Clone and build Swiss Ephemeris from GitHub mirror
RUN git clone https://github.com/aloistr/swisseph.git && \
    cd swisseph && \
    make libswe.a && make libswe.so && \
    cp libswe.so /usr/lib/ && \
    cd .. && rm -rf swisseph

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose app port
EXPOSE 8000

# Start FastAPI app
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
