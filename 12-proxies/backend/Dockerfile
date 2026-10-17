FROM python:3.15.0-alpine3.24

WORKDIR /app
COPY app.py .

# Run as an unprivileged user: the service only needs to bind port 5000.
RUN adduser -D -H -u 10001 app
USER 10001

EXPOSE 5000

HEALTHCHECK --interval=5s --timeout=3s --retries=10 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health')"]

CMD ["python", "-u", "app.py"]
