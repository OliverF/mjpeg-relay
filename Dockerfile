from python:2.7

expose 54321

run pip install requests

copy . /srv/app
workdir /srv/app

entrypoint ["python", "relay.py"]
