FROM python:3.13.16-slim-trixie

WORKDIR /app

RUN pip install --no-cache-dir pymysql==1.1.1 cryptography==44.0.3

COPY . .

EXPOSE 8080

CMD ["python", "server.py"]
