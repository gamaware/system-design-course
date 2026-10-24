# The official AWS Lambda base image: the Python runtime plus the Runtime Interface Emulator (RIE),
# which serves the Lambda invoke API on port 8080 so the function runs outside AWS.
FROM public.ecr.aws/lambda/python:3.12.2026.10.22.03

# The function code is a single file: this layer is the whole deployment unit of the function.
COPY app.py ${LAMBDA_TASK_ROOT}/

# Module "app", function "handler": the same handler setting you give Lambda in AWS.
CMD ["app.handler"]
