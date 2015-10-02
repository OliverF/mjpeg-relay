mjpeg-relay
===========

mjpeg-relay is a simple Python script which accepts input from an existing MJPEG stream, and relays it to any number of clients. This is inteded for a scenario where the original MJPEG stream is hosted on a low-bandwidth internet connection (such as a home connection) or from a low-resource device (such as a Raspberry Pi or IP camera), and you have a server from which you wish to relay the stream to multiple clients without placing extra demand on the original stream.

The script is designed to be simple to use with minimal configuration. All video parameters are defined by the source stream, ensuring mjpeg-relay is as transparent as possible. Rather than creating its own MJPEG stream, mjpeg-relay simply re-streams the original MJPEG stream directly. This is a faster and more transparent approach.

# Features
- Low resource
- Low latency
- Status page
- Option to stream to clients via WebSockets

# Usage
`relay.py [-p <relay port>] [-w <WebSocket port>] [-q] stream-source-url`

- **-p \<relay port\>**: Port that the stream will be relayed on (default is 54321)
- **-w \<WebSocket port\>**: Port that the stream will be relayed on via WebSockets (default is 54322)
- **-q**: Silence non-essential output
- **stream-source-url**: URL of the existing MJPEG stream. If the stream is protected with HTTP authentication, supply the credentials via the URL like so: `http://user:password@ip:port/path/to/stream/`

Once it is running, you can access the following URLs:

* `/status`: the status summary of mjpeg-relay
* `/stream`: the MJPEG stream. This can be embedded directly into an `<img>` tag on modern browsers like so: `<img src="http://localhost:54321/stream">`
* `/snapshot`: the latest JPEG frame from the MJPEG stream

# Example

**Relaying MJPEG stream at 192.0.2.1:1234/?action=stream on port 54017**

1. Start the relay: `python relay.py -p 54017 "http://192.0.2.1:1234/?action=stream"`
2. Confirm that mjpeg-relay has connected to the remote stream
3. Connect to the relayed stream at `http://localhost:54017/stream`. This can be embedded directly into an `<img>` tag on modern browsers like so: `<img src="http://localhost:54017/stream">`
4. The status of mjpeg-relay is displayed at `http://localhost:54017/status`

# WebSocket Example

**As above, but also relaying the MJPEG stream via WebSockets on port 54018**

1. Start the relay: `python relay.py -p 54017 -w 54018 "http://192.0.2.1:1234/?action=stream"`
2. Confirm that mjpeg-relay has connected to the remote stream
3. Copy and paste the example HTML and JavaScript in the file `websocketexample.html` into your website, and adapt as necessary
4. The status of mjpeg-relay is displayed at `http://localhost:54017/status`

# Docker

Here is the same example done with docker:

``` shell
docker build -t replay .
docker run -d -p 54017:54321 replay "http://192.0.2.1:1234/?action=stream"
```
