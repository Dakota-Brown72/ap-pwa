FROM ubuntu:24.04

# Install FFmpeg, Python and dependencies
RUN apt-get update && \
    apt-get install -y \
    ffmpeg \
    python3 \
    python3-pip \
    bash \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Create directories
RUN mkdir -p /segments /config /tmp/ffmpeg

# Copy our streaming files
COPY ffmpeg_api_server.py /config/ffmpeg_api_server.py
COPY start_streams.sh /config/start_streams.sh
RUN chmod +x /config/ffmpeg_api_server.py /config/start_streams.sh

# Set working directory
WORKDIR /config

# Expose HTTP API port
EXPOSE 8080

# Run the Python-based streaming service
CMD ["python3", "/config/ffmpeg_api_server.py"] 