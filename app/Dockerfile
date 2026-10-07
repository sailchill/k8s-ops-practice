FROM python:3.12-slim

ARG APP_VERSION=1.0.0
ENV APP_VERSION=${APP_VERSION} \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN useradd -u 10001 -M appuser && chmod +x /app/start.sh
USER 10001

EXPOSE 8080
CMD ["sh", "/app/start.sh"]
