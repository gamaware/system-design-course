FROM python:3.13.16-slim-trixie

# Print each line as soon as it is written, so compose shows the exercises live
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir redis==8.1.0 requests==2.34.2 \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

COPY cache_lab.py .

USER 10001:10001

ENTRYPOINT ["python", "cache_lab.py"]
