mjpeg-relay
===========

mjpeg-relay is a simple Python script which accepts input from an existing MJPEG stream, and relays it to any number of clients. This is inteded for a scenario where the original MJPEG stream is hosted on a low-bandwidth internet connection (such as a home connection) or from a low-resource device (such as a Raspberry Pi or IP camera), and you have a server from which you wish to relay the stream to multiple clients without placing extra demand on the original stream.

The script is designed to be simple to use with minimal configuration. All video parameters are defined by the source stream, ensuring mjpeg-relay is as transparent as possible. Rather than creating its own MJPEG stream, mjpeg-relay simply re-streams the original MJPEG stream directly. This is a faster and more transparent approach.

# Features
- Low resource
- Low latency
- Status page

# Usage
`relay.py [-p <relay port>] stream-source-address stream-source-url`

- **-p \<relay port\>**: Port that the stream will be relayed on (default is 54321)
- **stream-source-address**: IP address and port of the remote stream source
- **stream-source-url**: URL for the stream source

# Example

**Relaying MJPEG stream at 192.0.2.1:1234/?action=stream on port 54017**

1. Start the relay: `python relay.py -p 54017 192.0.2.1:1234 /?action=stream`
2. Confirm that mjpeg-relay has connected to the remote stream
3. Connect to the relayed stream at `http://yourIP:54017/stream`. This can be embedded directly into an `<img>` tag on modern browsers like so: `<img src="http://yourIP:54017/stream">`
4. The status of mjpeg-relay is displayed at `http://yourIP:54017/status`
