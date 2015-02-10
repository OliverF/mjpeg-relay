mjpeg-relay
===========

mjpeg-relay is a simple Python script which accepts input from an existing MJPEG stream, and relays it to any number of clients. This is inteded for a scenario where the original MJPEG stream is hosted on a low-bandwidth internet connection (such as a home connection) or from a low-resource device (such as a Raspberry Pi or IP camera), and you have a server from which you wish to relay the stream to multiple clients without placing extra demand on the original stream.

The script is designed to be simple to use with minimal configuration. All video parameters are defined by the source stream, ensuring mjpeg-relay is as transparent as possible. Rather than creating its own MJPEG stream, mjpeg-relay simply re-streams the original MJPEG stream directly. This is a faster and more transparent approach.

# Features
- Low resource
- Low latency
- Status page

# Usage
`relay.py [-p <relay port>] [-q] stream-source-url`

- **-p \<relay port\>**: Port that the stream will be relayed on (default is 54321)
- **-q**: Silence non-essential output
- **stream-source-url**: URL of the existing MJPEG stream. If the stream is protected with HTTP authentication, supply the credentials via the URL like so: `http://user:password@ip:port/path/to/stream/`

Once it is running, you can access the following URLs:

* `/status`: the mjpeg-replay status of connected clients.
* `/stream`: the mjpeg stream. This can be embedded directly into an `<img>` tag on modern browsers like so: `<img src="http://localhost:54321/stream">`
* `/snapshot`: the stream latest JPEG snapshot

# Example

**Relaying MJPEG stream at 192.0.2.1:1234/?action=stream on port 54017**

1. Start the relay: `python relay.py -p 54017 "http://192.0.2.1:1234/?action=stream"`
2. Confirm that mjpeg-relay has connected to the remote stream
3. Connect to the relayed stream at `http://localhost:54017/stream`. This can be embedded directly into an `<img>` tag on modern browsers like so: `<img src="http://localhost:54017/stream">`
4. The status of mjpeg-relay is displayed at `http://localhost:54017/status`
