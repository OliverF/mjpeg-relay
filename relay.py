import sys
import socket
import threading
import time
from optparse import OptionParser
import os
import Queue
import re
import logging
import requests

class StreamingClient:

	def __init__(self, sock):
		self.sock = sock
		sock.settimeout(5) #long timeout to allow clients some flexibility
		self.streamBuffer = ""
		self.streamQueue = Queue.Queue()
		self.streamThread = threading.Thread(target = self.stream)
		self.streamThread.daemon = True
		self.connected = True
		self.kill = False

	def start(self):
		self.streamThread.start()

	def bufferStreamData(self, data):
		#use a thread-safe queue to ensure stream buffer is not modified while we're sending it
		self.streamQueue.put(data)

	def stream(self):
		while True:
			if (self.kill):
				self.sock.close()
				return

			if (not self.streamQueue.empty()):
				self.streamBuffer += self.streamQueue.get()

			if (len(self.streamBuffer) > 0):
				try:
					streamedTo = self.sock.send(self.streamBuffer)
					self.streamBuffer = self.streamBuffer[streamedTo:]
				except socket.error, e:
					self.connected = False
					self.sock.close()
					return

class RequestHandler:
	"""Handles the initial connection with the client"""

	def __init__(self, port, broadcast, status):
		#response we'll send to the client, pretending to be from the real stream source
		dummyHeaderfh = open('dummy.header', 'r')
		self.dummyHeader = dummyHeaderfh.read()

		cssfh = open('style.css', 'r')
		self.statusCSS = cssfh.read()

		htmlfh = open('status.html', 'r')
		self.statusHTML = htmlfh.read()

		self.acceptsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.acceptsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.acceptsock.bind(("0.0.0.0", port))
		self.acceptsock.listen(10)

		self.broadcast = broadcast
		self.status = status

		self.kill = False

		self.acceptThread = threading.Thread(target = self.acceptClients)
		self.acceptThread.daemon = True

	def start(self):
		self.acceptThread.start()

	#
	# Thread to process client requests
	#
	def handleRequest(self, clientsock):
		buff = ""
		while True:
			try:
				data = clientsock.recv(64)
				if (data == ""):
					break

				buff += data

				if "\r\n\r\n" in buff or "\n\n" in buff:
					break #as soon as the header is sent - we only care about GET requests

			except Exception, e:
				logging.info(e)
				break

		if (buff != ""):
			try:
				match = re.search(r'GET (.*) ', buff)

				requestPath = match.group(1)
			except Exception, e:
				logging.info("Client sent unexpected request: {}".format(buff))
				return

			#explicitly deal with individual requests. Verbose, but more secure
			if ("/status" in requestPath):
				clientsock.sendall('HTTP/1.0 200 OK\r\nContentType: text/html\r\n\r\n')
				clientsock.sendall(self.statusHTML.format(clientcount = self.broadcast.clientCount, bwin = float(self.status.bandwidthIn*8)/1000000, bwout = float(self.status.bandwidthOut*8)/1000000))
				clientsock.close()
			elif ("/style.css" in requestPath):
				clientsock.sendall('HTTP/1.0 200 OK\r\nContentType: text/html\r\n\r\n')
				clientsock.sendall(self.statusCSS)
				clientsock.close()
			elif ("/stream" in requestPath):
				if (self.broadcast.broadcasting):
					logging.info("Client connected, sending dummy header")
					clientsock.sendall(self.dummyHeader.format(boundaryKey = self.broadcast.boundarySeparator))
					client = StreamingClient(clientsock)
					client.start()
					logging.info("Adding client to join waiting queue")
					self.broadcast.joiningClients.put(client) #blocking, no timeout
				else:
					clientsock.close()
			elif ("/snapshot" in requestPath):
				clientsock.sendall('HTTP/1.0 200 OK\r\n')
				clientsock.sendall(self.broadcast.lastFrame)
				clientsock.close()
			else:
				clientsock.sendall('HTTP/1.0 302 FOUND\r\nLocation: /status')
				clientsock.close()
		else:
			logging.info("Client connected but didn't make a request")

	#
	# Thread to handle connecting clients
	#
	def acceptClients(self):
		while True:
			clientsock, addr = self.acceptsock.accept()

			if (self.kill == True):
				clientsock.close()
				return
			handlethread = threading.Thread(target = self.handleRequest, args = (clientsock,))
			handlethread.start()

class Broadcaster:
	"""Handles relaying the source MJPEG stream to connected clients"""

	def __init__(self, url, status):
		self.headerType = "multipart/x-mixed-replace"
		self.url = url

		self.clients = []
		self.joiningClients = Queue.Queue()
		self.clientCount = 0

		self.status = status

		self.kill = False
		self.broadcastThread = threading.Thread(target = self.streamFromSource)
		self.broadcastThread.daemon = True

		self.lastFrame = ""
		self.lastFrameBuffer = ""

		self.connected = False
		self.broadcasting = False

		try:
			feedLostFile = open("feedlost.jpeg", "rb") #read-only, binary
			feedLostImage = feedLostFile.read()
			feedLostFile.close()

			self.feedLostFrame = 	"Content-Type: image/jpeg\r\n"\
									"Content-Length: {}\r\n\r\n"\
									"{}".format(len(feedLostImage), feedLostImage)
		except IOError, e:
			logging.warning("Unable to read feedlost.jpeg: {}".format(e))
			self.feedLostFrame = False

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
	# Broadcast data to all connected clients
	#
	def broadcast(self, data):
		#broadcast to connected clients
		for client in self.clients:
			if (not client.connected):
				self.clients.remove(client)
				self.clientCount -= 1
				logging.info("Client left. Client count: {}".format(len(self.clients)))
			client.bufferStreamData(data)

		self.status.addToBytesIn(len(data))
		self.status.addToBytesOut(len(data)*len(self.clients))

		self.lastFrameBuffer += data
		if (self.lastFrameBuffer.count(self.boundarySeparator) == 2):
			#calculate the start and end points of the frame
			start = self.lastFrameBuffer.find(self.boundarySeparator) + (len(self.boundarySeparator) - 1)
			end = self.lastFrameBuffer.find(self.boundarySeparator, start)
			#extract latest frame data
			self.lastFrame = self.lastFrameBuffer[start:end]
			#delete the frame now that it has been extracted, keep what remains in the buffer (faster, won't miss part of the next frame)
			self.lastFrameBuffer = self.lastFrameBuffer[end:]

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
						self.clientCount += 1
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
						for client in self.clients:
							client.kill = True
						return
					self.broadcast(data)
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


class Status:
	def __init__(self):
		self.bytesOut = 0
		self.bytesIn = 0

		self.bandwidthOut = 0
		self.bandwidthIn = 0

	def addToBytesOut(self, byteCount):
		self.bytesOut += byteCount

	def addToBytesIn(self, byteCount):
		self.bytesIn += byteCount

	def run(self):
		while True:
			self.bandwidthOut = self.bytesOut
			self.bandwidthIn = self.bytesIn

			self.bytesIn = 0
			self.bytesOut = 0

			time.sleep(1)

#
# Close threads gracefully
#
def quit():
	broadcast.kill = True
	requestHandler.kill = True
	quitsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	quitsock.connect(("127.0.0.1", options.port))
	quitsock.close()
	sys.exit(1)

if __name__ == '__main__':
	op = OptionParser(usage = "%prog [options] stream-source-url")

	op.add_option("-p", "--port", action="store", default = 54321, dest="port", help = "Port to broadcast the MJPEG stream on")
	op.add_option("-q", "--quiet", action="store_true", default = False, dest="quiet", help = "Silence non-essential output")

	(options, args) = op.parse_args()

	if (len(args) != 1):
		op.print_help()
		sys.exit(1)

	logging.basicConfig(level=logging.WARNING if options.quiet else logging.INFO, format="%(message)s")
	logging.getLogger("requests").setLevel(logging.WARNING if options.quiet else logging.INFO)

	try:
		options.port = int(options.port)
	except ValueError:
		logging.error("Port must be numeric")
		op.print_help()
		sys.exit(1)

	status = Status()
	statusthread = threading.Thread(target=status.run)
	statusthread.daemon = True
	statusthread.start()

	broadcast = Broadcaster(args[0], status)
	broadcast.start()

	requestHandler = RequestHandler(options.port, broadcast, status)
	requestHandler.start()

	try:
		while raw_input() != "quit":
			continue
		quit()
	except KeyboardInterrupt:
		quit()
	except EOFError:
		#this exception is raised when ctrl-c is used to close the application on Windows, appears to be thrown twice?
		try:
			quit()
		except KeyboardInterrupt:
			os._exit(0)
