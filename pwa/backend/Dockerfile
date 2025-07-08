FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Set timezone to Central Time
ENV TZ=America/Chicago
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data

RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app \
    && chown -R app:app /data

USER app

EXPOSE 5001

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5001/api/system/status')" || exit 1

CMD ["python", "app.py"]
