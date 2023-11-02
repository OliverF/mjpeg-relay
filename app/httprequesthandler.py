import socket
import threading
import logging
import re
import traceback
from .status import Status
from .streaming import TCPStreamingClient
from .broadcaster import Broadcaster

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
		self.acceptsock.listen(10)

		self.broadcast = Broadcaster._instance
		self.status = Status._instance

		self.kill = False

		self.acceptThread = threading.Thread(target = self.acceptClients)
		self.acceptThread.daemon = True

	def start(self):
		self.acceptThread.start()

	#
	# Thread to process client requests
	#
	def handleRequest(self, clientsock):
		buff = bytearray()
		while True:
			try:
				data = clientsock.recv(64)
				if (data == b""):
					break

				buff.extend(data)

				if buff.find(b"\r\n\r\n") >= 0 or buff.find(b"\n\n") >= 0:
					break #as soon as the header is sent - we only care about GET requests

			except Exception as e:
				logging.error(f"Error on importing request data to buffer")
				traceback.print_exc()
				break

		if (buff != b""):
			try:
				match = re.search(b'GET (.*) ', buff)
				requestPath = match.group(1)
			except Exception as e:
				logging.error("Client sent unexpected request")
				logging.debug(f"Request: {buff}")
				return

			#explicitly deal with individual requests. Verbose, but more secure
			if (b"/status" in requestPath):
				clientsock.sendall(b'HTTP/1.0 200 OK\r\nContentType: text/html\r\n\r\n')
				clientsock.sendall(self.statusHTML.format(clientcount = self.broadcast.getClientCount(), bwin = float(self.status.bandwidthIn*8)/1000000, bwout = float(self.status.bandwidthOut*8)/1000000).encode())
				clientsock.close()
			elif (b"/style.css" in requestPath):
				clientsock.sendall(b'HTTP/1.0 200 OK\r\nContentType: text/html\r\n\r\n')
				clientsock.sendall(self.statusCSS.encode())
				clientsock.close()
			elif (b"/stream" in requestPath):
				if (self.broadcast.broadcasting):
					clientsock.sendall(self.dummyHeader.format(boundaryKey = self.broadcast.boundarySeparator.decode()).encode())
					client = TCPStreamingClient(clientsock)
					client.start()
					self.broadcast.clients.append(client)
				else:
					clientsock.close()
			elif (b"/snapshot" in requestPath):
				clientsock.sendall(b'HTTP/1.0 200 OK\r\n')
				clientsock.sendall(b'Content-Type: image/jpeg\r\n')
				clientsock.sendall(f'Content-Length: {len(self.broadcast.lastFrame)}\r\n\r\n'.encode())
				clientsock.sendall(self.broadcast.lastFrame)
				clientsock.close()
			else:
				clientsock.sendall(b'HTTP/1.0 302 FOUND\r\nLocation: /status')
				clientsock.close()
		else:
			logging.info("Client connected but didn't make a request")

	#
	# Thread to handle connecting clients
	#
	def acceptClients(self):
		while True:
			clientsock, addr = self.acceptsock.accept()

			if self.kill:
				clientsock.close()
				return
			handlethread = threading.Thread(target = self.handleRequest, args = (clientsock,))
			handlethread.start()
