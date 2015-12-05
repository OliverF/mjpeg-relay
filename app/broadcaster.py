import Queue
import threading
import logging
import requests
import re
import time
import base64
from status import Status

class Broadcaster:
	"""Handles relaying the source MJPEG stream to connected clients"""

	_instance = None

	def __init__(self, url):
		self.headerType = "multipart/x-mixed-replace"
		self.url = url

		self.clients = []
		self.webSocketClients = []
		self.joiningClients = Queue.Queue()
		self.clientCount = 0

		self.status = Status._instance

		self.kill = False
		self.broadcastThread = threading.Thread(target = self.streamFromSource)
		self.broadcastThread.daemon = True

		self.lastFrame = ""
		self.lastFrameBuffer = ""

		self.connected = False
		self.broadcasting = False

		try:
			feedLostFile = open("app/resources/feedlost.jpeg", "rb") #read-only, binary
			feedLostImage = feedLostFile.read()
			feedLostFile.close()

			self.feedLostFrame = 	"Content-Type: image/jpeg\r\n"\
									"Content-Length: {}\r\n\r\n"\
									"{}".format(len(feedLostImage), feedLostImage)
		except IOError, e:
			logging.warning("Unable to read feedlost.jpeg: {}".format(e))
			self.feedLostFrame = False

		Broadcaster._instance = self

	def start(self):
		if (self.connectToStream()):
			self.broadcasting = True
			logging.info("Connected to stream source, boundary separator: {}".format(self.boundarySeparator))
			self.broadcastThread.start()

	#
	# Connects to the stream source
	#
	def connectToStream(self):
		try:
			self.sourceStream = requests.get(self.url, stream = True, timeout = 10)
		except Exception, e:
			logging.error("Error: Unable to connect to stream source at {}: {}".format(self.url, e))
			return False

		self.boundarySeparator = self.parseStreamHeader(self.sourceStream.headers['Content-Type'])

		if (not self.boundarySeparator):
			logging.error("Unable to find boundary separator in the header returned from the stream source")
			return False

		self.connected = True
		return True

	#
	# Parses the stream header and returns the boundary separator
	#
	def parseStreamHeader(self, header):
		if (not isinstance(header, str)):
			return None

		match = re.search(r'boundary=(.*)', header, re.IGNORECASE)
		try:
			return match.group(1)
		except:
			logging.error("Unexpected header returned from stream source: unable to parse boundary")
			logging.error(header)
			return None

	#
	# Returns the total number of connected clients
	#
	def getClientCount(self):
		return len(self.clients) + len(self.webSocketClients)

	#
	# Process data in frame buffer, extract frames when present
	#
	def extractFrames(self, frameBuffer):
		if (frameBuffer.count(self.boundarySeparator) >= 2):
			#calculate the start and end points of the frame
			start = frameBuffer.find(self.boundarySeparator) + (len(self.boundarySeparator) - 1)
			end = frameBuffer.find(self.boundarySeparator, start)

			#extract frame data
			imageStart = frameBuffer.find("\r\n\r\n", start) + len("\r\n\r\n")
			image = frameBuffer[imageStart:end]

			return (image, end)
		else:
			return (None,0)

	#
	# Broadcast data to all connected clients
	#
	def broadcast(self, data):
		#broadcast to connected clients
		for client in self.clients:
			if (not client.connected):
				self.clients.remove(client)
				logging.info("Client left. Client count: {}".format(self.getClientCount()))
			client.bufferStreamData(data)

		self.lastFrameBuffer += data
		frame, bufferProcessedTo = self.extractFrames(self.lastFrameBuffer)
		if (frame):
			#delete the frame now that it has been extracted, keep what remains in the buffer (faster, won't miss part of the next frame)
			self.lastFrameBuffer = self.lastFrameBuffer[bufferProcessedTo:]

			#save for /snapshot requests
			self.lastFrame = frame

			#serve to websocket clients
			for client in self.webSocketClients:
				if (not client.connected):
					self.webSocketClients.remove(client)
					logging.info("Client left. Client count: {}".format(self.getClientCount()))
				client.bufferStreamData(base64.b64encode(frame))

		if (not self.joiningClients.empty()):
			pos = data.find(self.boundarySeparator)
			if (pos != -1):
				logging.info("Ready to join waiting clients to stream...")
				#waiting clients can join the stream from this moment on
				#first, send the data from the boundary key to the end of what we have in the buffer
				catchup = data[pos:]

				while (not self.joiningClients.empty()):
					logging.info("Joining...")
					try:
						client = self.joiningClients.get()
						client.bufferStreamData(catchup)
						self.clients.append(client)
						logging.info("Client has joined! Client count: {}".format(len(self.clients)))
					except Exception, e:
						logging.info("Failed to join client to stream: {}".format(e))

	#
	# Thread to handle reading the source of the stream and rebroadcasting
	#
	def streamFromSource(self):
		while True:
			try:
				for data in self.sourceStream.iter_content(1024):
					if (self.kill == True):
						for client in self.clients + self.webSocketClients:
							client.kill = True
						return
					self.broadcast(data)
					self.status.addToBytesIn(len(data))
					self.status.addToBytesOut(len(data)*self.getClientCount())
			except Exception, e:
				logging.error("Lost connection to the stream source: {}".format(e))
			finally:
				#flush the frame buffer to avoid conflicting with future image data
				self.lastFrameBuffer = ""
				self.connected = False
				while (not self.connected):
					if (self.feedLostFrame):
						data = "--" + self.boundarySeparator + "\r\n" + self.feedLostFrame + "\r\n"
						self.broadcast(data)
					time.sleep(5)
					self.connectToStream()