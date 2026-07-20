FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --create-home --uid 10001 exporter
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY collector/ ./collector/
COPY collectors/ ./collectors/
COPY config.py me5_exporter.py metrics.py entrypoint.sh ./
RUN chmod +x /app/entrypoint.sh && chown -R exporter:exporter /app

USER exporter
EXPOSE 9824
ENTRYPOINT ["/app/entrypoint.sh"]
