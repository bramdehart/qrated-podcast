FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

ENV DATA_DIR=/data FEEDS_FILE=/config/feeds.yaml PYTHONUNBUFFERED=1
VOLUME /data
ENTRYPOINT ["qrated"]
CMD ["serve"]
