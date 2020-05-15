FROM python:3.6-alpine

COPY app /app

WORKDIR /app

RUN pip install boto3
RUN pip install requests

CMD [ "python", "-u", "main.py" ]
