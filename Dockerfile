FROM python:alpine

ENV PYTHONUNBUFFERED=1
ENV SOURCE_URL="http://localhost:8081/?action=stream"

COPY . /
RUN		pip3 install -r /requirements.txt

EXPOSE 54321
EXPOSE 54322
CMD ["python", "/relay.py"]
