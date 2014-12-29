import sys
import socket
import threading
import time
from optparse import OptionParser
import os
import Queue
import re

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
				print e
				break
		
		if (buff != ""):
			try:
				match = re.search(r'GET (.*) ', buff)

				requestPath = match.group(1)
			except Exception, e:
				print "Client sent unexpected request: {}".format(buff)
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
				print "Client connected, sending dummy header"
				clientsock.sendall(self.dummyHeader.format(boundaryKey = self.broadcast.boundarySeparator))

				print "Adding client to join waiting queue"
				self.broadcast.joiningClients.put(clientsock) #blocking, no timeout
			else:
				clientsock.close()
		else:
			print "Client connected but didn't make a request"

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

	def __init__(self, address, port, url, status):
		self.headerType = "multipart/x-mixed-replace"

		self.clients = []
		self.joiningClients = Queue.Queue()
		self.clientCount = 0

		self.status = status

		self.kill = False
		self.broadcastThread = threading.Thread(target = self.streamFromSource)
		self.broadcastThread.daemon = True

		try:
			self.sourcesock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self.sourcesock.connect((address, port))
			print "Connected to stream source"
		except Exception, e:
			print "Error: Unable to connect to stream source at {}:{}: {}".format(address, port, e)
			return

		self.boundarySeparator = self.parseStreamHeader(self.getStreamHeader(self.sourcesock, url))

		if (not self.boundarySeparator):
			print "Unable to find boundary separator in the header returned from the stream source"
			return

		print "Boundary separator: {}".format(self.boundarySeparator)

	def start(self):
		self.broadcastThread.start()

	#
	# Reads the initial stream header
	#
	def getStreamHeader(self, sock, url):
		#send GET request to begin the stream
		get = "GET {} HTTP/1.1\r\n\
		Connection=keep-alive\r\n\r\n".format(url)

		sock.sendall(get)

		buff = ""
		while (buff.find("\r\n\r\n") == -1):
			d = sock.recv(1)

			if (d == ""):
				break

			buff += d

		return buff

	#
	# Parses the stream header and returns the boundary separator
	#
	def parseStreamHeader(self, header):
		if (not isinstance(header, str)):
			return None

		header = header.replace("\r\n", "\n")

		#check for multipart header
		match = re.search(r'Content-Type: (.*?)[;\s]', header, re.IGNORECASE)
		try:
			if (match.group(1) != self.headerType):
				print "Unexpected header returned from stream source: expecting {}, got {}".format(self.headerType, match.group(1))
				return None
		except:
			print "Unexpected header returned from stream source: unable to parse Content-Type"
			print header
			return None

		#get boundary
		match = re.search(r'boundary=(.*)', header, re.IGNORECASE)
		try:
			return match.group(1)
		except:
			print "Unexpected header returned from stream source: unable to parse boundary"
			print header
			return None

	#
	# Thread to handle reading the source of the stream and rebroadcasting
	#
	def streamFromSource(self):
		while True:
			data = self.sourcesock.recv(1024)

			if (data == ""):
				print "Lost connection to the stream source"
				return

			if (self.kill == True):
				for sock in self.clients:
					sock.close()
				self.sourcesock.close()
				return

			#broadcast to connected clients
			for sock in self.clients:
				try:
					sock.sendall(data)
				except:
					self.clients.remove(sock)
					self.clientCount -= 1
					print "Client left. Client count: {}".format(len(self.clients))

			self.status.addToBytesIn(len(data))
			self.status.addToBytesOut(len(data)*len(self.clients))

			if (not self.joiningClients.empty()):
				pos = data.find(self.boundarySeparator)
				if (pos != -1):
					print "Ready to join waiting clients to stream..."
					#waiting clients can join the stream from this moment on
					#first, send the data from the boundary key to the end of what we have in the buffer
					catchup = data[pos:]

					while (not self.joiningClients.empty()):
						print "Joining..."
						acceptsock = self.joiningClients.get()
						acceptsock.sendall(catchup)
						self.clients.append(acceptsock)
						self.clientCount += 1
						print "Client has joined! Client count: {}".format(len(self.clients))

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
	op = OptionParser(usage = "%prog [options] stream-source-address stream-source-url")

	op.add_option("-p", "--port", action="store", default = 54321, dest="port", help = "Port to broadcast the MJPEG stream on")

	(options, args) = op.parse_args()

	if (len(args) != 2):
		op.print_help()
		sys.exit(1)

	try:
		options.port = int(options.port)
	except ValueError:
		print "Port must be numeric"
		op.print_help()
		sys.exit(1)

	try:
		address, port = args[0].split(":", 2)
		port = int(port)
	except ValueError:
		print "stream-source-address should be in the format host:port"
		op.print_help()
		sys.exit(1)

	status = Status()
	statusthread = threading.Thread(target=status.run)
	statusthread.daemon = True
	statusthread.start()

	broadcast = Broadcaster(address, port, args[1], status)
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