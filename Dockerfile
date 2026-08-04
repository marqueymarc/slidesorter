FROM python:3.13-slim

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app
RUN python -m pip install --no-cache-dir .

VOLUME ["/media", "/state"]
EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/gallery/', timeout=3)"

ENTRYPOINT ["slidesorter", "run", "/media", "--state-dir", "/state", "--host", "0.0.0.0"]
