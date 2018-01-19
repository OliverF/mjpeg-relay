FROM alpine:3.7

RUN apk add --no-cache python2 py2-pip

COPY . /relay/
RUN pip install -r /relay/requirements.txt

WORKDIR /relay

EXPOSE 54321
ENTRYPOINT ["python", "relay.py"]
