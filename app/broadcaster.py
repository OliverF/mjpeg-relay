import sys
sys.tracebacklimit = 0
import traceback
import threading
import logging
import requests
import re
import time
import base64
from .status import Status

class HTTPBasicThenDigestAuth(requests.auth.HTTPDigestAuth):
	"""Try HTTPBasicAuth, then HTTPDigestAuth."""

	def __init__(self):
		super(HTTPBasicThenDigestAuth, self).__init__(None, None)

	def __call__(self, r):
		# Extract auth from URL
		self.username, self.password = requests.utils.get_auth_from_url(r.url)

		# Prepare basic auth
		r = requests.auth.HTTPBasicAuth(self.username, self.password).__call__(r)

		# Let HTTPDigestAuth handle the 401
		return super(HTTPBasicThenDigestAuth, self).__call__(r)

class Broadcaster:
	"""Handles relaying the source MJPEG stream to connected clients"""

	_instance = None

	def __init__(self, url):
		self.url = url

		self.clients = []
		self.webSocketClients = []

		self.status = Status._instance

		self.kill = False
		self.broadcastThread = threading.Thread(target = self.streamFromSource)
		self.broadcastThread.daemon = True

		self.lastFrame: bytes = b""
		self.lastFrameBuffer: bytes = b""

		self.connected = False
		self.broadcasting = False

		try:
			feedLostFile = open("app/resources/feedlost.jpeg", "rb") #read-only, binary
			feedLostImage = feedLostFile.read()
			feedLostFile.close()
			self.feedLostFrame = bytearray(f"Content-Type: image/jpeg\r\nContent-Length: {len(feedLostImage)}\r\n\r\n",'utf-8')
			self.feedLostFrame.extend(feedLostImage)
		except IOError as e:
			logging.warning("Unable to read feedlost.jpeg")
			# traceback.print_exc()
			self.feedLostFrame = False

		Broadcaster._instance = self

	def start(self):
		if (self.connectToStream()):
			self.broadcasting = True
			logging.info(f"Connected to stream source, boundary separator: {self.boundarySeparator}")
			self.broadcastThread.start()

	#
	# Connects to the stream source
	#
	def connectToStream(self):
		try:
			self.sourceStream = requests.get(self.url, stream = True, timeout = 3, auth = HTTPBasicThenDigestAuth())
		except Exception as e:
			logging.error(f"[ERROR] Unable to connect to stream source at {self.url}")
			traceback.print_exc()
			return False
		except:
			logging.error("[ERROR] failed to connect to stream source.")
			pass
		

		self.boundarySeparator: bytes = self.parseStreamHeader(self.sourceStream.headers['Content-Type']).encode()

		if (not self.boundarySeparator):
			logging.error("Unable to find boundary separator in the header returned from the stream source")
			return False

		self.connected = True
		return True

	#
	# Parses the stream header and returns the boundary separator
	#
	def parseStreamHeader(self, header) -> str:
		if (not isinstance(header, str)):
			return None

		match = re.search(r'boundary=(.*)', header, re.IGNORECASE)
		try:
			boundary = match.group(1)
			if not boundary.startswith("--"):
				boundary = "--" + boundary
			return boundary
		except:
			logging.error("[ERROR] Unexpected header returned from stream source; unable to parse boundary")
			logging.debug(f"header={header}")
			return None

	#
	# Returns the total number of connected clients
	#
	def getClientCount(self):
		return len(self.clients) + len(self.webSocketClients)

	#
	# Process data in frame buffer, extract frames when present
	#
	def extractFrames(self, frameBuffer: bytes):
		if (frameBuffer.count(self.boundarySeparator) >= 2):
			#calculate the start and end points of the frame
			start = frameBuffer.find(self.boundarySeparator)
			end = frameBuffer.find(self.boundarySeparator, start + 1)

			#extract full MJPEG frame
			mjpegFrame = frameBuffer[start:end]

			#extract frame data
			frameStart = frameBuffer.find(b"\r\n\r\n", start) + len(b"\r\n\r\n")
			frame = frameBuffer[frameStart:end]

			#process for WebSocket clients
			webSocketFrame = base64.b64encode(frame)

			return (mjpegFrame, webSocketFrame, frame, end)
		else:
			return (None, None, None, 0)

	#
	# Broadcast data to a list of StreamingClients
	#
	def broadcastToStreamingClients(self, clients, data: bytes):
		for client in clients:
			if (not client.connected):
				clients.remove(client)
				logging.info(f"\nClient left; {self.getClientCount()} client(s) connected")
			client.bufferStreamData(data)

	#
	# Broadcast data to all connected clients
	#
	def broadcast(self, data: bytes):
		self.lastFrameBuffer += data

		mjpegFrame, webSocketFrame, frame, bufferProcessedTo = self.extractFrames(self.lastFrameBuffer)

		if (mjpegFrame and webSocketFrame and frame):
			#delete the frame now that it has been extracted, keep what remains in the buffer
			self.lastFrameBuffer = self.lastFrameBuffer[bufferProcessedTo:]

			#save for /snapshot requests
			self.lastFrame = frame

			#serve to websocket clients
			self.broadcastToStreamingClients(self.webSocketClients, webSocketFrame)

			#serve to standard clients
			self.broadcastToStreamingClients(self.clients, mjpegFrame)

	#
	# Thread to handle reading the source of the stream and rebroadcasting
	#
	def streamFromSource(self):
		while True:
			try:
				for data in self.sourceStream.iter_content(1024):
					if self.kill:
						for client in self.clients + self.webSocketClients:
							client.kill = True
						return
					self.broadcast(data)
					self.status.addToBytesIn(len(data))
					self.status.addToBytesOut(len(data)*self.getClientCount())
			except Exception as e:
				logging.error(f"Lost connection to the stream source: \n")
			finally:
				#flush the frame buffer to avoid conflicting with future frame data
				self.lastFrameBuffer = b""
				self.connected = False
				while (not self.connected):
					data_during_lost = bytearray(self.boundarySeparator)
					data_during_lost.extend(b"\r\n")
					data_during_lost.extend(self.feedLostFrame)
					data_during_lost.extend(b"\r\n")
					if (self.feedLostFrame):
						self.broadcast(data_during_lost)
					time.sleep(5)
					self.connectToStream()