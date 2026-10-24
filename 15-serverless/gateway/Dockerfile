FROM python:3.13.16-slim-trixie

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 lab
USER 10001

EXPOSE 8080

HEALTHCHECK --interval=5s --timeout=5s --retries=12 \
    CMD ["python", "-c", "import gateway; gateway.healthcheck()"]

CMD ["python", "gateway.py"]
