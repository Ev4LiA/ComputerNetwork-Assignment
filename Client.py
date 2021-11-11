from socket import SOCK_DGRAM, SOCK_STREAM
from tkinter import *
from tkinter import messagebox
import time
import tkinter.messagebox
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os
from datetime import datetime


from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"

class Client:
	INIT = 0
	READY = 1
	PLAYING = 2
	state = INIT
	
	SETUP = 0
	PLAY = 1
	PAUSE = 2
	TEARDOWN = 3
	DESCRIBE = 4;
	
	startingTime = 0
	totalPlayTime = 0
	dataRate = 0
	lossRate = 0
	totalByte = 0
	frameNbr = 0
	# Initiation..
	def __init__(self, master, serveraddr, serverport, rtpport, filename):
		self.master = master
		self.master.protocol("WM_DELETE_WINDOW", self.handler)
		self.createWidgets()
		self.serverAddr = serveraddr
		self.serverPort = int(serverport)
		self.rtpPort = int(rtpport)
		self.fileName = filename
		self.rtspSeq = 0
		self.sessionId = 0
		self.requestSent = -1
		self.teardownAcked = 0
		self.connectToServer()
		self.frameNbr = 0
		
	def createWidgets(self):
		"""Build GUI."""
		# Create Setup button
		# self.setup = Button(self.master, width=20, padx=3, pady=3)
		# self.setup["text"] = "Setup"
		# self.setup["command"] = self.setupMovie
		# self.setup.grid(row=1, column=0, padx=2, pady=2)
		# Create Play button		
		self.start = Button(self.master, width=20, padx=3, pady=3)
		self.start["text"] = "Play"
		self.start["command"] = self.playMovie
		self.start.grid(row=1, column=1, padx=2, pady=2)
		
		# Create Pause button			
		self.pause = Button(self.master, width=20, padx=3, pady=3)
		self.pause["text"] = "Pause"
		self.pause["command"] = self.pauseMovie
		self.pause.grid(row=1, column=2, padx=2, pady=2)
		
		# Create Teardown button
		self.teardown = Button(self.master, width=20, padx=3, pady=3)
		self.teardown["text"] = "Stop"
		self.teardown["command"] =  self.stopClient
		self.teardown.grid(row=1, column=3, padx=2, pady=2)

		# Create Describe button
		self.describe = Button(self.master, width=20, padx=3, pady=3)
		self.describe["text"] = "Describe"
		self.describe["command"] = self.describeMovie
		self.describe.grid(row=1, column=4, padx=2, pady=2)
		
		# Create a label to display the movie
		self.label = Label(self.master, height=19)
		self.label.grid(row=0, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5) 
	def setClientStat(self):
		# Create LossRate lable
		self.lossRateStat = Label(self.master, width=20, padx=3, pady=3)
		self.lossRateStat["text"] = "LossRate : " + str("{:.2f}".format(self.lossRate)) + " %"
		self.lossRateStat.grid(row=2, column=1, padx=2, pady=2)	
		# Create Datarate lable
		self.dataRateStat = Label(self.master, width=20, padx=3, pady=3)
		self.dataRateStat["text"] = "Data rate " + str("{:.2f}".format(self.dataRate))+ " Kb/s"
		self.dataRateStat.grid(row=2, column=2, padx=2, pady=2)
		# Create Play Time lable 
		self.playTimeStat = Label(self.master, width=20, padx=3, pady=3)
		self.playTimeStat["text"] = "Playtime : " + str(self.totalPlayTime)
		self.playTimeStat.grid(row=2, column=3, padx=2, pady=2)
		# Crate FPS lable
		self.videoTimeStat = Label(self.master, width=20, padx=3, pady=3)
		self.videoTimeStat["text"] = "Video's Time : " + str(self.frameNbr / 20) + " seconds"
		self.videoTimeStat.grid(row=2, column=4, padx=2, pady=2)
	def setupMovie(self):
		"""Setup button handler."""
		if self.state == self.INIT:
			self.sendRtspRequest(self.SETUP)

	def describeMovie(self):
    		self.sendRtspRequest(self.DESCRIBE)
	
	def exitClient(self):
		"""Teardown button handler."""
		self.sendRtspRequest(self.TEARDOWN)		
		self.master.destroy() # Close the gui window
		os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT) # Delete the cache image from video

	def pauseMovie(self):
		"""Pause button handler."""
		if self.state == self.PLAYING:
			self.sendRtspRequest(self.PAUSE)
	
	def playMovie(self):
		"""Play button handler."""
		if self.state == self.READY:
			# Create a new thread to listen for RTP packets
			threading.Thread(target=self.listenRtp).start()
			self.playEvent = threading.Event()
			self.playEvent.clear()
			self.sendRtspRequest(self.PLAY)

	def stopClient(self):
		self.sendRtspRequest(self.TEARDOWN)		
		if self.state == self.PAUSE:
			os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT) # Delete the cache image from video
		#  Receive Rtsp from server, if server accept close then re-connect again
		if self.teardownAcked == 1:
			self.state = self.INIT
			self.rtspSeq = 0
			self.sessionId = 0
			self.requestSent = -1
			self.teardownAcked = 0
			self.connectToServer()
			self.frameNbr = 0
	
	def listenRtp(self):		
		"""Listen for RTP packets."""
		self.startingTime = datetime.now()
		oldframeNbr = 0
		self.setClientStat()
		ploss = 0
		while True:
			try:
				data = self.rtpSocket.recv(20480)
				if data: 
					rtpPacket = RtpPacket()
					rtpPacket.decode(data)
					currFrameNbr = rtpPacket.seqNum()
					print("Current Seq Num: " + str(currFrameNbr))
					self.totalByte += len(rtpPacket.getPayload())			
					if currFrameNbr > self.frameNbr: # Discard the late packet
						if (currFrameNbr - self.frameNbr > 1):
							ploss = ploss + currFrameNbr - self.frameNbr - 1
						self.frameNbr = currFrameNbr
						self.updateMovie(self.writeFrame(rtpPacket.getPayload()))	
					self.totalPlayTime = datetime.now() - self.startingTime
					self.lossRate = ploss / self.frameNbr * 100
					print("LossRate : " + str(self.lossRate) + "    Loss Packet : " + str(ploss))
					print("Total data : " + str(self.totalByte))
					print("Playtime : " + str(self.totalPlayTime))
					self.dataRate = self.totalByte / abs(self.totalPlayTime.seconds) / 1024 
					print("Data rate " + "{:.2f}".format(self.dataRate)+ " kb/s" )
					if (self.frameNbr - oldframeNbr > 20):
						oldframeNbr = self.frameNbr
						self.setClientStat()
			
			except:
				# Stop listening upon requesting PAUSE or TEARDOWN
				if self.playEvent.isSet(): 
					break
				
				# Upon receiving ACK for TEARDOWN request,
				# close the RTP socket
				if self.teardownAcked == 1:
					self.rtpSocket.shutdown(socket.SHUT_RDWR)
					self.rtpSocket.close()
					# reconnect to server
					break
					
	def writeFrame(self, data):
		"""Write the received frame to a temp image file. Return the image file."""
		cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
		file = open(cachename, "wb")
		file.write(data)
		file.close()
		
		return cachename
	
	def updateMovie(self, imageFile):
		"""Update the image file as video frame in the GUI."""
		photo = ImageTk.PhotoImage(Image.open(imageFile))
		self.label.configure(image = photo, height=288) 
		self.label.image = photo
		
	def connectToServer(self):
		"""Connect to the Server. Start a new RTSP/TCP session."""
		self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			self.rtspSocket.connect((self.serverAddr, self.serverPort))
		except:
			tkinter.messagebox.showwarning('Connection Failed', 'Connection to \'%s\' failed.' %self.serverAddr)
		# Send Init request to server
		self.setupMovie()
	
	def sendRtspRequest(self, requestCode):
		"""Send RTSP request to the server."""	
		#-------------
		# TO COMPLETE
		#-------------
		
		# Setup request
		if requestCode == self.SETUP and self.state == self.INIT:
			threading.Thread(target=self.recvRtspReply).start()
			# Update RTSP sequence number.
			# ...
			self.rtspSeq += 1
			# Write the RTSP request to be sent.
			# request = ...
			request = 'SETUP ' + (self.fileName) + ' RTSP/1.0\nCSeq: ' + str(self.rtspSeq) + '\nTransport: RTP/UDP; client_port= ' + str(self.rtpPort)
			
			# Keep track of the sent request.
			# self.requestSent = ...
			self.requestSent = self.SETUP
		
		# Play request
		elif requestCode == self.PLAY and self.state == self.READY:
			# Update RTSP sequence number.
			# ...
			self.rtspSeq += 1
			
			# Write the RTSP request to be sent.
			# request = ...
			request = 'PLAY ' + (self.fileName) + ' RTSP/1.0\nCSeq: ' + str(self.rtspSeq) + '\nSession: ' + str(self.sessionId)
			
			# Keep track of the sent request.
			# self.requestSent = ...
			self.requestSent = self.PLAY

		# Describe request
		elif requestCode == self.DESCRIBE and self.state == self.READY:
			# Update RTSP sequence number.
			# ...
			self.rtspSeq += 1

			# Write the RTSP request to be sent.
			# request = ...
			request = 'DESCRIBE ' + (self.fileName) + ' RTSP/1.0\nCSeq: ' + str(self.rtspSeq) + '\nSession: ' + str(self.sessionId)

			# Keep track of the sent request.
			# self.requestSent = ...
			self.requestSent = self.DESCRIBE

		# Pause request
		elif requestCode == self.PAUSE and self.state == self.PLAYING:
			# Update RTSP sequence number.
			# ...
			self.rtspSeq += 1
			# Write the RTSP request to be sent.
			# request = ...
			request = 'PAUSE ' + (self.fileName) + ' RTSP/1.0\nCSeq: ' + str(self.rtspSeq) + '\nSession: ' + str(self.sessionId)
			
			# Keep track of the sent request.
			# self.requestSent = ...
			self.requestSent = self.PAUSE
			
		# Teardown request
		elif requestCode == self.TEARDOWN and not self.state == self.INIT:
			# Update RTSP sequence number.
			# ...
			self.rtspSeq += 1
			
			# Write the RTSP request to be sent.
			# request = ...
			request = 'TEARDOWN ' + (self.fileName) + ' RTSP/1.0\nCSeq: ' + str(self.rtspSeq) + '\nSession: ' + str(self.sessionId) 
			self.requestSent = self.TEARDOWN
			# Keep track of the sent request.
			# self.requestSent = ...
			
		else:
			return 
		
		# Send the RTSP request using rtspSocket.
		# ...
		self.rtspSocket.send(request.encode("utf-8"))
		
		print('\nData sent:\n' + request)
	
	def recvRtspReply(self):
		"""Receive RTSP reply from the server."""
		while True:
			reply = self.rtspSocket.recv(1024)
			
			if reply: 
				self.parseRtspReply(reply.decode("utf-8"))
			
			# Close the RTSP socket upon requesting Teardown
			if self.requestSent == self.TEARDOWN:
				self.rtspSocket.shutdown(socket.SHUT_RDWR)
				self.rtspSocket.close()
				break
	
	def parseRtspReply(self, data):
		"""Parse the RTSP reply from the server."""
		lines = data.split('\n')
		seqNum = int(lines[1].split(' ')[1])
		
		# Process only if the server reply's sequence number is the same as the request's
		if seqNum == self.rtspSeq:
			session = int(lines[2].split(' ')[1])
			# New RTSP session ID
			if self.sessionId == 0:
				self.sessionId = session
			
			# Process only if the session ID is the same
			if self.sessionId == session:
				if int(lines[0].split(' ')[1]) == 200: 
					if self.requestSent == self.SETUP:
						#-------------
						# TO COMPLETE
						#-------------
						# Update RTSP state.
						# self.state = ...
						self.state = self.READY
						
						# Open RTP port.
						self.openRtpPort() 
					elif self.requestSent == self.PLAY:
						# self.state = ...
						self.state = self.PLAYING

					elif self.requestSent == self.DESCRIBE:
    						
    					#print('Data Received: ' + lines[3])
						print('Data Received: ' + lines[3])
						messagebox.showwarning('Data Received', 'Kinds of stream: ' + lines[3].split(' ')[0] + '\nEncoding: ' + lines[3].split(' ')[1])
					
					elif self.requestSent == self.PAUSE:
						# self.state = ...
						self.state = self.READY
						# The play thread exits. A new thread is created on resume.
						self.playEvent.set()
					elif self.requestSent == self.TEARDOWN:
						# self.state = ...
						self.state = self.INIT
						# Flag the teardownAcked to close the socket.
						self.teardownAcked = 1 
	
	def openRtpPort(self):
		"""Open RTP socket binded to a specified port."""
		#-------------
		# TO COMPLETE
		#-------------
		# Create a new datagram socket to receive RTP packets from the server
		# self.rtpSocket = ...
		# soc_dgram using for UDP protocol
		self.rtpSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
		
		# Set the timeout value of the socket to 0.5sec
		# ...
		self.rtpSocket.settimeout(0.5)
		try:
			# Bind the socket to the address using the RTP port given by the client user
			# ...
			# self.rtpSocket.bind((socket.gethostname(), self.rtpPort))
			self.rtpSocket.bind(("", self.rtpPort))

		except:
			messagebox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' %self.rtpPort)

	def handler(self):
		"""Handler on explicitly closing the GUI window."""
		self.pauseMovie()
		if messagebox.askokcancel("Quit?", "Are you sure you want to quit?"):
			self.exitClient()
		else: # When the user presses cancel, resume playing.
			self.playMovie()
