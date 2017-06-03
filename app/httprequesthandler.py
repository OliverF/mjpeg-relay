import socket
import threading
import logging
import re
from status import Status
from streaming import TCPStreamingClient
from broadcaster import Broadcaster

class HTTPRequestHandler:
	"""Handles the initial connection with HTTP clients"""

	def __init__(self, port):
		#response we'll send to the client, pretending to be from the real stream source
		dummyHeaderfh = open('app/resources/dummy.header', 'r')
		self.dummyHeader = dummyHeaderfh.read()

		cssfh = open('app/web/style.css', 'r')
		self.statusCSS = cssfh.read()

		htmlfh = open('app/web/status.html', 'r')
		self.statusHTML = htmlfh.read()

		self.acceptsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.acceptsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.acceptsock.bind(("0.0.0.0", port))

		self.broadcast = Broadcaster._instance
		self.status = Status._instance

		self.acceptThread = threading.Thread(target = self.acceptClients)
		self.acceptThread.daemon = True

	def start(self):
		self.acceptsock.listen(10)
		self.acceptThread.start()

	def stop(self):
		self.acceptsock.close()

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
				clientsock.sendall(self.statusHTML.format(clientcount = self.broadcast.getClientCount(), bwin = float(self.status.bandwidthIn*8)/1000000, bwout = float(self.status.bandwidthOut*8)/1000000))
				clientsock.close()
			elif ("/style.css" in requestPath):
				clientsock.sendall('HTTP/1.0 200 OK\r\nContentType: text/html\r\n\r\n')
				clientsock.sendall(self.statusCSS)
				clientsock.close()
			elif ("/stream" in requestPath):
				if (self.broadcast.broadcasting):
					clientsock.sendall(self.dummyHeader.format(boundaryKey = self.broadcast.boundarySeparator))
					client = TCPStreamingClient(clientsock)
					client.start()
					self.broadcast.clients.append(client)
				else:
					clientsock.close()
			elif ("/snapshot" in requestPath):
				clientsock.sendall('HTTP/1.0 200 OK\r\n')
				clientsock.sendall('Content-Type: image/jpeg\r\n')
				clientsock.sendall('Content-Length: {}\r\n\r\n'.format(len(self.broadcast.lastFrame)))
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
			handlethread = threading.Thread(target = self.handleRequest, args = (clientsock,))
			handlethread.start()