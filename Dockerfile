# Use a stable Python image
FROM python:3.11-slim

# Install dependencies and tools
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    libsqlite3-0 \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Download and build Swiss Ephemeris from source
RUN wget https://www.astro.com/ftp/swisseph/swe_unix_src_2.10.03.tar.gz && \
    tar -xzf swe_unix_src_2.10.03.tar.gz && \
    cd swisseph && \
    make libswe.a && make libswe.so && \
    cp libswe.so /usr/lib/ && \
    cd .. && rm -rf swisseph swe_unix_src_2.10.03.tar.gz

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
