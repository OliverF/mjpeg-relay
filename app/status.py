import time

class Status:

	_instance = None

	def __init__(self):
		self.bytesOut = 0
		self.bytesIn = 0
		self.framesIn = 0
		self.framesOut = 0

		self.bandwidthOut = 0
		self.bandwidthIn = 0
		self.framerateIn = 0
		self.framerateOut = 0

		Status._instance = self

	def addToBytesOut(self, byteCount):
		self.bytesOut += byteCount

	def addToBytesIn(self, byteCount):
		self.bytesIn += byteCount

	def incFramesIn(self):
		self.framesIn += 1.0

	def incFramesOut(self):
		self.framesOut += 1.0

	def run(self):
		while True:
			self.bandwidthOut = self.bytesOut / 5
			self.bandwidthIn = self.bytesIn / 5
			self.framerateIn = self.framesIn / 5
			self.framerateOut = self.framesOut / 5

			self.bytesIn = 0
			self.bytesOut = 0
			self.framesIn = 0
			self.framesOut = 0

			time.sleep(5)
