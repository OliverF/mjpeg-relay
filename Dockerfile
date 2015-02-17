from python:2.7-onbuild

expose 54321

entrypoint ["python", "relay.py"]
