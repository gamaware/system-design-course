# The official AWS Lambda base image: the Python runtime plus the Runtime Interface Emulator (RIE),
# which serves the Lambda invoke API on port 8080 so the function runs outside AWS.
FROM public.ecr.aws/lambda/python:3.12.2026.10.22.03
# The function code is a single file: this layer is the whole deployment unit of the function.
COPY app.py ${LAMBDA_TASK_ROOT}/
# Run as an unprivileged user, like Lambda itself: the emulator and the handler need no root.
USER 10001
# Healthy once the emulator accepts TCP connections on 8080. The check only opens a socket with bash (almost
# no CPU): it never invokes the handler, so it never causes a cold start or shows up in the function logs.
HEALTHCHECK --interval=2s --timeout=2s --retries=15 \
    CMD ["bash", "-c", "exec 3<>/dev/tcp/127.0.0.1/8080"]
# Module "app", function "handler": the same handler setting you give Lambda in AWS.
CMD ["app.handler"]
