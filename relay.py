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
import base64
from app.status import Status
from app.broadcaster import Broadcaster
from app.httprequesthandler import HTTPRequestHandler
from app.streaming import WebSocketStreamingClient
try:
	from app.SimpleWebSocketServer.SimpleWebSocketServer import SimpleWebSocketServer
except ImportError, e:
	print "Failed to import dependency: {0}".format(e)
	print "Please ensure the SimpleWebSocketServer submodule has been correctly installed: git submodule update --init"
	sys.exit(1)

#
# Close threads gracefully
#
def quit():
	if not broadcast is None:
		broadcast.kill = True
	if not requestHandler is None:
		requestHandler.kill = True
	quitsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	quitsock.connect(("127.0.0.1", options.port))
	quitsock.close()
	sys.exit(1)

if __name__ == '__main__':
	op = OptionParser(usage = "%prog [options] stream-source-url")

	op.add_option("-p", "--port", action="store", default = 54321, dest="port", help = "Port to serve the MJPEG stream on (default: 54321, 0 to disable)")
	op.add_option("-w", "--ws-port", action="store", default = 0, dest="wsport", help = "Port to serve the MJPEG stream on via WebSockets (default: disabled)")
	op.add_option("-q", "--quiet", action="store_true", default = False, dest="quiet", help = "Silence non-essential output")

	(options, args) = op.parse_args()

	if (len(args) != 1):
		op.print_help()
		sys.exit(1)

	logging.basicConfig(level=logging.WARNING if options.quiet else logging.INFO, format="%(message)s")
	logging.getLogger("requests").setLevel(logging.WARNING if options.quiet else logging.INFO)

	try:
		options.port = int(options.port)
		options.wsport = int(options.wsport)
	except ValueError:
		logging.error("Port must be numeric")
		op.print_help()
		sys.exit(1)
		
	broadcast = None
	requestHandler = None

	Status()
	statusThread = threading.Thread(target=Status._instance.run)
	statusThread.daemon = True
	statusThread.start()

	broadcaster = Broadcaster(args[0])
	broadcaster.start()

	if options.port>0:
		requestHandler = HTTPRequestHandler(options.port)
		requestHandler.start()
   
	if options.wsport>0:
		s = SimpleWebSocketServer('', options.wsport, WebSocketStreamingClient)
		webSocketHandlerThread = threading.Thread(target=s.serveforever)
		webSocketHandlerThread.daemon = True
		webSocketHandlerThread.start()

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
