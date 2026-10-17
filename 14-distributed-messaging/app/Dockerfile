FROM python:3.13.16-slim-trixie

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./

# Run as an unprivileged user; /data holds the payment ledger used in Task 5.
RUN useradd --create-home --uid 10001 lab \
    && mkdir /data \
    && chown lab /data
USER 10001

CMD ["python", "worker.py"]
