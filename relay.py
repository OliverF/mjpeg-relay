import sys
sys.tracebacklimit = 0
import socket
import threading
import os
import logging
from SimpleWebSocketServer import SimpleWebSocketServer
from optparse import OptionParser
from app.status import Status
from app.broadcaster import Broadcaster
from app.httprequesthandler import HTTPRequestHandler
from app.streaming import WebSocketStreamingClient


#
# Close threads gracefully
#
def quit():
	broadcaster.kill = True
	requestHandler.kill = True
	quitsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	quitsock.connect(("127.0.0.1", options.port))
	quitsock.close()
	sys.exit(1)

if __name__ == '__main__':
	op = OptionParser(usage = "%prog [options] stream-source-url")

	op.add_option("-p", "--port", action="store", default = 54321, dest="port", help = "Port to serve the MJPEG stream on")
	op.add_option("-w", "--ws-port", action="store", default = 54322, dest="wsport", help = "Port to serve the MJPEG stream on via WebSockets")
	op.add_option("-q", "--quiet", action="store_true", default = False, dest="quiet", help = "Silence non-essential output")
	op.add_option("-d", "--debug", action="store_true", default = False, dest="debug", help = "Turn debugging on")

	(options, args) = op.parse_args()

	if (len(args) != 1):
		logging.info(f"ENV SOURCE_URL = {os.environ.get('SOURCE_URL', None)}")
		if os.environ.get('SOURCE_URL', None) == None:
			op.print_help()
			sys.exit(1)
		else:
			source = os.environ.get('SOURCE_URL', None)
	else:
		source = args[0]

	logging.basicConfig(level=logging.WARNING if options.quiet else logging.INFO, format="%(message)s")
	logging.getLogger("requests").setLevel(logging.WARNING if options.quiet else logging.INFO)

	if options.debug:
		from http.client import HTTPConnection
		HTTPConnection.debuglevel = 1
		logging.getLogger().setLevel(logging.DEBUG)
		logging.getLogger("requests").setLevel(logging.DEBUG)

	try:
		options.port = int(options.port)
		options.wsport = int(options.wsport)
	except ValueError:
		logging.error("Port must be numeric")
		op.print_help()
		sys.exit(1)

	Status()
	statusThread = threading.Thread(target=Status._instance.run)
	statusThread.daemon = True
	statusThread.start()

	broadcaster = Broadcaster(source)
	broadcaster.start()

	requestHandler = HTTPRequestHandler(options.port)
	requestHandler.start()

	s = SimpleWebSocketServer('', options.wsport, WebSocketStreamingClient)
	webSocketHandlerThread = threading.Thread(target=s.serveforever)
	webSocketHandlerThread.daemon = True
	webSocketHandlerThread.start()

	try:
		while eval(input()) != "quit":
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
