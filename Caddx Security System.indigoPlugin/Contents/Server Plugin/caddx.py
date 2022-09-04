#! /usr/bin/env python
# -*- coding: utf-8 -*-
################################################################################
# This is an Indigo 2022.1+ plugin to support the "Caddx NetworX NX-8e Alarm System"
# Original 2011 by Ian Sibley
# Ported to Python 3 + Refactor 2022 by Don Hoffman
################################################################################

################################################################################
# Python Imports
################################################################################
import logging
import time
import queue
import copy
import datetime

################################################################################
# Local Imports
################################################################################
import indigo

################################################################################
# Globals
################################################################################
panelFirmware = ""						# used as a comm alive flag on initiate comms
keypadDisplayName = " "					# used to store temporary zoneDisplayName for Keypad Display Name used in creating zone devices

# Simple Requests and Commands		message format[0x7e, msg_length, msg_number, {msg_contents}, checksum1, checksum2,]
ACK = "011d"
NAK = "011e"
CAN = "011f"

# Commands
cmdArmStay = "04bd030101"
cmdArmAway = "04bd020101"
cmdDisarm = "04bd010101"
cmdFirePanic = "03be0401"
cmdMedicalPanic = "03be0501"
cmdPolicePanic = "03be0601"
cmdTurnOffSounderOrAlarm = "04bd000101"
cmdCancel = "04bd040101"
cmdInitiateAutoArm = "04bd050101"
cmdStartWalkTestMode = "04bd060101"
cmdStopWalkTestMode = "04bd070101"
cmdStay1ButtonArmToggleInteriors = "03be0001"
cmdChimeToggleChimeMode = "03be0101"
cmdExitButtonArmToggleInstant = "03be0201"
cmdBypassInteriors = "03be0301"
cmdSmokeDetectorReset = "03be0701"
cmdAutoCallbackDownload = "03be0801"
cmdManualPickupDownload = "03be0901"
cmdEnableSilentExitForThisArmCycle = "03be0a01"
cmdPerformTest = "03be0b01"
cmdGroupBypass = "03be0c01"
cmdAuxiliaryFunction1 = "03be0d01"
cmdAuxiliaryFunction2 = "03be0e01"
cmdStartKeypadSounder = "03be0f01"
cmdInterfaceConfigurationRequest = "0121"
cmdZoneNameRequest = "0223"
cmdZoneStatusRequest = "0224"
cmdZonesSnapshotRequest = "0225"
cmdPartitionStatusRequest = "0226"
cmdPartitionSnapshotRequest = "0127"
cmdSystemStatusRequest = "0128"
cmdUserInformationRequestWithoutPin = "0233"
cmdZoneBypassToggle = "02bf"
cmdSetClockCalendar = "073b"

# Spoken Text Comments
sayArmingStay = "Alarm system arming in Stay Mode"
sayArmedStay = "Alarm system armed in Stay Mode"
sayArmingAway = "Alarm system arming in Away Mode"
sayArmedAway = "Alarm system armed in Away Mode"
sayArmed = "Alarm system Armed"
sayDisarmed = "Alarm system Disarmed. Welcome Home"
sayExitDelayWarning = "Warning - exit delay expires in 10 seconds"
sayFailedToArm = "Alarm system Failed To Arm"
sayZoneTripped = "Intruder Alert, sensor tripped in"
sayActivateFire = "The fire alarm has been activated. Please evacuate the building immediately"
sayActivateMedical = "A medical emergency has been activated. An Ambulance has been called"
sayActivatePolice = "A duress alert has been activated. The police have been called"


class CaddxException(Exception):
	pass


class CaddxShutdown(CaddxException):
	pass


class CaddxProgramError(CaddxException):
	pass


class Caddx(object):

	def __init__(self, plugin):
		self.plugin = plugin

		self.zoneList = {}
		self.trippedZoneList = {}
		self.keypadList = {}
		self.partitionList = {}
		self.keypadList = {}
		self.userList = {}
		self.panelList = {}
		self.systemStatusList = {}
		
		self.commandQueue = queue.Queue()
		self.shutdown = ""
		self.devicePort = None
		self.conn = None
		self.systemId = 1
		self.model = ""
		self.initialiseAlarmSystem = False
		self.configRead = False
		self.messageACK = True
		self.receivedValidMessage = False
		self.breachedZone = " "
		self.watchdogTimer = (time.time()) + 5
		self.suspendInterfaceConfigMessageDisplay = True
		self.errorCountComm = 0
		self.devStateChangeList = {}
		self.repeatAlarmTripped = False

	def __del__(self):
		pass
		
	################################################################################
	# Actions command method routines <action.xml>
	################################################################################

	########################################
	# Primary & Secondary Keypad Commands routines
	########################################

	def actionGeneric(self, pluginAction, action):
		dev = indigo.devices[pluginAction.deviceId]
		# noinspection PyUnusedLocal
		partition = int(dev.pluginProps["address"])
		# noinspection PyUnusedLocal
		keypad = int(dev.pluginProps["associatedKeypad"])
		if action == "Arm in Stay Mode":
			logPrintMessage = "Execute action:        Arm Alarm in Stay Mode"
			self.sendMsgToQueue(cmdArmStay)
			if self.plugin.enableSpeakPrompts:	
				indigo.server.speak(sayArmingStay)
		elif action == "Arm in Away Mode":
			logPrintMessage = "Execute action:        Arm Alarm in Away Mode"
			self.sendMsgToQueue(cmdArmAway)
			if self.plugin.enableSpeakPrompts:
				indigo.server.speak(sayArmingAway)
		elif action == "Disarm System":
			logPrintMessage = "Execute action:        Disarm System"
			self.sendMsgToQueue(cmdDisarm)
		elif action == "Activate Fire Panic":
			logPrintMessage = "Execute action:        Activate Fire Alert"
			self.sendMsgToQueue(cmdFirePanic)
			if self.plugin.enableSpeakPrompts:
				indigo.server.speak(sayActivateFire)
		elif action == "Activate Medical Panic":
			logPrintMessage = "Execute action:        Activate Medical Alert"
			self.sendMsgToQueue(cmdMedicalPanic)
			if self.plugin.enableSpeakPrompts:
				indigo.server.speak(sayActivateMedical)
		elif action == "Activate Police Duress":
			logPrintMessage = "Execute action:        Activate Police Duress"
			self.sendMsgToQueue(cmdPolicePanic)
			if self.plugin.enableSpeakPrompts:
				indigo.server.speak(sayActivatePolice)
		elif action == "Turn Off Any Sounder or Alarm":
			logPrintMessage = "Execute action:        Turn Off Any Sounder or Alarm"
			self.sendMsgToQueue(cmdTurnOffSounderOrAlarm)
		elif action == "Cancel":
			logPrintMessage = "Execute action:        Cancel"
			self.sendMsgToQueue(cmdCancel)
		elif action == "Initiate Auto Arm":
			logPrintMessage = "Execute action:        Initiate Auto Arm"
			self.sendMsgToQueue(cmdInitiateAutoArm)
		elif action == "Start Walk Test Mode":
			logPrintMessage = "Execute action:        Start Walk Test Mode"
			self.sendMsgToQueue(cmdStartWalkTestMode)
		elif action == "Stop Walk Test Mode":
			logPrintMessage = "Execute action:        Stop Walk Test Mode"
			self.sendMsgToQueue(cmdStopWalkTestMode)
		elif action == "Stay 1 Button Arm Toggle Interiors":
			logPrintMessage = "Execute action:        Stay (1 button arm / toggle Interiors)"
			self.sendMsgToQueue(cmdStay1ButtonArmToggleInteriors)
		elif action == "Toggle Chime Mode":
			logPrintMessage = "Execute action:        Chime (toggle Chime Mode)"
			self.sendMsgToQueue(cmdChimeToggleChimeMode)
		elif action == "Exit 1 Button Arm Toggle Instant":
			logPrintMessage = "Execute action:        Exit (1 button arm / toggle Instant)"
			self.sendMsgToQueue(cmdExitButtonArmToggleInstant)
		elif action == "Bypass Interiors":
			logPrintMessage = "Execute action:        Bypass Interiors"
			self.sendMsgToQueue(cmdBypassInteriors)
		elif action == "Reset Smoke Detectors":
			logPrintMessage = "Execute action:        Reset Smoke Detectors"
			self.sendMsgToQueue(cmdSmokeDetectorReset)
		elif action == "Auto Callback Download":
			logPrintMessage = "Execute action:        Auto Callback Download"
			self.sendMsgToQueue(cmdAutoCallbackDownload)
		elif action == "Manual Pickup Download":
			logPrintMessage = "Execute action:        Manual Pickup Download"
			self.sendMsgToQueue(cmdManualPickupDownload)
		elif action == "Enable Silent Exit for this Arm Cycle":
			logPrintMessage = "Execute action:        Enable Silent Exit (for this arm cycle)"
			self.sendMsgToQueue(cmdEnableSilentExitForThisArmCycle)
		elif action == "Perform Test":
			logPrintMessage = "Execute action:        Perform Test"
			self.sendMsgToQueue(cmdPerformTest)
		elif action == "Group Bypass":
			logPrintMessage = "Execute action:        Group Bypass"
			self.sendMsgToQueue(cmdGroupBypass)
		elif action == "Auxiliary Function 1":
			logPrintMessage = "Execute action:        Auxiliary Function 1"
			self.sendMsgToQueue(cmdAuxiliaryFunction1)
		elif action == "Auxiliary Function 2":
			logPrintMessage = "Execute action:        Auxiliary Function 2"
			self.sendMsgToQueue(cmdAuxiliaryFunction2)
		elif action == "Start Keypad Sounder":
			logPrintMessage = "Execute action:        Start Keypad Sounder"
			self.sendMsgToQueue(cmdStartKeypadSounder)
		else:
			logPrintMessage = f"Execute action:        Requested Action {action} not defined."
		if self.plugin.commandActInfo or self.plugin.debug:
			indigo.server.log("%s" % logPrintMessage)

	########################################
	# Supported Requests and Commands routines
	########################################

	def actionCmdMessage(self, pluginAction, action):
		if action == "Interface Configuration Request":
			logPrintMessage = "Execute action:        Interface Configuration Request"
			self.sendMsgToQueue(cmdInterfaceConfigurationRequest)
		elif action == "Zone Name Request":
			value = int(pluginAction.props["zone"]) - 1  # 0 = zone 1
			zone = f"{value:02x}"
			zoneNameRequest = cmdZoneNameRequest + zone
			logPrintMessage = "Execute action:        Zone Name Request,  zone: %s" % value
			self.sendMsgToQueue(zoneNameRequest)
		elif action == "Zone Status Request":
			value = int(pluginAction.props["zone"]) - 1  # 0 = zone 1
			zone = f"{value:02x}"
			zoneStatusRequest = cmdZoneStatusRequest + zone
			logPrintMessage = "Execute action:        Zone Status Request,  zone: %s" % value
			self.sendMsgToQueue(zoneStatusRequest)
		elif action == "Zone Status Request ALL":
			for zz in self.zoneList.keys():
				value = int(zz) - 1  # 0 = zone 1
				zone = f"{value:02x}"
				zoneStatusRequest = cmdZoneStatusRequest + zone
				self.sendMsgToQueue(zoneStatusRequest)
			logPrintMessage = "Execute action:        Zone Status Request, all zones"
		elif action == "Zones Snapshot Request":
			value = int(pluginAction.props["zoneOffset"])
			kzoneOffSet = f"{value:02x}"
			zonesSnapshotRequest = cmdZonesSnapshotRequest + kzoneOffSet
			logPrintMessage = "Execute action:        Zones Snapshot Request,  block address: %s" % value
			self.sendMsgToQueue(zonesSnapshotRequest)
		elif action == "Partition Status Request":
			value = int(pluginAction.props["partition"]) - 1  # 0 = partition 1
			kpartition = f"{value:02x}"
			partitionStatusRequest = cmdPartitionStatusRequest + kpartition
			logPrintMessage = "Execute action:        Partition Status Request,  partition: %s" % value
			self.sendMsgToQueue(partitionStatusRequest)
		elif action == "Partition Snapshot Request":
			logPrintMessage = "Execute action:        Partition Snapshot Request"
			self.sendMsgToQueue(cmdPartitionSnapshotRequest)
		elif action == "System Status Request":
			logPrintMessage = "Execute action:        System Status Request"
			self.sendMsgToQueue(cmdSystemStatusRequest)
		# Todo: Incomplete implementation?
		# elif action == "Send X-10 Command":
		# 	logPrintMessage = "Execute action:        Send X-10 Command"
		# 	self.sendMsgToQueue(cmdSystemStatusRequest)
		# elif action == "Log Event Request":
		# 	logPrintMessage = "Execute action:        Log Event Request"
		# 	self.sendMsgToQueue(cmdSystemStatusRequest)
		# elif action == "Send Keypad Text Message":
		# 	logPrintMessage = "Execute action:        Send Keypad Text Message"
		# 	self.sendMsgToQueue(cmdSystemStatusRequest)
		# elif action == "Keypad Terminal Mode Request":
		# 	logPrintMessage = "Execute action:        Keypad Terminal Mode Request"
		# 	self.sendMsgToQueue(cmdSystemStatusRequest)
		# elif action == "Program Data Request":
		# 	logPrintMessage = "Execute action:        Program Data Request"
		# 	self.sendMsgToQueue(cmdSystemStatusRequest)
		# elif action == "Program Data Command":
		# 	logPrintMessage = "Execute action:        Program Data Command"
		# 	self.sendMsgToQueue(cmdSystemStatusRequest)
		# elif action == "User Information Request with Pin":
		# 	logPrintMessage = "Execute action:        User Information Request with Pin"
		# 	self.sendMsgToQueue(cmdSystemStatusRequest)
		elif action == "User Information Request without Pin":
			value = int(pluginAction.props["user"])
			kuser = f"{value:02x}"
			userInformationRequestWithoutPin = cmdUserInformationRequestWithoutPin + kuser
			logPrintMessage = "Execute action:        User Information Request without Pin,  user: %s" % value
			self.sendMsgToQueue(userInformationRequestWithoutPin)
		# Todo: Incomplete implementation?
		# elif action == "Set User Code Command with Pin":
		# 	logPrintMessage = "Execute action:        Set User Code Command with Pin"
		# 	self.sendMsgToQueue(userInformationRequestWithPin)
		# elif action == "Set User Code Command without Pin":
		# 	logPrintMessage = "Execute action:        Set User Code Command without Pin"
		# 	self.sendMsgToQueue(cmdSystemStatusRequest)
		# elif action == "Set User Authorisation with Pin":
		# 	logPrintMessage = "Execute action:        Set User Authorisation with Pin"
		# 	self.sendMsgToQueue(cmdSystemStatusRequest)
		# elif action == "Set User Authorisation without Pin":
		# 	logPrintMessage = "Execute action:        Set User Authorisation without Pin"
		# 	self.sendMsgToQueue(cmdSystemStatusRequest)
		# elif action == "Store Communication Event Command":
		# 	logPrintMessage = "Execute action:        Store Communication Event Command"
		# 	self.sendMsgToQueue(cmdSystemStatusRequest)
		elif action == "Set Clock and Calender":
			logPrintMessage = "Execute action:        Set Clock and Calender"
			self.actionSetClockCalenderCommand(action="")
		elif action == "Zone Bypass toggle":
			value = int(pluginAction.props["bypassZone"]) - 1  # 0 = zone 1
			zone = f"{value:02x}"
			zoneBypassToggle = cmdZoneBypassToggle + zone
			logPrintMessage = f"Execute action:        Zone Bypass Toggle: zone {value}: "
			self.sendMsgToQueue(zoneBypassToggle)
		else:
			logPrintMessage = f"Execute action:        Requested Action: '{action}' is not defined."
		if self.plugin.commandActInfo or self.plugin.debug:
			indigo.server.log(logPrintMessage)
	
	########################################
	# System action requests for database synchronisation
	########################################

	# noinspection PyUnusedLocal
	def actionInterfaceConfigurationRequest(self, action):
		if self.plugin.commandActInfo or self.plugin.debug:
			indigo.server.log("Execute action:        Interface Configuration Request")
		self.sendMsgToQueue(cmdInterfaceConfigurationRequest)
		time.sleep(self.plugin.sleepBetweenComm)
		
	def actionZoneNameRequest(self, action):
		for key in range(0, action):
			zone = f"{key:02x}"  # 0 = zone 1
			zoneNameRequest = cmdZoneNameRequest + zone
			if self.plugin.commandActInfo or self.plugin.debug:
				indigo.server.log("Execute action:        Zone Name Request: %s,   %s  (zone %s)" % (zone, zoneNameRequest, (key + 1)))
			self.sendMsgToQueue(zoneNameRequest)
			time.sleep(self.plugin.sleepBetweenComm)

	def actionZoneStatusRequest(self, action):
		for key in range(0, action):
			zone = f"{key:02x}"  # 0 = zone 1
			zoneStatusRequest = cmdZoneStatusRequest + zone
			if self.plugin.commandActInfo or self.plugin.debug:
				indigo.server.log("Execute action:        Zone Status Request: %s,  %s  (zone %s)" % (zone, zoneStatusRequest, (key + 1)))
			self.sendMsgToQueue(zoneStatusRequest)
			time.sleep(self.plugin.sleepBetweenComm)
									
	def actionZonesSnapshotRequest(self, action):
		for key in range(0, action):
			kzoneOffSet = f"{key:02x}"
			zonesSnapshotRequest = cmdZonesSnapshotRequest + kzoneOffSet
			if self.plugin.commandActInfo or self.plugin.debug:
				indigo.server.log("Execute action:        Zones Snapshot Request: %s,  %s  (block %s)" % (kzoneOffSet, zonesSnapshotRequest, key))
			self.sendMsgToQueue(zonesSnapshotRequest)
			time.sleep(self.plugin.sleepBetweenComm)
		
	def actionPartitionStatusRequest(self, action):
		for key in range(0, action):
			kpartition = f"{key:02x}"		# 0 = partition 1
			partitionStatusRequest = cmdPartitionStatusRequest + kpartition
			if self.plugin.commandActInfo or self.plugin.debug:
				indigo.server.log("Execute action:        Partition Status Request: %s  %s  (partition %s)" % (kpartition, partitionStatusRequest, (key + 1)))
			self.sendMsgToQueue(partitionStatusRequest)
			time.sleep(self.plugin.sleepBetweenComm)

	# noinspection PyUnusedLocal
	def actionPartitionSnapshotRequest(self, action):
		if self.plugin.commandActInfo or self.plugin.debug:
			indigo.server.log("Execute action:        Partition Snapshot Request: Partition 1 - 8")
		self.sendMsgToQueue(cmdPartitionSnapshotRequest)
		time.sleep(self.plugin.sleepBetweenComm)

	# noinspection PyUnusedLocal
	def actionSystemStatusRequest(self, action):
		if self.plugin.commandActInfo or self.plugin.debug:
			indigo.server.log("Execute action:        System Status Request")
		self.sendMsgToQueue(cmdSystemStatusRequest)
		time.sleep(self.plugin.sleepBetweenComm)		

	# noinspection PyUnusedLocal
	def actionLogEventRequest(self, action):
		action = 25
		for key in range(0, action):
			kmessagestart = "022a"
			keventNumber = f"{key+1:02x}"
			logEventRequest = kmessagestart + keventNumber
			if self.plugin.commandActInfo or self.plugin.debug:
				indigo.server.log("Execute action:        Log Event Request: %s,  %s" % (keventNumber, logEventRequest))
			self.sendMsgToQueue(logEventRequest)
			time.sleep(self.plugin.sleepBetweenComm)
		
	def actionUserInformationRequestWithoutPin(self, action):
		for key in range(0, action):
			user = f"{key+1:02x}"
			userInformationRequestWithoutPin = cmdUserInformationRequestWithoutPin + user
			if self.plugin.commandActInfo or self.plugin.debug:
				indigo.server.log("Execute action:        User Information Request without Pin: %s,  %s  (user %s)" % (user, userInformationRequestWithoutPin, (key + 1)))
			self.sendMsgToQueue(userInformationRequestWithoutPin)
			time.sleep(self.plugin.sleepBetweenComm)					

	# noinspection PyUnusedLocal
	def actionSetClockCalenderCommand(self, action):
		timeStamp = time.localtime(time.time())
		kyear = timeStamp.tm_year - 2000  # Even in this day and age, only two digit years accepted by panel.
		kdate = f"{kyear:02x}" + f"{timeStamp.tm_mon:02x}" + f"{timeStamp.tm_mday:02x}"
		ktime = f"{timeStamp.tm_hour:02x}" + f"{timeStamp.tm_min:02x}"
		correctedWDay = [2, 3, 4, 5, 6, 7, 1][timeStamp.tm_wday]  # Correct for offset between time.localtime() and what panels expects.
		kday = f"{correctedWDay:02x}"
		kSetClockCalenderCommand = cmdSetClockCalendar + kdate + ktime + kday
		self.sendMsgToQueue(kSetClockCalenderCommand)
		time.sleep(self.plugin.sleepBetweenComm)

	# Poll each zone for Keypad Display Name to use in Create Zone Device name
	# Todo: singleZoneNameRequest() is used incorrectly by callers.  Figure out what to do?
	def singleZoneNameRequest(self, zoneKey: int) -> None:
		zone = f"{zoneKey:02x}"  # 0 = zone 1
		zoneNameRequest = cmdZoneNameRequest + zone
		self.plugin.debugLog("Execute action:        Zone Name Request: %s,  %s" % (zone, zoneNameRequest))
		self.sendMsg(zoneNameRequest)
		time.sleep(self.plugin.sleepBetweenCreateZone)
											
	################################################################################
	# Routines for Serial Communication Process methods 
	################################################################################
	
	########################################
	# Device Start and Stop methods	
	########################################
	
	def deviceStart(self, dev):
		self.plugin.debugLog("deviceStart:        starting device %s." % dev.name)
			
		if dev.deviceTypeId == 'zone':
			zone = int(dev.pluginProps['address'])
			if zone not in self.zoneList.keys():
				self.zoneList[zone] = dev
				self.addToStatesUpdateList(dev, key='zoneNumber', value=zone)
		elif dev.deviceTypeId == 'partition':
			partition = int(dev.pluginProps['address'])
			if partition not in self.partitionList.keys():
				self.partitionList[partition] = dev
				self.addToStatesUpdateList(dev, key='partitionNumber', value=partition)
		elif dev.deviceTypeId == 'user':
			user = int(dev.pluginProps['address'])
			if user not in self.userList.keys():
				self.userList[user] = dev
				self.addToStatesUpdateList(dev, key='userNumber', value=user)
		elif dev.deviceTypeId == 'keypad':
			keypad = int(dev.pluginProps['address'])
			if keypad not in self.keypadList.keys():
				self.keypadList[keypad] = dev
				self.addToStatesUpdateList(dev, key='keypadNumber', value=keypad)
		elif dev.deviceTypeId == 'panel':
			panel = int(self.systemId)
			if panel not in self.panelList.keys():
				self.panelList[panel] = dev
				self.addToStatesUpdateList(dev, key='panelNumber', value=panel)
		elif dev.deviceTypeId == 'statusInfo':
			system = int(self.systemId)
			if system not in self.systemStatusList.keys():
				self.systemStatusList[system] = dev
				self.addToStatesUpdateList(dev, key='systemNumber', value=system)
		self.executeUpdateStatesList()

	def deviceStop(self, dev):
		self.plugin.debugLog("deviceStop:        stopping device %s." % dev.name)
		
		if dev.deviceTypeId == 'zone':
			zone = int(dev.pluginProps['address'])
			if zone in self.zoneList.keys():
				del self.zoneList[zone]
		elif dev.deviceTypeId == 'partition':
			partition = int(dev.pluginProps['address'])
			if partition in self.partitionList.keys():
				del self.partitionList[partition]
		elif dev.deviceTypeId == 'user':
			user = int(dev.pluginProps['address'])
			if user in self.userList.keys():
				del self.userList[user]
		elif dev.deviceTypeId == 'keypad':
			keypad = int(dev.pluginProps['address'])
			if keypad in self.keypadList.keys():
				del self.keypadList[keypad]		
		elif dev.deviceTypeId == 'panel':
			panel = int(self.systemId)
			if panel in self.panelList.keys():
				del self.panelList[panel]
		elif dev.deviceTypeId == 'statusInfo':
			system = int(self.systemId)
			if system in self.systemStatusList.keys():
				del self.systemStatusList[system]
		# Todo: Since no states were changed, this seems superfluous.
		self.executeUpdateStatesList()

	########################################
	# Communication Start and Stop methods
	#######################################
	
	def startComm(self) -> None:
		"""
		Activates activeCommLoop()

		:return: None.  Does not return until activeCommLoop() returns.
		"""
		self.plugin.debugLog("startComm:        entering process")
		
		devicePort = self.plugin.devicePort
		baudRate = int(self.plugin.pluginPrefs['serialBaudRate'])
		serialTimeout = 3  # Hard coded to 3 seconds to reflect worst-case panel processing time for a command.
		
		self.devicePort = devicePort
		indigo.server.log("initialing connection to Caddx NetworX security devices . . .")
		
		# open serial communication port
		conn = self.plugin.openSerial("Caddx Security System", devicePort, baudRate, timeout=serialTimeout, writeTimeout=1)
		if conn:
			self.commStatusUp()
			indigo.server.log(
				f"Connection initialised to Caddx NetworX Security Panel on {devicePort} - Bit Rate: {baudRate} bps, Timeout: {serialTimeout} seconds.")
			self.conn = conn
			self.plugin.debugLog(f"startComm: connection: {devicePort}")
			self.activeCommLoop(devicePort, conn, self.commandQueue)
		else:
			self.plugin.errorLog(f"startComm: connection failure to Caddx NetworX Security device on {devicePort}")

	def stopComm(self) -> None:
		"""
		Sends termination command to activeCommLoop.  Shuts down all panel message handling.
		:return: None
		"""
		self.plugin.debugLog("stopComm:        entering process")
		self.plugin.debugLog("stopComm:        initiating stop looping communication to device %s" % self.devicePort)
		self.commStatusDown()
		
		while not self.commandQueue.empty():
			command = self.commandQueue.get()
			self.plugin.debugLog("stopComm:        command Queue contains: %s" % command)
		self.commandQueue.put("stopSerialCommunication")
		while not self.commandQueue.empty():
			try:
				self.commandQueue.get(False)
			except queue.Empty:
				continue
			self.commandQueue.task_done()

	def activeCommLoop(self, devicePort: str, conn, commandQueue: queue) -> None:
		"""
		Primary worker loop for handling events and commands

		:param devicePort: Serial device string.  Used only for logging.
		:param conn: The pyserial connection object.  Used for all I/O operations on comm port
		:param commandQueue: The queue used to contain commands for execution.
		:return: None
		"""
		try:
			indigo.server.log("Starting Caddx security device communications loop.")

			# allow interface configuration print to log for the first initialise
			self.suspendInterfaceConfigMessageDisplay = False
			self.flushCommPort(conn)

			# Start things rolling.
			self.actionSystemStatusRequest("")
			self.sendMsgToQueue(cmdInterfaceConfigurationRequest)

			# Start active serial communication loop
			# Todo: Exit activeCommLoop() using boolean rather than exception.
			while True:
				# trigger to periodically poll data and keep alive
				self.commContinuityCheck()

				# These messages are usually async events from panel.  Request/response handled below.
				receivedMessageDict = self.readMsg(conn, waitForResponse=False)
				if receivedMessageDict:
					self.decodeReceivedData(receivedMessageDict, 0)

				while not commandQueue.empty():
					lenQueue = commandQueue.qsize()
					self.plugin.debugLog("activeCommLoop:        || queue has %s command(s) waiting." % str(lenQueue))
					command = str(commandQueue.get())

					if command == "stopSerialCommunication":
						indigo.server.log("raising exception 'CaddxShutdown' to stop communication with panel.")
						raise CaddxShutdown
							
					self.plugin.debugLog("activeCommLoop:        || processing command: %s" % command)		
					if not self.processMessageFromQueue(conn, command):
						self.plugin.errorLog("activeCommLoop: Message send failed.  Retrying")
						continue
					self.plugin.debugLog("activeCommLoop:        || command completed: %s" % command)
					self.commandQueue.task_done()

				time.sleep(self.plugin.sleepBetweenIdlePoll)

		except CaddxShutdown:
			indigo.server.log("closing connection to conn device %s (shutdown process)." % devicePort)

		finally:
			indigo.server.log("closed connection to conn device %s (finally)." % devicePort)
			conn.close()	
			pass
		self.executeUpdateStatesList()

	def compute_fletcher16(self, data: bytearray) -> int:
		"""
		Returns the Fletcher16 checksum value in integer format.
		Eight-bit implementation.

		:param data: The data message to be checksummed.
		:return: 16-bit checksum.
		"""

		sum1, sum2 = int(), int()
		for index in range(len(data)):
			sum1 = (sum1 + data[index]) % 255
			sum2 = (sum2 + sum1) % 255
		return (sum2 << 8) | sum1

	def sendMsgToQueue(self, transmitDataHex: str) -> None:
		"""
		Add new command to queue, which is polled and emptied by activeCommLoop() and passed to processMessageFromQueue()

		:param transmitDataHex: The command message in hex-encoded ASCII.
		:return: None.
		"""
		messageNumber = transmitDataHex[2:4]
		alarmMessage = self.messageAlarmDict(messageNumber)
		if self.plugin.messageActInfo or self.plugin.debug:
			indigo.server.log("sendCmdToQueue:          || queue send message: %s  " % str(transmitDataHex))
		self.commandQueue.put(transmitDataHex)

		partition = 1  # update partition device state - lastFunction with the last transmitted message
		if partition in self.partitionList.keys():
			dev = self.partitionList[partition]
			self.addToStatesUpdateList(dev, key="lastFunction", value=f"{alarmMessage}  >> {messageNumber}  ** {self.timestamp()} ")
		self.updateVariable("sendingMessage", f" >> {messageNumber} --  {alarmMessage}     {transmitDataHex} ")

	def processMessageFromQueue(self, conn, transmitDataHex: str) -> bool:
		"""Send a message in binary format. Wait for reply if necessary.

		:param conn: Handle for serial port.
		:param transmitDataHex: Hex-formatted message.
		:return: True if message sent and reply received.  False otherwise.
		"""
		self.sendMsg(transmitDataHex)
		# Todo:  Extract message type so we can check for correct reply.
		return self.waitForResponse(conn, 0)

	#######################################
	# Check to see if serial port has any incoming information.
	#######################################
	
	def readMsg(self, conn, waitForResponse: bool) -> None | list[str]:
		"""
		Read complete message from serial port.
		**Note**:  Serial port timeout should be set to 3 seconds to reflect worst-case processing time.

		:param conn: pySerial object.
		:param waitForResponse: If True, wait up to port timeout until message received,
			otherwise return immediately if no message.
		:return: None if no message.   Valid message list object otherwise.
		"""
		if not waitForResponse and conn.in_waiting == 0:
			return None

		startCharacter = conn.read()
		if not len(startCharacter):
			self.plugin.errorLog("readMsg: No data when reply was expected.  Probably timeout.")
			return None
		if startCharacter != b'\x7e':
			self.plugin.errorLog("readMsg: Message buffer out of sync.  Missing start character.  Flushing and discarding.")
			self.flushCommPort(conn)
			return None
		msgLengthByte = conn.read()
		if not msgLengthByte:
			self.plugin.errorLog("readMsg: Missing length.  Flushing and discarding.")
			self.flushCommPort(conn)
			return None
		msgData = bytearray()
		msgData.extend(msgLengthByte)
		msgLength = int.from_bytes(msgLengthByte, "little")
		msgLengthFull = msgLength + 3   # Full message length includes length byte and 2 byte checksum
		for i in range(msgLength + 2):  # Message checksum included.  Already read length.
			nextChar = conn.read()
			if nextChar == b'\x7d':
				nextChar = conn.read()
				if nextChar == b'\x5e':
					self.plugin.debugLog("readMsg: Escape sequence 0x7d5e")
					nextChar = b'\x7e'
				elif nextChar == b'\x5d':
					self.plugin.debugLog("readMsg: Escape sequence 0x7d5d")
					nextChar = b'\x7d'
				else:
					self.plugin.errorLog("readMsg: Bad byte stuffing. Flushing and discarding.")
					self.flushCommPort(conn)
					return None
			msgData.extend(nextChar)
		if len(msgData) != msgLengthFull:  # The actual data plus the length byte and 2 byte checksum.
			self.plugin.errorLog(f"readMsg: Message data wrong length ({len(msgData)} != {msgLengthFull}). Flushing and discarding.")
			self.flushCommPort(conn)
			return None

		offeredChecksum = int.from_bytes(msgData[-2:], byteorder="little")
		del msgData[-2:]
		computedChecksum = self.compute_fletcher16(msgData)
		if offeredChecksum != computedChecksum:
			self.plugin.errorLog("readMsg: Checksum failed.  Discarding.")
			return None

		# Convert to the ASCII message list used by upstream parsing.
		messageList = []
		for i in msgData:
			messageList.append(f"{i:02x}")
		return messageList

	def flushCommPort(self, conn) -> None:
		"""
		Flush any data in comm port buffer.

		:param conn: pySerial object.  Used for all serial I/O
		:return: None
		"""
		while len(conn.read(100)):
			self.plugin.debugLog("flushCommPort: throwing away data.")
		conn.reset_input_buffer()

	def waitForResponse(self, conn, requestMessageType: int) -> bool:
		"""
		Wait for reply to sent queued command.

		:param conn: pySerial object.  Used for all serial I/O
		:param requestMessageType: Command/message type of original message.  Used to determine correct reply.
		:return: True if correct reply received.  False otherwise.
		"""
		# Todo: Return appropriate response status
		result = True
		for i in range(5):
			responseMessage = self.readMsg(conn, waitForResponse=True)
			if responseMessage:
				self.decodeReceivedData(responseMessage, requestMessageType)
				break
			else:
				time.sleep(self.plugin.sleepBetweenIdlePoll)
		return result

	def sendMsg(self, transmitDataHex: str) -> None:
		"""
		Send binary message to panel with byte stuffing and checksum.

		:param transmitDataHex: Hex-encoded message
		:return: None
		"""

		transmitMessage = bytearray.fromhex(transmitDataHex)
		checksum = self.compute_fletcher16(transmitMessage)
		transmitMessage.extend(checksum.to_bytes(2, byteorder="little"))
		transmitMessageStuffed = bytearray()
		for i in transmitMessage:
			if i == '0x7e':
				transmitMessageStuffed.extend(b"\x7d\x5e")
			elif i == '0x7d':
				transmitMessageStuffed.extend(b"\x7d\x5d")
			else:
				transmitMessageStuffed.append(i)
		transmitMessageStuffed[0:0] = b'\x7e'
		self.conn.write(transmitMessageStuffed)
		messageNumber = transmitDataHex[2:4]
		alarmMessage = self.messageAlarmDict(messageNumber)
		self.plugin.debugLog("sendMsg:           >> sent message: %s,  %s,  %r" % (messageNumber, alarmMessage, transmitMessage))

	def timestamp(self) -> str:
		"""
		Create a friendly-formatted current timestamp for event logging and device status event updates.
		
		:return: Timestamp string.
		"""
		timeLogged = time.localtime(time.time())
		timeLogEvent = "%r/%r/%r   %02d:%02d:%02d" % (
			timeLogged.tm_mon, timeLogged.tm_mday, timeLogged.tm_year, timeLogged.tm_hour, timeLogged.tm_min,
			timeLogged.tm_sec)
		return timeLogEvent

	################################################################################
	# Routines for Keypad Display Processing methods (decode partition snapshot status for LCD messages)
	###############################################################################

	# noinspection PyUnusedLocal
	def updateAlarmDisplay(self, varList, newByte) -> None:
		"""
		Update Alarm Display from received "Partition Snapshot Message" method

		:param varList: ???
		:param newByte: ???
		:return: None
		"""
		partition = 1								# assumes control keypad is always in partition 1
		if partition in self.partitionList.keys():
			dev = self.partitionList[partition]
			
			partition1 = newByte[0]
			self.plugin.debugLog("updateAlarmDisplay:        display message byte: %s" % partition1)
			timestamp = self.timestamp()
			partitionState = 0
							
			# display lists
			displayLCDLine1List = [
				'Unknown', 'System Ready', 'System Not Ready', 'System Arming ...', 'Alarm Intruder',
				'System Armed', 'Type code to', 'Alarm Intruder', 'System Arming ...',
				'Alarm Intruder ', 'System Armed', 'Type code to', 'Alarm Intruder'
			]
			displayLCDLine2List = [
				'Unknown', 'Type code to arm', 'For help, press ->', 'Zone(s) Bypassed', '       ',
				'Zone(s) Bypassed', 'Disarm', '        ', 'All Zones Secure', '        ',
				'Away Mode', 'Disarm', '        ']
		
			# display conditions
			displayLCDLine1 = " "
			displayLCDLine2 = " "
		
			# analyze partition state conditions for Common Mode  (Chime Mode Off)
			if partition1 == '00000011':  												# Disarmed, System Ready, Chime Off
				partitionState = 1
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]
				self.breachedZone = " "													# Reset breached zone on disarm cycle		
			elif partition1 == '00000001':												# Disarmed, System Not Ready, Chime Off
				partitionState = 2
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]			
			
			# analyze partition state conditions for Stay Mode
			elif partition1 == '01001111':												# Arming Stay Mode, System Ready, Chime Off
				partitionState = 3
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]		
			elif partition1 == '11001111':												# Arming Stay Mode (exit delay timed), Security Alert Parameter, Chime Off
				partitionState = 4
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = self.breachedZone		
			elif partition1 == '00001111':												# Armed Stay Mode , System Secure, Chime Off
				partitionState = 5
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]	
			elif partition1 == '00101101' or partition1 == '00101111':					# Armed Stay Mode (entry delay timed), Security Alert (entry zone), Chime Off
				partitionState = 6
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]	
			elif partition1 == '10001111':												# Armed Stay Mode , Security Alert Parameter, Chime Off
				partitionState = 7
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = self.breachedZone	
			
			# analyze partition state conditions for Away Mode
			elif partition1 == '01000111':												# Arming Away Mode , System Ready, Chime Off
				partitionState = 8
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]
			elif partition1 == '11000101' or partition1 == '11000111':					# Arming Away Mode (exit delay timed), Security Alert Parameter, Chime Off
				partitionState = 9
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = self.breachedZone
			elif partition1 == '00000111':												# Armed Away Mode, System Secure, Chime Off
				partitionState = 10
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]
			elif partition1 == '00100101' or partition1 == '00100111':				# Armed Away Mode (entry delay timed), Security Alert (entry zone), Chime Off
				partitionState = 11
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]
			elif partition1 == '10000101' or partition1 == '10000111':				# Armed Away Mode , Security Alert Parameter, Chime Off
				partitionState = 12	
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = self.breachedZone
			
			# analyze partition state conditions for Common Mode  (Chime Mode On)
			elif partition1 == '00010011':  											# Disarmed, System Ready, Chime Off
				partitionState = 1
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]
				self.breachedZone = " "													# Reset breached zone on disarm cycle
			elif partition1 == '00010001':												# Disarmed, System Not Ready, Chime On
				partitionState = 2
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]
			
			# analyze partition state conditions for Stay Mode
			elif partition1 == '01011111':												# Arming Stay Mode, System Ready, Chime On
				partitionState = 3
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]
			elif partition1 == '11011111':												# Arming Stay Mode (exit delay timed), Security Alert Parameter, Chime On
				partitionState = 4
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = self.breachedZone
			elif partition1 == '00011111':												# Armed Stay Mode , System Secure, Chime On
				partitionState = 5
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]
			elif partition1 == '00111101' or partition1 == '00111111':					# Armed Stay Mode (entry delay timed), Security Alert (entry zone), Chime On
				partitionState = 6
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]
			elif partition1 == '10011111':												# Armed Stay Mode , Security Alert Parameter, Chime On
				partitionState = 7
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = self.breachedZone
			
			# analyze partition state conditions for Away Mode
			elif partition1 == '01010111':												# Arming Away Mode , System Ready, Chime On
				partitionState = 8
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]
			elif partition1 == '11010101' or partition1 == '11010111':					# Arming Away Mode (exit delay timed), Security Alert Parameter, Chime On
				partitionState = 9
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = self.breachedZone
			elif partition1 == '00010111':												# Armed Away Mode, System Secure, Chime On
				partitionState = 10
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]
			elif partition1 == '00110101' or partition1 == '00110111':					# Armed Away Mode (entry delay timed), Security Alert (entry zone), Chime On
				partitionState = 11
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]
			elif partition1 == '10010101' or partition1 == '10010111':					# Armed Away Mode , Security Alert Parameter, Chime On
				partitionState = 12
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = self.breachedZone
				
			# update Partition State variables
			partitionStateList = [
				'Multiple State Changes', 'Disarmed', 'Not Ready', 'Arming (exit)', 'Arming Not Ready', 'Armed Stay',
				'Alarm (entry)', 'ALARM Intruder', 'Arming (exit)', 'ALARM Intruder', 'Armed Away',  'Alarm (entry)',
				'ALARM Intruder'
			]
			partitionConditionList = [
				'multipleChanges', 'disarmed', 'notReady', 'armingExit', 'armingNotReady', 'armedStay', 'alarmEntry',
				'alarmIntruder', 'armingExit', 'alarmIntruder', 'armedAway',  'alarmEntry', 'alarmIntruder'
			]
			pstate = partitionStateList[partitionState]
			pcondition = partitionConditionList[partitionState]
			# localPropsCopy = dev.pluginProps
			if dev.states['delayExpirationWarning'] == "1":
				if self.plugin.enableSpeakPrompts:
					indigo.server.speak(sayExitDelayWarning)	
				if self.plugin.partitionActInfo or self.plugin.debug:
					indigo.server.log("partition 1:       \'Warning - exit delay expires in 10 sec!\' ")
			else:	
				# localPropsCopy["partitionState"] = pstate
				# localPropsCopy["lastStateChange"] = "Partition (1) %r  ** %s " % (pstate, self.timestamp())
				# dev.replacePluginPropsOnServer(localPropsCopy)
				self.addToStatesUpdateList(dev, key="partitionState", value=pstate)
				self.addToStatesUpdateList(dev, key="partitionStatus", value=pcondition)
				self.addToStatesUpdateList(dev, key="lastStateChange", value="Partition (1) %r  ** %s " % (pstate, self.timestamp()))
				if self.plugin.partitionActInfo or self.plugin.debug:
					indigo.server.log("partition 1:       '%s!' " % pstate)
			
			# update Display Messages for Keypad device
			keypad = int(dev.pluginProps['associatedKeypad'])
			if keypad in self.keypadList.keys():
				dev = self.keypadList[keypad]
				self.addToStatesUpdateList(dev, key="LCDMessageLine1", value=displayLCDLine1)
				self.addToStatesUpdateList(dev, key="LCDMessageLine2", value=displayLCDLine2)
				if self.plugin.partitionActInfo or self.plugin.debug:
					indigo.server.log('keypad %s:           LCD message line 1: "%s",  LCD message line 2: "%s"' % (keypad, displayLCDLine1, displayLCDLine2))
			
			# update indigo variable "partitionState"  from Display Conditions above
			variableID = "partitionState"
			partitionStateVariable = ("%s   ** %s " % (pstate, self.timestamp()))
			self.updateVariable(variableID, partitionStateVariable)		
				
	########################################
	# update Breached Zone for Alarm Display from received "Log Event Message" method 
	########################################
			
	def updateAlarmDisplayZoneBreached(self, partition, zoneBreached) -> None:
		"""
		Update breached zone for alarm display from received "Log Event Message" method

		:param partition: Partition associated with breached zone.
		:param zoneBreached: Zone number of breached zone.
		:return: None
		"""
		if partition in self.partitionList.keys():
			dev = self.partitionList[partition]
			keypad = int(dev.pluginProps['associatedKeypad'])
			if keypad in self.keypadList.keys():
				dev = self.keypadList[keypad]
				displayLCDLine1 = "Security Breach"
				displayLCDLine2 = zoneBreached
				self.addToStatesUpdateList(dev, key="LCDMessageLine1", value=displayLCDLine1)
				self.addToStatesUpdateList(dev, key="LCDMessageLine2", value=displayLCDLine2)
				if self.plugin.partitionActInfo or self.plugin.debug:
					indigo.server.log('keypad %d:           LCD message line 1: "%s",   LCD message line 2: "%s"' % (keypad, displayLCDLine1, displayLCDLine2))
			if self.plugin.enableSpeakPrompts:
				say = sayZoneTripped + zoneBreached
				indigo.server.speak(say)
			
	########################################
	# update Breached Zone Name for Alarm Display from device config ui "Zone Name" method
	########################################

	def updateZoneNameBreached(self, zone) -> str:
		"""
		Update breached zone name for alarm display from device config ui "Zone Name" method

		:param zone: Zone for which to get name.
		:return: Zone name.
		"""
		zoneDisplayName = ""		
		if zone in self.zoneList.keys():
			dev = self.zoneList[zone]
			localPropsCopy = dev.pluginProps
			zoneDisplayName = localPropsCopy['zoneDisplayName']
			if zoneDisplayName is None:
				zoneDisplayName = 'zone %r' % zone	
		return zoneDisplayName	
													
	################################################################################
	# Routines for Zone Group Type Processing methods (decode zone group type configuration and add zone description)
	################################################################################
	
	def zoneGroupType(self, zoneTypeDict: str) -> str:
		"""
		Determine the zone group type number.

		:param zoneTypeDict: ???
		:return: The zone group type in string format.
		"""
		if zoneTypeDict == '000000000001001111110100':
			zoneType = '01'
		elif zoneTypeDict == '000000100001001111000000':
			zoneType = '02'		
		elif zoneTypeDict == '000100000001101111110000':
			zoneType = '03'	
		elif zoneTypeDict == '000110000001001111110000':
			zoneType = '04'	
		elif zoneTypeDict == '010110000001001111110000':
			zoneType = '05'	
		elif zoneTypeDict == '000000000001101111110000':
			zoneType = '06'	
		elif zoneTypeDict == '000000100000000011000000':
			zoneType = '07'
		elif zoneTypeDict == '000000010000010111000100':
			zoneType = '08'	
		elif zoneTypeDict == '001000000001101111110000':
			zoneType = '09'	
		elif zoneTypeDict == '000010100001000011000000':
			zoneType = '10'		
		elif zoneTypeDict == '000001000000000000000000':
			zoneType = '11'		
		elif zoneTypeDict == '010110000001001111111000':
			zoneType = '12'	
		elif zoneTypeDict == '000000001001101111110000':
			zoneType = '13'
		elif zoneTypeDict == '000100000011101111110000':
			zoneType = '14'	
		elif zoneTypeDict == '010110000011001111110000':
			zoneType = '15'	
		elif zoneTypeDict == '000000000011101111110000':
			zoneType = '16'	
		elif zoneTypeDict == '000100000001101111110010':
			zoneType = '17'	
		elif zoneTypeDict == '010110000001001111110010':
			zoneType = '18'	
		elif zoneTypeDict == '000000000001101111110010':
			zoneType = '19'
		elif zoneTypeDict == '001000000001101111110010':
			zoneType = '20'	
		elif zoneTypeDict == '000010100001000111000000':
			zoneType = '21'		
		elif zoneTypeDict == '000010100001000111000000':
			zoneType = '22'	
		elif zoneTypeDict == '000010100001000111000000':
			zoneType = '23'
		elif zoneTypeDict == '000000010000010111000100':
			zoneType = '24'	
		elif zoneTypeDict == '100010100001100000000000':
			zoneType = '25'
		elif zoneTypeDict == '011010000001001111110000':
			zoneType = '26'	
		elif zoneTypeDict == '010110000101001111110000':
			zoneType = '27'		
		elif zoneTypeDict == '001000000101101111110000':
			zoneType = '28'	
		elif zoneTypeDict == '010110000001001111110000':
			zoneType = '29'
		elif zoneTypeDict == '000100000001101111110000':
			zoneType = '30'
		else:
			zoneType = 'no zone group match'	
		return zoneType

	def zoneGroupDescription(self, zoneTypeDict: str) -> str:
		"""
		Determine the zone group type description label

		:param zoneTypeDict: ???
		:return: The zone type description in string format.
		"""
		if zoneTypeDict == '000000000001001111110100':
			# zoneType = '01'
			zoneDescription = 'Day/Night Alarm'
		elif zoneTypeDict == '000000100001001111000000':
			# zoneType = '02'
			zoneDescription = 'Panic Alarm'	
		elif zoneTypeDict == '000100000001101111110000':
			# zoneType = '03'
			zoneDescription = 'Entry/Exit (delay1)'
		elif zoneTypeDict == '000110000001001111110000':
			# zoneType = '04'
			zoneDescription = 'Interior Alarm'	
		elif zoneTypeDict == '010110000001001111110000':
			# zoneType = '05'
			zoneDescription = 'Interior Alarm'
		elif zoneTypeDict == '000000000001101111110000':
			# zoneType = '06'
			zoneDescription = 'Perimeter Alarm'	
		elif zoneTypeDict == '000000100000000011000000':
			# zoneType = '07'
			zoneDescription = 'Silent Panic'	
		elif zoneTypeDict == '000000010000010111000100':
			# zoneType = '08'
			zoneDescription = 'Fire Alarm'	
		elif zoneTypeDict == '001000000001101111110000':
			# zoneType = '09'
			zoneDescription = 'Entry/Exit (delay2)'
		elif zoneTypeDict == '000010100001000011000000':
			# zoneType = '10'
			zoneDescription = 'Tamper Alarm'	
		elif zoneTypeDict == '000001000000000000000000':
			# zoneType = '11'
			zoneDescription = 'Arm/Disarm (momentary keyswitch)'	
		elif zoneTypeDict == '010110000001001111111000':
			# zoneType = '12'
			zoneDescription = 'Interior Alarm (cross zone)'	
		elif zoneTypeDict == '000000001001101111110000':
			# zoneType = '13'
			zoneDescription = 'Perimeter Alarm (entry guard)'
		elif zoneTypeDict == '000100000011101111110000':
			# zoneType = '14'
			zoneDescription = 'Entry/Exit (delay1, group bypass)'
		elif zoneTypeDict == '010110000011001111110000':
			# zoneType = '15'
			zoneDescription = 'Interior Alarm (group bypass)'	
		elif zoneTypeDict == '000000000011101111110000':
			# zoneType = '16'
			zoneDescription = 'Perimeter Alarm (group bypass)'	
		elif zoneTypeDict == '000100000001101111110010':
			# zoneType = '17'
			zoneDescription = 'Arm/Disarm (maintained keyswitch)'
		elif zoneTypeDict == '010110000001001111110010':
			# zoneType = '18'
			zoneDescription = 'Entry/Exit (delay1, force armable)'
		elif zoneTypeDict == '000000000001101111110010':
			# zoneType = '19'
			zoneDescription = 'Entry/Exit (delay2, force armable)'
		elif zoneTypeDict == '001000000001101111110010':
			# zoneType = '20'
			zoneDescription = 'Entry/Exit (delay2, chime enabled)'	
		elif zoneTypeDict == '000010100001000111000000':
			# zoneType = '21"'
			zoneDescription = 'Gas Detected or Low/High Temp'	
		elif zoneTypeDict == '000010100001000111000000':
			# zoneType = '22'
			zoneDescription = 'Freeze Alarm'	
		elif zoneTypeDict == '000010100001000111000000':
			# zoneType = '23'
			zoneDescription = 'Interior Alarm'
		elif zoneTypeDict == '000000010000010111000100':
			# zoneType = '24'
			zoneDescription = 'Perimeter Alarm'	
		elif zoneTypeDict == '100010100001100000000000':
			# zoneType = '25'
			zoneDescription = 'Interior Alarm'	
		elif zoneTypeDict == '011010000001001111110000':
			# zoneType = '26'
			zoneDescription = 'Burglary Alarm (supervised local)'
		elif zoneTypeDict == '010110000101001111110000':
			# zoneType = '27'
			zoneDescription = 'Perimeter Alarm (activity monitor)'		
		elif zoneTypeDict == '001000000101101111110000':
			# zoneType = '28'
			zoneDescription = 'Perimeter Alarm (request to exit)'
		elif zoneTypeDict == '010110000001001111110000':
			# zoneType = '29'
			zoneDescription = 'Interior Alarm (request access to entry)'	
		elif zoneTypeDict == '000100000001101111110000':
			# zoneType = '30'
			zoneDescription = 'Medical Alarm'
		else:
			zoneDescription = 'no zone group match'	
		return zoneDescription		
																							
	################################################################################
	# Routines for Zone State Update method  (update zoneState value condition from received "Zone Status Message")
	################################################################################
	
	def updateZoneStateCondition(self, dev, zoneNum, zoneCondition) -> None:
		"""
		Determine and update zoneState value condition

		:param dev: ???
		:param zoneNum: ???
		:param zoneCondition: ???
		:return: None
		"""
		
		# test if zoneDisplayName exists in pluginProps dictionary
		zone = f"{zoneNum:03}"
		if dev.pluginProps['zoneDisplayName']:
			zoneName = dev.pluginProps['zoneDisplayName']
		else:
			zoneName = "Zone " + zone
		# bitList = zoneCondition
				
		# test for condition of zoneState device state for Group Trigger Plugin
		if zoneCondition == '00000001':
			zoneState = "triggered"
		elif zoneCondition == '00000010':
			zoneState = "tampered"
		elif zoneCondition == '00000100':
			zoneState = "trouble"	
		elif zoneCondition == '00001000':
			zoneState = "bypassed"
		elif zoneCondition == '00010000':
			zoneState = "inhibited"
		elif zoneCondition == '00100000':
			zoneState = "lowBattery"
		elif zoneCondition == '01000000':
			zoneState = "supervisionLoss"
		elif zoneCondition == '00000000':
			zoneState = "normal"
		else:
			zoneState = "multipleChanges"

		# update zoneState device state
		self.addToStatesUpdateList(dev, key="zoneState", value=zoneState)
		if self.plugin.zoneActInfo or self.plugin.debug:
			indigo.server.log("zone %s:          '%s!' {%s }" % (zone, zoneState, zoneName))
		
		# update partition lastZoneTrigger device state and variable
		if zoneState == "triggered":
			partition = 1
			if partition in self.partitionList.keys():
				dev = self.partitionList[partition]
				self.addToStatesUpdateList(dev, key="lastZoneTrigger", value="Zone %s  ** %s " % (zone, self.timestamp()))
				self.updateVariable("lastZoneTrigger", f"Zone {zone}  ** {self.timestamp()} ")
		
	################################################################################
	# Routines for Communication Status Update methods (update comm status in plugin config preferences)
	################################################################################

	def commStatusUp(self) -> None:
		"""
		Set comm state to active.

		:return: None
		"""
		self.plugin.pluginPrefs['portStatus'] = "Port (opened)"
		self.plugin.pluginPrefs['communicationFailure'] = False	
		self.plugin.pluginPrefs['activeCommunication'] = True	
		self.plugin.pluginPrefs['panelStatus'] = f"Connected  ** {self.timestamp()}"
		self.updateVariable("portStatus", "Port (opened)")
		self.updateVariable("panelStatus", f"Connected  ** {self.timestamp()}")

		# Update partition status variables config ui and device state
		partition = 1
		if partition in self.partitionList.keys():
			dev = self.partitionList[partition]
			self.addToStatesUpdateList(dev, key="partitionState", value="Connected")
			self.addToStatesUpdateList(dev, key="securityState", value="Connected")
			self.addToStatesUpdateList(dev, key="lastStateChange", value=f"Partition 1  Connected  ** {self.timestamp()}")
			self.updateVariable("securityState", "Connected")
			self.updateVariable("lastStateChange", f"Partition 1  Connected  ** {self.timestamp()}")

	def commStatusDown(self) -> None:
		"""
		Set comm state to inactive.

		:return: None
		"""
		self.plugin.pluginPrefs['portStatus'] = 'Port(closed)'
		self.plugin.pluginPrefs['communicationFailure'] = True
		self.plugin.pluginPrefs['lastFailureTime'] = "Failed ** %s" % self.timestamp()	
		self.plugin.pluginPrefs['activeCommunication'] = False	
		self.plugin.pluginPrefs['panelStatus'] = "Disconnected  ** %s" % self.timestamp()
		self.plugin.pluginPrefs['synchronised'] = False
		self.updateVariable("portStatus", "Port (closed)")
		self.updateVariable("panelStatus", f"Disconnected  ** {self.timestamp()}")

		# update partition status variables config ui and device state
		partition = 1
		if partition in self.partitionList.keys():
			dev = self.partitionList[partition]
			self.addToStatesUpdateList(dev, key="partitionState", value="Disconnected")
			self.addToStatesUpdateList(dev, key="securityState", value="Disconnected")
			self.addToStatesUpdateList(dev, key="lastStateChange", value=f"Partition 1  Disconnected  ** {self.timestamp}")
			self.updateVariable("securityState", "Disconnected")
			self.updateVariable("lastStateChange", f"Partition 1  Disconnected  ** {self.timestamp()}")

	def commContinuityCheck(self) -> None:
		"""
		Periodic test with comm continuity check to security system.

		:return: None
		"""
		timeNow = time.time()
		if self.plugin.watchdogTimerPeriod > 0:								# test if watchdog timer disabled
			if not self.plugin.pluginPrefs['isSynchronising']:					# abort if Synchronising Database process running
				if timeNow >= self.watchdogTimer:								# test if watchdog timer expired
					if self.plugin.messageProcessInfo or self.plugin.debug:
						indigo.server.log("watchdog timer triggered:        Interface Configuration Message: %s" % timeNow)
					if self.plugin.pluginPrefs['firmware'] == '*****':			# test for communication failure, update plugin prefs
						self.plugin.pluginPrefs['portStatus'] = "Port (open failure)"
						self.plugin.pluginPrefs['communicationFailure'] = True
						self.plugin.pluginPrefs['lastFailureTime'] = "Failed ** %s" % self.timestamp()
						self.errorCountComm += 1								# if error , increment counter
						indigo.server.log("error: communication continuity test FAILURE to Caddx Security System, error count %s" % self.errorCountComm)
					self.watchdogTimer = timeNow + self.plugin.watchdogTimerPeriod  # reset watchdog timer
					self.plugin.pluginPrefs['firmware'] = '*****'				# reset firmware to test communication loop
					self.sendMsgToQueue(cmdInterfaceConfigurationRequest)	 # command action: Interface Configuration Request
					# Todo:  Getting a dump of all zones seems like overkill.  Really necessary?
					self.actionCmdMessage("", "Zone Status Request ALL")  # update status of zones in case we missed an event

			else:
				return
		else:
			return		

	################################################################################
	# Routines for Received Message Processing method (decode Received messages and call update process)
	################################################################################
	
	########################################
	# process received messages and call associated decode and update method
	########################################

	# noinspection PyUnusedLocal
	def decodeReceivedData(self, messageDict: list[str], reqMessageType: int) -> None:
		"""
		Process received messages and call associated decode and update method.

		:param messageDict: A hex-formatted message dictionary.
		:param reqMessageType: The type of message that triggered the received data.
		:return: None.  (TBD: bool)
		"""
		# Todo: validate received data was proper response for reqMessageType
		messageNumber = int(messageDict[1], 16)
		ackRequested = bool(messageNumber & 0x80)
		messageNumber = messageNumber & ~0xc0  # Use only bottom 6 bits.

		match messageNumber:
			case 0x01:											# Interface Configuration Message
				self._interfaceConfigurationMessage(messageDict)
			case 0x03:											# Zone Name Message
				self._zoneNameMessage(messageDict)
			case 0x04:											# Zone Status Message
				self._zoneStatusMessage(messageDict)
			case 0x05:											# Zone Snapshot Message
				self._zoneSnapshotMessage(messageDict)
			case 0x06:											# Partition Status Message
				self._partitionStatusMessage(messageDict)
			case 0x07:											# Partition Snapshot Message
				self._partitionSnapshotMessage(messageDict)
			case 0x08:											# System Status Message
				self._systemStatusMessage(messageDict)
			case 0x09:											# X-10 Message Received
				self._x10MessageReceived(messageDict)
			case 0x0a:											# Log Event Message
				self._logEventMessage(messageDict)
			case 0x0b:											# Keypad Message Received
				self._keypadMessageReceived(messageDict)
			case 0x10:											# Program Data Reply
				self._programDataReply(messageDict)
			case 0x12:											# User Information Reply
				self._userInformationReply(messageDict)
			case 0x1c:											# Command / Request Failed
				self.plugin.debugLog("decodeReceivedData: Got 'Command/Request Failed'")
				pass
			case 0x1d:											# Positive Acknowledge
				self.plugin.debugLog("decodeReceivedData: Got 'ACK'")
				pass
			case 0x1e:											# Negative Acknowledge
				self.plugin.debugLog("decodeReceivedData: Got 'NAK'")
				pass
			case 0x1f:											# Message Rejected
				self.plugin.debugLog("decodeReceivedData: Got 'Message Rejected'")
				pass
			case _:
				self.sendMsg(CAN)
				indigo.plugin.errorLog(f"decodeReceivedData: Invalid or not supported message type. Type: '{messageNumber:02x}'")
		if ackRequested:
			self.sendMsg(ACK)
		self.executeUpdateStatesList()

	########################################
	# process "Interface Configuration Message"
	########################################
	
	def _interfaceConfigurationMessage(self, dataDict: list[str]):
		# extract each ASCII word from the system status message
		kmessageLength = dataDict[0]
		kmessageNumber = dataDict[1]
		kalarmMessage = self.messageAlarmDict(kmessageNumber)							# convert message number to message description
		bmessageLength = int(kmessageLength, 16)										# convert message length from hex to dec
		
		panel = int(self.systemId)														# system panel type number for updating state values
		messageStart = 6																# start pointer for valid message data (exclude message length and message number)
				
		# verified message being processed notice
		if self.plugin.messageProcessInfo or self.plugin.debug:
			indigo.server.log("processing message:         %s,  system model: %s,  length: %r" % (kalarmMessage, self.model, bmessageLength))

		# convert hex to binary map
		dmessageLength = bmessageLength - 5
		binterfaceConfigurationMessageDict = self.convertByteDictToBinaryMap(messageStart, dmessageLength, dataDict)
		
		# convert hex to ascii
		# Fixme:  Added "global"  Was this the intent?
		global panelFirmware
		panelFirmware = chr(int(dataDict[2], 16)) + chr(int(dataDict[3], 16)) + chr(int(dataDict[4], 16)) + chr(int(dataDict[5], 16))

		# verify message word value and binary mapping
		self.plugin.debugLog("interfaceConfigurationMessage:        interface configuration message dictionary: %r" % dataDict)
		self.plugin.debugLog("interfaceConfigurationMessage:        interface configuration message bit map dictionary: %r" % binterfaceConfigurationMessageDict)
				
		# parameter byte definition lists
		transitionMessageFlags1List = [
			"partitionSnapshotMessage", "partitionStatusMessage", "zoneSnapshotMessage", "zoneStatusMessage",
			"zreservedBit3TransitionMessageFlags1", "zreservedBit2TransitionMessageFlags1",
			"interfaceConfigurationMessage", "zreservedBit0TransitionMessageFlags1"
		]
		transitionMessageFlags2List = [
			"zreservedBit7TransitionMessageFlags2", "zreservedBit6TransitionMessageFlags2",
			"zreservedBit5TransitionMessageFlags2", "zreservedBit4TransitionMessageFlags2", "keypadMessageReceived",
			"logEventReceived", "receivedX10Message", "systemStatusMessage"
		]
		requestCommandFlags1List = [
			"partitionSnapshotRequest", "partitionStatusRequest", "zoneSnapshotRequest", "zoneStatusRequest",
			"zoneNameRequest", "zreservedBit2RequestCommandFlags1", "interfaceConfigurationRequest",
			"zreservedBit0RequestCommandFlags1"
		]
		requestCommandFlags2List = [
			"zreservedBit7RequestCommandFlags2", "zreservedBit6RequestCommandFlags2",
			"zreservedBit5RequestCommandFlags2", "keypadTerminalModeRequest", "sendKeypadTextMessage",
			"logEventRequest", "sendX10Message", "systemStatusRequest"
		]
		requestCommandFlags3List = [
			"setUserAuthorisationCommandWithoutPin", "setUserAuthorisationCommandWithPin",
			"setUserCodeCommandWithoutPin", "setUserCodeCommandWithPin", "userInformationRequestWithoutPin",
			"userInformationRequestWithPin", "programDataCommand", "programDataRequest"
		]
		requestCommandFlags4List = [
			"zoneBypassToggle", "secondaryKeypadFunction", "primaryKeypadFunctionWithoutPin",
			"primaryKeypadFunctionWithPin", "setClockCalenderCommand", "storeCommunicationEventCommand",
			"zreservedBit1RequestCommandFlags4", "zreservedBit0RequestCommandFlags4"]
		
		# update Interface Configuration Status Plugin Preferences "Interface Configuration Message"
		if binterfaceConfigurationMessageDict is not None:
			self.plugin.pluginPrefs["firmware"] = panelFirmware
			self.updateInterfaceConfigPluginPrefs(transitionMessageFlags1List, binterfaceConfigurationMessageDict[0])
			self.updateInterfaceConfigPluginPrefs(transitionMessageFlags2List, binterfaceConfigurationMessageDict[1])
			self.updateInterfaceConfigPluginPrefs(requestCommandFlags1List, binterfaceConfigurationMessageDict[2])
			self.updateInterfaceConfigPluginPrefs(requestCommandFlags2List, binterfaceConfigurationMessageDict[3])
			self.updateInterfaceConfigPluginPrefs(requestCommandFlags3List, binterfaceConfigurationMessageDict[4])
			self.updateInterfaceConfigPluginPrefs(requestCommandFlags4List, binterfaceConfigurationMessageDict[5])
			if self.plugin.messageProcessInfo or self.plugin.debug:
				indigo.server.log("update interface configuration:        plugin preferences successfully updated with alarm panel interface configuration settings.")
			
			# copy "Transition Based Broadcast" message state values that are currently "enabled" to Indigo Log	
			if not self.suspendInterfaceConfigMessageDisplay:
				indigo.server.log("Caddx NetworX Security System:        System Model: %s        Firmware: %s " % (self.model, panelFirmware))
				indigo.server.log("")
				localPrefsCopy = self.plugin.pluginPrefs
				indigo.server.log("Transition Based Broadcast messages currently enabled: ")
				prefsInterfaceConfigList = [
					"interfaceConfigurationMessage", "zoneStatusMessage", "zoneSnapshotMessage",
					"partitionStatusMessage", "partitionSnapshotMessage",
					"systemStatusMessage", "receivedX10Message", "logEventReceived", "keypadMessageReceived"
				]
				# Display enabled broadcast messages.
				for item in prefsInterfaceConfigList:
					var = localPrefsCopy[item]
					if var == '1':
						indigo.server.log(f"  - {item}")

				# copy "Command / Request" message state values that are currently "enabled" to Indigo Log	
				indigo.server.log("")
				indigo.server.log("Command / Request messages currently enabled: ")
				prefsInterfaceConfigList = [
					"interfaceConfigurationRequest", "zoneNameRequest", "zoneStatusRequest", "zoneSnapshotRequest",
					"partitionStatusRequest", "partitionSnapshotRequest", "systemStatusRequest", "sendX10Message",
					"logEventRequest", "sendKeypadTextMessage", "keypadTerminalModeRequest", "programDataRequest",
					"programDataCommand", "userInformationRequestWithPin",
					"userInformationRequestWithoutPin", "setUserCodeCommandWithPin", "setUserCodeCommandWithoutPin",
					"setUserAuthorisationCommandWithPin",
					"setUserAuthorisationCommandWithoutPin", "storeCommunicationEventCommand",
					"setClockCalenderCommand", "primaryKeypadFunctionWithPin",
					"primaryKeypadFunctionWithoutPin", "secondaryKeypadFunction", "zoneBypassToggle"
				]
				# Display enabled commands.
				for item in prefsInterfaceConfigList:
					var = localPrefsCopy[item]
					if var == '1':
						indigo.server.log(f"  - {item}")
				self.suspendInterfaceConfigMessageDisplay = True
	
		# update Interface Configuration Status States from received "Interface Configuration Message"
		if binterfaceConfigurationMessageDict is not None:
			# Fixme:  The panel device was never created, so following if will always fail.  Intent?
			if panel in self.panelList.keys():
				dev = self.panelList[panel]
				self.addToStatesUpdateList(dev, key=u'firmware', value=panelFirmware)
				self.updateInterfaceConfigStates(dev, transitionMessageFlags1List, binterfaceConfigurationMessageDict[0])
				self.updateInterfaceConfigStates(dev, transitionMessageFlags2List, binterfaceConfigurationMessageDict[1])
				self.updateInterfaceConfigStates(dev, requestCommandFlags1List, binterfaceConfigurationMessageDict[2])
				self.updateInterfaceConfigStates(dev, requestCommandFlags2List, binterfaceConfigurationMessageDict[3])
				self.updateInterfaceConfigStates(dev, requestCommandFlags3List, binterfaceConfigurationMessageDict[4])
				self.updateInterfaceConfigStates(dev, requestCommandFlags4List, binterfaceConfigurationMessageDict[5])
				if self.plugin.messageProcessInfo or self.plugin.debug:
					indigo.server.log("update interface configuration:        device state records successfully updated with alarm panel interface configuration settings.")
			else:
				self.plugin.debugLog("update interface configuration:        no record in indigo database (device - state) for alarm panel interface configuration settings.")
		else:
			self.plugin.debugLog("update interface configuration:        no device state records in message dictionary for alarm panel interface configuration settings update.")
					
	########################################
	# process "Zone Name Message"
	########################################
	
	def _zoneNameMessage(self, dataDict: list[str]):
		kmessageNumber = dataDict[1]
		kalarmMessage = self.messageAlarmDict(kmessageNumber)							# convert message number to message description

		kzoneNumber = dataDict[2]
		dzoneNumber = int(kzoneNumber, 16) + 1 	# zone numbers start from 0 ie.(0 = zone 1)

		kzoneNameHex = ""
		for i in range(3, 19):
			kzoneNameHex += dataDict[i]
		displayName = bytes.fromhex(kzoneNameHex).decode("utf-8").rstrip()

		# kzoneName1 = dataDict[3] + dataDict[4] + dataDict[5] + dataDict[6] + dataDict[7] + dataDict[8] + dataDict[9] + dataDict[10]
		# kzoneName2 = dataDict[11] + dataDict[12] + dataDict[13] + dataDict[14] + dataDict[15] + dataDict[16] + dataDict[17] + dataDict[18]
		# kzoneName = kzoneName1 + kzoneName2

		# verified message being processed notice
		if self.plugin.messageProcessInfo or self.plugin.debug:
			indigo.server.log(f"processing message:         {kalarmMessage},  zone: {dzoneNumber},  {displayName}")
		
		# verify message word value and binary mapping
		self.plugin.debugLog("zoneNameMessage:        zone name message dictionary: %r" % dataDict)
		
		# update Device Zone configuration UI displayName
		zone = dzoneNumber
		if displayName is not None:
			if zone in self.zoneList.keys():
				dev = self.zoneList[zone]
				localPropsCopy = dev.pluginProps
				localPropsCopy["zoneDisplayName"] = displayName
				dev.replacePluginPropsOnServer(localPropsCopy)
				# self.addToStatesUpdateList(dev,key="zoneDisplayName", value=displayName)
				if self.plugin.messageProcessInfo or self.plugin.debug:
					indigo.server.log("update zone name:        device configuration ui and device state records successfully updated with zone: %r, '%s'" % (dzoneNumber, displayName))
			else:
				self.plugin.debugLog("update zone name:        no record in indigo database (device) for zone: %r" % dzoneNumber)
		else:
			self.plugin.debugLog("update zone name:        no device configuration ui records in message dictionary for zone name message update.")
		self.keypadDisplayName = displayName
			
	########################################
	# process "Zone Status Message"
	########################################
		
	def _zoneStatusMessage(self, dataDict: list[str]):
		# extract each ASCII word from the system status message
		kmessageLength = dataDict[0]
		kmessageNumber = dataDict[1]
		kalarmMessage = self.messageAlarmDict(kmessageNumber)							# convert message number to message description
		bmessageLength = int(kmessageLength, 16)							# convert message length from hex to dec
				
		kzoneNumber = dataDict[2]
		dzoneNumber = int(kzoneNumber, 16)									# convert zone number from hex to dec for indexing
		dzoneNumber = dzoneNumber + 1											# zone numbers start from 0 ie.(0 = zone 1)

		messageStart = 3
		
		# verified message being processed notice
		if self.plugin.messageProcessInfo or self.plugin.debug:
			indigo.server.log("processing message:         %s,  zone: %r,  length: %r" % (kalarmMessage, dzoneNumber, bmessageLength))
		
		# convert hex to binary map
		dmessageLength = int(kmessageLength, 16) - 2	 # valid data message length
		bzoneStatusMessageDict = self.convertByteDictToBinaryMap(messageStart, dmessageLength, dataDict)
		
		# verify message word value and binary mapping
		self.plugin.debugLog("zoneStatusMessage:        zone status message dictionary: %r" % dataDict)
		self.plugin.debugLog("zoneStatusMessage:        zone status message bit map dictionary: %r" % bzoneStatusMessageDict)
				
		# parameter byte definition lists
		partitionMaskList = [
			"partition8", "partition7", "partition6", "partition5", "partition4", "partition3",
			"partition2", "partition1"
		]
		typeFlag1List = [
			"localOnly", "interior", "entryExitDelay2", "entryExitDelay1", "follower", "keySwitch",
			"in24HourFormat", "fire"
		]
		typeFlag2List = [
			"entryGuard", "forceArmable", "groupBypassable", "bypassableType", "chime", "steadySiren",
			"yelpingSiren", "keypadSounder"
		]
		typeFlag3List = [
			"listenIn", "restorable", "swingerShutdown", "dialerDelay", "crossZone", "troubleZoneType",
			"doubleEOLTamper", "fastLoopResponse"
		]
		# noinspection PyUnusedLocal
		conditionFlag1List = [
			"zreservedbit7ConditionFlag1", "lossOfSupervision", "lowBattery", "inhibitedForceArmed",
			"bypassedCondition", "troubleCondition", "tampered", "faultedOrDelayedTrip"
		]
		# noinspection PyUnusedLocal
		conditionFlag2List = [
			"zreservedbit7ConditionFlag2", "zreservedbit6ConditionFlag2",
			"zreservedbit5ConditionFlag2", "zreservedbit4ConditionFlag2",
			"zreservedbit3ConditionFlag2", "zreservedbit2ConditionFlag2", "bypassMemory",
			"alarmMemoryCondition"
		]
			
		# update Device Zone Configuration UI values from received "Zone Status Message"
		zone = dzoneNumber
		if bzoneStatusMessageDict is not None:
			if zone in self.zoneList.keys():
				dev = self.zoneList[zone]
				localPropsCopy = dev.pluginProps
				self.updateZoneStatusConfigUi(localPropsCopy, partitionMaskList, bzoneStatusMessageDict[0])
				self.updateZoneStatusConfigUi(localPropsCopy, typeFlag1List, bzoneStatusMessageDict[1])
				self.updateZoneStatusConfigUi(localPropsCopy, typeFlag2List, bzoneStatusMessageDict[2])
				self.updateZoneStatusConfigUi(localPropsCopy, typeFlag3List, bzoneStatusMessageDict[3])

				# determine configured panel 'zone group type'
				zoneGroupTypeDict = bzoneStatusMessageDict[1] + bzoneStatusMessageDict[2] + bzoneStatusMessageDict[3]
				zoneGroupType = self.zoneGroupType(zoneGroupTypeDict)
				zoneGroupDescription = self.zoneGroupDescription(zoneGroupTypeDict)
				self.plugin.debugLog("zoneStatusMessage:        zone group type %r,  %s  dictionary: %r" % (zoneGroupType, zoneGroupDescription, zoneGroupTypeDict))

				# update zone configuration UI for zone group type and description
				localPropsCopy["zoneGroupType"] = zoneGroupType	
				localPropsCopy["zoneGroupDescription"] = zoneGroupDescription			
				dev.replacePluginPropsOnServer(localPropsCopy)

				# update zone device state for zone group type and description
				# self.addToStatesUpdateList(dev,key="zoneGroupType", value=zoneGroupType)
				# self.addToStatesUpdateList(dev,key="zoneGroupDescription", value=zoneGroupDescription)
				if self.plugin.messageProcessInfo or self.plugin.debug:
					indigo.server.log("update zone status:        device configuration ui records successfully updated with zone status message:  zone: %r" % dzoneNumber)	
			else:
				self.plugin.debugLog("update zone status:        no record in indigo database (device - config ui) for zone; %r." % dzoneNumber)
		else:
			self.plugin.debugLog("update zone status:        no device configuration ui records in message dictionary for zone status message update.")
			
		# update Zone Device states values from received "Zone Status Message"
		if bzoneStatusMessageDict is not None:
			if zone in self.zoneList.keys():
				dev = self.zoneList[zone]
				self.updateZoneStatus(dev, bzoneStatusMessageDict[4], bzoneStatusMessageDict[5])
				if self.plugin.messageProcessInfo or self.plugin.debug:
					indigo.server.log("update zone status:        device state records successfully updated with zone status message:  zone: %r" % dzoneNumber)
			else:
				self.plugin.debugLog("update zone status:        no record in indigo database (device - state) for zone: %r." % dzoneNumber)
		else:
			self.plugin.debugLog("update zone status:        no device state records in message dictionary for zone status message update.")	
			
		# update zoneState value condition from received "Zone Status Message"
		if bzoneStatusMessageDict is not None:
			zoneCondition = bzoneStatusMessageDict[4]
			if zone in self.zoneList.keys():
				dev = self.zoneList[zone]
				self.updateZoneStateCondition(dev, zone, zoneCondition)
				if self.plugin.messageProcessInfo or self.plugin.debug:
					indigo.server.log("update zone status:        zoneState device state value successfully updated with zone status message:  zone: %r" % dzoneNumber)
			else:
				self.plugin.debugLog("update zone status:        no record in indigo database (device - state 'zoneState') for zone: %r." % dzoneNumber)
		else:
			self.plugin.debugLog("update zone status:        no device state records in message dictionary for zone status message update.")	
				
	########################################
	# process "Zones Snapshot Message"
	########################################
	
	def _zoneSnapshotMessage(self, dataDict: list[str]):
		# extract each ASCII word from the system status message
		kmessageLength = dataDict[0]
		kmessageNumber = dataDict[1]
		kalarmMessage = self.messageAlarmDict(kmessageNumber)							# convert message number to message description
		# noinspection PyUnusedLocal
		bmessageLength = int(kmessageLength, 16)							# convert message length from hex to dec
			
		kzoneOffset = dataDict[2]
		bzoneOffset = int(kzoneOffset, 16)									# convert hex to binary map for zone blocks 1 - 16 + (offset, 16)
		
		messageStart = 3
		zoneGroups = {
			0: "zone 1 - zone 16", 1: "zone 17 - zone 32", 2: "zone 33 - zone 48", 3: "zone 49 - zone 64",
			4: "zone 65 - zone 80", 5: "zone 81 - zone 96",
			6: "zone 97 - zone 112", 7: "zone 113 - zone 128", 8: "zone 129 - zone 144", 9: "zone 145 - zone 160",
			10: "zone 161 - zone 176", 11: "zone 177 - zone 192"
		}
		
		# verified message being processed notice
		if self.plugin.messageProcessInfo or self.plugin.debug:
			indigo.server.log("processing message:         %s,  block address: %r,  group: %s" % (kalarmMessage, bzoneOffset, zoneGroups[bzoneOffset]))		
		
		# convert hex to binary map
		dmessageLength = int(kmessageLength, 16) - 2				# valid data message length
		bzoneSnapshotMessageDict = self.convertByteDictToBinaryMap(messageStart, dmessageLength, dataDict)
		
		# verify binary mapping 
		self.plugin.debugLog("zoneSnapshotMessage:        zone snapshot message dictionary: %r" % dataDict)
		self.plugin.debugLog("zoneSnapshotMessage:        zone snapshot message bit map dictionary: %r" % bzoneSnapshotMessageDict)
		
		# parameter byte definition lists
		# noinspection PyUnusedLocal
		zoneSnapshotList = ["alarmMemory", "trouble", "bypass", "triggered"]
		
		# update Zone Device states values from received "Zone Snapshot Message"
		"""
		dzoneOffset = int(kzoneOffset, 16)									# convert zone offset number from hex to dec for indexing
		if bzoneSnapshotMessageDict != None:
				self.updateZoneSnapshot(bzoneOffset, zoneSnapshotList, bzoneSnapshotMessageDict)
				if self.plugin.messageProcessInfo or self.plugin.debug:
					indigo.server.log("update zone snapshot:        device state records successfully updated with zone snapshot message: %s" % zoneGroups[bzoneOffset])
			else:
				self.plugin.debugLog("update zone snapshot:        no device state records in message dictionary for zone snapshot message update.")
		"""
		
	########################################
	# process "Partition Status Message"
	########################################
	
	def _partitionStatusMessage(self, dataDict: list[str]):
		# extract each ASCII word from the partition status message
		kmessageLength = dataDict[0]
		kmessageNumber = dataDict[1]
		kalarmMessage = self.messageAlarmDict(kmessageNumber)		# convert message number to message description
		messageLength = int(kmessageLength, 16)						# convert message length from hex to dec

		# convert zone number from hex to dec for indexing. partition numbers start from 0 i.e.(0 = partition 1)
		partition = int(dataDict[2], 16) + 1
		partitionLastUserNumber = int(dataDict[7], 16)

		# start pointer for valid message data (exclude message length and message number)
		messageStart = 3
		
		# verified message being processed notice	
		if self.plugin.messageProcessInfo or self.plugin.debug:
			indigo.server.log("processing message:          %s,  partition: %r,  length: %r" % (kalarmMessage, partition, messageLength))

		# convert hex to binary map
		dmessageLength = int(kmessageLength, 16) - 2					# valid data message length
		bpartitionStatusMessageDict = self.convertByteDictToBinaryMap(messageStart, dmessageLength, dataDict)
		
		# verify message word value and binary mapping 
		self.plugin.debugLog("partitionStatusMessage:        partition status message dictionary: %r" % dataDict)
		self.plugin.debugLog("partitionStatusMessage:        partition status message bit map dictionary: %r" % bpartitionStatusMessageDict)
		
		# parameter byte definition lists
		partitionConditionFlag1List = [
			"instant", "armedSystem", "reservedbit5ConditionFlag1", "tLMFaultMemory", "firePulsingBuzzer", "fire",
			"fireTrouble", "bypassCodeRequired"
		]
		partitionConditionFlag2List = [
			"cancelPending", "codeEntered", "cancelCommandEntered", "tamper", "alarmMemoryCondition", "steadySirenOn",
			"sirenOn", "previousAlarm"
		]
		partitionConditionFlag3List = [
			"exit2", "exit1", "delayExpirationWarning", "entry", "chimeModeOn", "entryGuardStayMode",
			"silentExitEnabled", "reservedbit0ConditionFlag3"
		]
		partitionConditionFlag4List = [
			"sensorLostSupervision", "sensorLowBattery", "autoHomeInhibited", "exitErrorTriggered",
			"reservedbit3ConditionFlag4", "recentClosingBeingTimed", "crossTiming", "ledExtinguish"
		]
		partitionConditionFlag5List = [
			"toneOnActivationTone", "errorBeepTripleBeep", "chimeOnSounding", "validPinAccepted", "readyToForceArm",
			"readyToArm", "forceArmTriggeredByAutoArm", "zoneBypass"
		]
		partitionConditionFlag6List = [
			"delayTripInProgressCommonZone", "keySwitchArmed", "cancelReportIsInTheStack", "alarmSendUsingPhoneNumber3",
			"alarmSendUsingPhoneNumber2", "alarmSendUsingPhoneNumber1", "openPeriod", "entry1"
		]
		
		# update Partition Device states values from received "Partition Status Message"
		if bpartitionStatusMessageDict is not None:
			if partition in self.partitionList.keys():
				dev = self.partitionList[partition]
				self.addToStatesUpdateList(dev, key="lastUserNumber", value=partitionLastUserNumber)
				self.updatePartitionStatus(dev, partitionConditionFlag1List, bpartitionStatusMessageDict[0])
				self.updatePartitionStatus(dev, partitionConditionFlag2List, bpartitionStatusMessageDict[1])
				self.updatePartitionStatus(dev, partitionConditionFlag3List, bpartitionStatusMessageDict[2])
				self.updatePartitionStatus(dev, partitionConditionFlag4List, bpartitionStatusMessageDict[3])
				self.updatePartitionStatus(dev, partitionConditionFlag5List, bpartitionStatusMessageDict[5])
				self.updatePartitionStatus(dev, partitionConditionFlag6List, bpartitionStatusMessageDict[6])
				if self.plugin.messageProcessInfo or self.plugin.debug:
					indigo.server.log("update partition status:        device state records successfully updated with partition status message:  partition: %r" % partition)
				
				# update Keypad Device states values from received "Partition Status Message"
				systemArmed = dev.states['armedSystem']
				systemReady = dev.states['readyToArm']
				fireAlert = dev.states['fire']
				acPowerOn = dev.states['reservedbit5ConditionFlag1']
				stayArmed = dev.states['entryGuardStayMode']
				chimeMode = dev.states['chimeModeOn']
				exitDelay = dev.states['exit1']
				bypassZone = dev.states['zoneBypass']
				# cancel = dev.states['cancelPending']
				keypad = int(dev.pluginProps['associatedKeypad'])
				if keypad in self.keypadList.keys():
					dev = self.keypadList[keypad]
					self.addToStatesUpdateList(dev, key='armedSystem', value=systemArmed)
					self.addToStatesUpdateList(dev, key='readyToArm', value=systemReady)
					self.addToStatesUpdateList(dev, key='fire', value=fireAlert)
					self.addToStatesUpdateList(dev, key='acPowerOn', value=acPowerOn)
					self.addToStatesUpdateList(dev, key='stayMode', value=stayArmed)
					self.addToStatesUpdateList(dev, key='chimeMode', value=chimeMode)
					self.addToStatesUpdateList(dev, key='exitDelay', value=exitDelay)
					self.addToStatesUpdateList(dev, key='zoneBypass', value=bypassZone)
					# self.addToStatesUpdateList(dev,key='cancelPending', value=cancelPending)
					if self.plugin.messageProcessInfo or self.plugin.debug:
						indigo.server.log("update keypad status:        device state records successfully updated with partition status message:  keypad: %r" % keypad)
			else:
				self.plugin.debugLog("update partition status:        no record in indigo database (device - state) for partition: %r." % partition)
		else:
			self.plugin.debugLog("update partition status:        no device state records in message dictionary for partition status message update.")
		
	########################################
	# process "Partitions Snapshot Message"
	########################################
	
	def _partitionSnapshotMessage(self, dataDict: list[str]):
		# extract each ASCII word from the partition status message
		kmessageLength = dataDict[0]
		kmessageNumber = dataDict[1]
		kalarmMessage = self.messageAlarmDict(kmessageNumber)							# convert message number to message description
		bmessageLength = int(kmessageLength, 16)										# convert message length from hex to dec
						
		messageStart = 2																# start pointer for valid message data (exclude message length and message number)
		
		# verified message being processed notice
		if self.plugin.messageProcessInfo or self.plugin.debug:
			indigo.server.log("processing message:         %s,  partition 1 - 8,  length: %r" % (kalarmMessage, bmessageLength))

		# convert hex to binary map for partitions 1 - 8
		dmessageLength = int(kmessageLength, 16) - 1				# valid data message length
		bpartitionSnapshotMessageDict = self.convertByteDictToBinaryMap(messageStart, dmessageLength, dataDict)
		
		# verify binary mapping 
		self.plugin.debugLog("partitionSnapshotMessage:        snapshot partition message dictionary: %r" % dataDict)
		self.plugin.debugLog("partitionSnapshotMessage:        snapshot partition message bit map dictionary: %r" % bpartitionSnapshotMessageDict)
		
		# parameter byte definition lists
		partitionSnapshotList = ["partitionPreviousAlarm", "anyExitDelay", "anyEntryDelay", "chimeMode", "stayArm", "exitArm", "securityReady", "validPartition"]
		
		# update Device Partition Configuration UI values from received "Partition Snapshot Message"
		"""
		if bpartitionSnapshotMessageDict != None:
			self.updatePartitionSnapshotConfigUi(partitionSnapshotList, bpartitionSnapshotMessageDict)
			if self.plugin.messageProcessInfo or self.plugin.debug:
				indigo.server.log("update partition snapshot . device configuration ui records  successfully updated for partition snapshot message: partition: all active partitions: ")
		else:
			self.plugin.debugLog("update partition snapshot . no device configuration ui records in message dictionary for partition status message update.")
		"""
							
		# update Device Partition State values from received "Partition Snapshot Message"
		if bpartitionSnapshotMessageDict is not None:
			self.updatePartitionSnapshot(partitionSnapshotList, bpartitionSnapshotMessageDict)
			if self.plugin.messageProcessInfo or self.plugin.debug:
				indigo.server.log("update partition snapshot:        device state records successfully updated with partition snapshot message: all active partitions: ")
		else:
			self.plugin.debugLog("update partition snapshot:        no device state records in message dictionary for partition snapshot message update.")
			
		# Update Alarm Display from received "Partition Snapshot Message"
		if bpartitionSnapshotMessageDict is not None:
			self.updateAlarmDisplay(partitionSnapshotList, bpartitionSnapshotMessageDict)	
		
	########################################
	# process "System Status Message"
	########################################
	
	def _systemStatusMessage(self, dataDict: list[str]):
		# extract each ASCII word from the system status message
		kmessageLength = dataDict[0]
		kmessageNumber = dataDict[1]
		ksystemNumber = dataDict[2]
		kalarmMessage = self.messageAlarmDict(kmessageNumber)							# convert message number to message description
		bmessageLength = int(kmessageLength, 16)							# convert message length from hex to dec
		systemPanelId = int(ksystemNumber, 16)						# convert system number from hex to dec
		
		model = {"0": 'None', "1": 'NX-4', "2": 'NX-6', "3": 'NX-8', "4": 'NX-8e', "10": 'NX-6v2', "12": 'NX-8v2'}

		systemPanelIdS = str(systemPanelId)
		if systemPanelIdS in model:
			self.model = model[systemPanelIdS]
		else:
			self.model = "Other"

		kpanelByte12 = dataDict[12]
		bpanelByte12 = int(kpanelByte12, 16)								# convert communicator stack pointer length from hex to dec
		
		system = int(self.systemId)														# system panel type number for updating state values
		messageStart = 3																# start pointer for valid message data (exclude message length and message number)
		
		# verified message being processed notice
		if self.plugin.messageProcessInfo or self.plugin.debug:
			indigo.server.log("processing message:         %s,  system model: %s,  length: %r" % (kalarmMessage, self.model, bmessageLength))
			
		# convert hex to binary map
		dmessageLength = int(kmessageLength, 16) - 2					# valid data message length
		bsystemStatusMessageDict = self.convertByteDictToBinaryMap(messageStart, dmessageLength, dataDict)

		# verify message word value and binary mapping
		self.plugin.debugLog("systemStatusMessage:        system status message dictionary: %r" % dataDict)
		self.plugin.debugLog("systemStatusMessage:        system status message bit map dictionary: %r" % bsystemStatusMessageDict)
		
		# parameter byte definition lists
		panelByte03List = [
			"twoWayLockout", "listenInActive", "usingBackupPhone", "dialerDelayInProgress", "downloadInProgress",
			"initialHandshakeReceived", "offHook", "lineSeizure"
		]
		panelByte04List = [
			"acFail", "lowBattery", "sirenTamper", "boxTamper", "fuseFault", "failToCommunicate", "phoneFault",
			"groundFault"
		]
		panelByte05List = [
			"zreservedbit7PanelByte5", "expanderBellFault", "auxiliaryCommChannelFailure", "expanderAuxOverCurrent",
			"expanderLossOffSupervision", "expanderLowBattery", "expanderACFailure", "expanderBoxTamper"
		]
		panelByte06List = [
			"busDeviceRequestedSniffMode", "busDeviceHasLineSeized", "globalSteadySiren", "globalSirenOn",
			"globalPulsingBuzzer", "pinRequiredForLocalDownload", "programmingTokenInUse", "enable6DigitPin"
		]
		panelByte07List = [
			"timingHighVoltageBatteryCharge", "linePowerDetected50Hz", "smokePowerReset",
			"fireAlarmVerificationBeingTimed", "groundFaultMemory", "lowBatteryMemory", "acPowerOn",
			"dynamicBatteryTest"
		]
		panelByte08List = [
			"timingACancelWindow", "controlShutdownMode", "testFixtureMode", "enrollRequested", "lossOfSystemTime",
			"walkTestMode", "powerUpDelayInProgress", "communicationSinceLastAutoTest"
		]
		panelByte09List = [
			"callBackInProgress", "zreservedbit6PanelByte9", "zreservedbit5PanelByte9", "zreservedbit4PanelByte9",
			"zreservedbit3PanelByte9", "zreservedbit2PanelByte9", "zreservedbit1PanelByte9", "zreservedbit0PanelByte9"
		]
		panelByte10List = [
			"listenInTrigger", "listenInRequested", "lastReadWasOffHook", "sniffing", "phoneLineMonitorEnabled",
			"housePhoneOffHook", "voltagePresentInterruptActive", "phoneLineFaulted"
		]
		panelByte11List = [
			"validPartition8", "validPartition7", "validPartition6", "validPartition5", "validPartition4",
			"validPartition3", "validPartition2", "validPartition1"
		]
		# noinspection PyUnusedLocal
		panelByte12List = ["communicatorStackPointer"]
		
		# update System Status Message Plugin Preferences "System Status Message"
		if bsystemStatusMessageDict is not None:
			self.plugin.pluginPrefs["communicatorStackPointer"] = bpanelByte12
			self.updateSystemStatusPluginPrefs(panelByte03List, bsystemStatusMessageDict[0])
			self.updateSystemStatusPluginPrefs(panelByte04List, bsystemStatusMessageDict[1])
			self.updateSystemStatusPluginPrefs(panelByte05List, bsystemStatusMessageDict[2])
			self.updateSystemStatusPluginPrefs(panelByte06List, bsystemStatusMessageDict[3])
			self.updateSystemStatusPluginPrefs(panelByte07List, bsystemStatusMessageDict[4])
			self.updateSystemStatusPluginPrefs(panelByte08List, bsystemStatusMessageDict[5])
			self.updateSystemStatusPluginPrefs(panelByte09List, bsystemStatusMessageDict[6])
			self.updateSystemStatusPluginPrefs(panelByte10List, bsystemStatusMessageDict[7])
			self.updateSystemStatusPluginPrefs(panelByte11List, bsystemStatusMessageDict[8])
			if self.plugin.messageProcessInfo or self.plugin.debug:
				indigo.server.log("update system status:        plugin preferences  successfully updated with alarm panel system status message information.")
		
		# update System Status States from received "System Status Message"
		if bsystemStatusMessageDict is not None:
			if system in self.systemStatusList.keys():
				dev = self.systemStatusList[system]
				self.addToStatesUpdateList(dev, key=u'systemNumber', value=systemPanelId)
				self.addToStatesUpdateList(dev, key=u'model', value=self.model)
				self.addToStatesUpdateList(dev, key=u'communicatorStackPointer', value=bpanelByte12)
				self.updateSystemStatus(dev, panelByte03List, bsystemStatusMessageDict[0])
				self.updateSystemStatus(dev, panelByte04List, bsystemStatusMessageDict[1])
				self.updateSystemStatus(dev, panelByte05List, bsystemStatusMessageDict[2])
				self.updateSystemStatus(dev, panelByte06List, bsystemStatusMessageDict[3])
				self.updateSystemStatus(dev, panelByte07List, bsystemStatusMessageDict[4])
				self.updateSystemStatus(dev, panelByte08List, bsystemStatusMessageDict[5])
				self.updateSystemStatus(dev, panelByte09List, bsystemStatusMessageDict[6])
				self.updateSystemStatus(dev, panelByte10List, bsystemStatusMessageDict[7])
				self.updateSystemStatus(dev, panelByte11List, bsystemStatusMessageDict[8])
				if self.plugin.messageProcessInfo or self.plugin.debug:
					indigo.server.log("update system status:        device state records  successfully updated with alarm panel system status message information.")
			else:
				self.plugin.debugLog("update system status:        no record in indigo database (device - state) for alarm panel system status message information.")
		else:
			self.plugin.debugLog("update system status:        no device state records in message dictionary for alarm panel system status message information update.")
	
	########################################
	# process "X10 Messages Received" (this method is not yet complete)
	########################################
	
	def _x10MessageReceived(self, dataDict: list[str]):
		# extract each ASCII word from the x-10 message received
		# noinspection PyUnusedLocal
		kmessageLength = dataDict[0]
		kmessageNumber = dataDict[1]
		khouseCode = dataDict[2]
		kunitCode = dataDict[3]
		kx10FunctionCode = dataDict[4]
		# noinspection PyUnusedLocal
		kalarmMessage = self.messageAlarmDict(kmessageNumber)
		
		# convert hex to binary map
		bhouseCode = int(khouseCode, 16)
		bunitCode = int(kunitCode, 16)
		bx10FunctionCode = int(kx10FunctionCode, 16)
		
		# verify binary mapping 
		self.plugin.debugLog("x10MessageReceived:        decode X-10 house code: %r" % bhouseCode)
		self.plugin.debugLog("x10MessageReceived:        decode X-10 unit code: %r" % bunitCode)
		self.plugin.debugLog("x10MessageReceived:        decode X-10 function code: %r" % bx10FunctionCode)
		
		# parameter byte definition lists
		# noinspection PyUnusedLocal
		x10FunctionCodeDict = {"\x68": "allLightsOff", "\x58": "bright", "\x48": "dim", "\x38": "off", "\x28": "on", "\x18": "allLightsOn", "\x08": "allUnitsOff"}
		
	########################################
	# process "Log Event Message"
	########################################
	
	def _logEventMessage(self, dataDict: list[str]):
		# extract each ASCII word from the log event message
		# noinspection PyUnusedLocal
		kmessageLength = dataDict[0]
		kmessageNumber = dataDict[1]
		kalarmMessage = self.messageAlarmDict(kmessageNumber)
						
		# convert hex to ascii map
		deventNum = int(dataDict[2], 16)								# specific sequence event number
		# noinspection PyUnusedLocal
		dtotalLogSize = int(dataDict[3], 16)							# total size of the event log queue
		deventType = int(dataDict[4], 16)								# event type number to translated to event scription
		dzoneUserDevice = int(dataDict[5], 16) + 1						# event effects zone (0 = zone 1), user (0 = user 1) or device reference
		dpartitionNumber = int(dataDict[6], 16) + 1   					# partition numbers start from 0 i.e.(0 = partition 1)
	
		timeStamp = time.asctime(time.localtime(time.time()))
		deventNumber = f"{deventNum:03}"
		dzoneUserDeviceNumber = f"{dzoneUserDevice:03}"

		# verified message being processed notice
		if self.plugin.messageProcessInfo or self.plugin.debug:
			indigo.server.log("processing message:         %s,  alarm event: %r,  %s" % (kalarmMessage, deventType, timeStamp))
		
		# use computer day/time clock for the Log Event timestamp
		timeLogEvent = self.timestamp()
	
		if deventType <= 127:
			# look up dictionary event number for description, byte 5 and byte 6 values
			eventDescription = self.messageLogEventDict(deventType)
			eventZoneUserDeviceValid = self.messageLogByte5Dict(deventType)
			eventPartitionNumberValid = self.messageLogByte6Dict(deventType)
		
			# conditional log event format statements
			if eventZoneUserDeviceValid == "zone" and eventPartitionNumberValid:
				zoneName = self.updateZoneNameBreached(dzoneUserDevice)
				logEventMessagePrint = "log event %s:      %s,  partition: %s  zone: %s  {%s}   ** %s" % (deventNumber, eventDescription, dpartitionNumber, dzoneUserDeviceNumber, zoneName, timeLogEvent)	
				# Keypad LCD Message for Zone Security Breach
				if deventType == 0:
					self.breachedZone = self.updateZoneNameBreached(dzoneUserDevice)
					self.updateAlarmDisplayZoneBreached(dpartitionNumber, self.breachedZone)	
			elif eventZoneUserDeviceValid == "none" and eventPartitionNumberValid:
				logEventMessagePrint = "log event %s:      %s,  partition: %s   ** %s" % (deventNumber, eventDescription, dpartitionNumber, timeLogEvent)
			elif eventZoneUserDeviceValid == "device" and not eventPartitionNumberValid:
				logEventMessagePrint = "log event %s:      %s,  device: %s   ** %s" % (deventNumber, eventDescription, dzoneUserDevice, timeLogEvent)
			elif eventZoneUserDeviceValid == "none" and not eventPartitionNumberValid:
				logEventMessagePrint = "log event %s:      %s,   ** %s" % (deventNumber, eventDescription, timeLogEvent)
			elif eventZoneUserDeviceValid == "user" and eventPartitionNumberValid:
				logEventMessagePrint = "log event %s:      %s,  partition: %s  user: %r   ** %s" % (deventNumber, eventDescription, dpartitionNumber, dzoneUserDevice, timeLogEvent)
			elif eventZoneUserDeviceValid == "user" and not eventPartitionNumberValid:
				logEventMessagePrint = "log event %s:      %s,  user: %s   ** %s" % (deventNumber, eventDescription, dzoneUserDevice, timeLogEvent)
			else:
				logEventMessagePrint = "log event %s:      Program error." % deventNumber
				
		# for special conditional log events not defined in the dictionary			
		else:
			if deventType == 138:
				eventDeviceDescription = self.messageLogDeviceAddressDict(dzoneUserDevice - 1)
				# noinspection PyUnusedLocal
				logEventMessagePrint = "log event %s:      Loss of Supervision (wireless): %s,  zone: %s,  partition: %s  ** %s" % (
					deventNumber, eventDeviceDescription, (dzoneUserDevice - 1), dpartitionNumber, timeLogEvent)
			if deventType == 139:
				eventDeviceDescription = self.messageLogDeviceAddressDict(dzoneUserDevice - 1)
				# noinspection PyUnusedLocal
				logEventMessagePrint = "log event %s:      Loss of Supervision RESTORED (wireless): %s,  zone: %s,  partition: %s  ** %s" % (
					deventNumber, eventDeviceDescription, (dzoneUserDevice - 1), dpartitionNumber, timeLogEvent)
			if deventType == 168:
				eventDeviceDescription = self.messageLogDeviceAddressDict(dzoneUserDevice - 1)
				logEventMessagePrint = "log event %s:      system DISARMED: %s,  address: %s,  partition: %s  ** %s" % (
					deventNumber, eventDeviceDescription, (dzoneUserDevice - 1), dpartitionNumber, timeLogEvent)
				if self.plugin.enableSpeakPrompts:
					indigo.server.speak(sayDisarmed)
			elif deventType == 169:
				eventDeviceDescription = self.messageLogDeviceAddressDict(dzoneUserDevice - 1)
				logEventMessagePrint = "log event %s:      system ARMED: %s,  address: %s,  partition: %s  ** %s" % (
					deventNumber, eventDeviceDescription, (dzoneUserDevice - 1), dpartitionNumber, timeLogEvent)
				if self.plugin.enableSpeakPrompts:
					indigo.server.speak(sayArmed)
			elif deventType == 173:
				eventDeviceDescription = self.messageLogDeviceAddressDict(dzoneUserDevice - 1)
				logEventMessagePrint = "log event %s:      entering program mode: %s,  address: %s,  partition: %s  ** %s" % (
					deventNumber, eventDeviceDescription, (dzoneUserDevice - 1), dpartitionNumber, timeLogEvent)
				# update enter keypad program mode states in plugin preferences
				self.plugin.pluginPrefs["isKeypadProgramming"] = True
				self.plugin.pluginPrefs["panelStatus"] = "Program Mode (enter)  ** %s " % self.timestamp()
				self.updateVariable("panelStatus", f"Program Mode (enter)  ** {self.timestamp()}")
			elif deventType == 174:
				eventDeviceDescription = self.messageLogDeviceAddressDict(dzoneUserDevice - 1)
				logEventMessagePrint = "log event %s:        exiting program mode: %s,  address: %s,  partition: %s  ** %s" % (
					deventNumber, eventDeviceDescription, (dzoneUserDevice - 1), dpartitionNumber, timeLogEvent)
				# update exit keypad program mode states in plugin preferences
				self.plugin.pluginPrefs["isKeypadProgramming"] = False
				self.plugin.pluginPrefs["panelStatus"] = "Program Mode (exit)  ** %s " % self.timestamp()
				self.updateVariable("panelStatus", f"Program Mode (exit)  ** {self.timestamp()}")
			elif deventType == 245:
				eventDeviceDescription = self.messageLogDeviceAddressDict(dzoneUserDevice - 1)
				logEventMessagePrint = "log event %s:      registering module: %s,  address: %s,  partition: %s  ** %s" % (
					deventNumber, eventDeviceDescription, (dzoneUserDevice - 1), dpartitionNumber, timeLogEvent)
			elif deventType == 247:
				logEventMessagePrint = "log event %s:      confirm alarm system time and date set: %s  ** %s" % (
					deventNumber, timeStamp, timeLogEvent)
			else:
				logEventMessagePrint = "log event %s:      alarm event: (%s)  is out of range of event dictionary definitions byte 5: (device address %s),  byte 6: (partition %s)  ** %s" % (
					deventNumber, deventType, (dzoneUserDevice - 1), dpartitionNumber, timeLogEvent)
				if self.plugin.alarmEventInfo or self.plugin.debug:
					indigo.server.log("log event %s:      data dictionary: %s " % (deventNumber, dataDict))

		# log event to indigo log history (last 25 entries)
		logEventHistoryList = [
			"zlogEventHistory01", "zlogEventHistory02", "zlogEventHistory03", "zlogEventHistory04",
			"zlogEventHistory05", "zlogEventHistory06", "zlogEventHistory07",
			"zlogEventHistory08", "zlogEventHistory09", "zlogEventHistory10", "zlogEventHistory11",
			"zlogEventHistory12", "zlogEventHistory13", "zlogEventHistory14",
			"zlogEventHistory15", "zlogEventHistory16", "zlogEventHistory17", "zlogEventHistory18",
			"zlogEventHistory19", "zlogEventHistory20", "zlogEventHistory21",
			"zlogEventHistory22", "zlogEventHistory23", "zlogEventHistory24", "zlogEventHistory25"
		]
		item = 0
		for i in range(0, 24):
			newVariable = logEventHistoryList[item] 
			oldVariable = logEventHistoryList[item + 1]
			self.plugin.pluginPrefs[newVariable] = self.plugin.pluginPrefs[oldVariable]
			item += 1
		self.plugin.pluginPrefs["zlogEventHistory25"] = logEventMessagePrint
			
		# update indigo eventLog variable		
		if self.plugin.alarmEventInfo or self.plugin.debug:
			indigo.server.log("%s" % logEventMessagePrint)
			self.updateVariable("eventLogMessage", logEventMessagePrint)
			
	########################################
	# process "Keypad Message Received"
	########################################
	
	def _keypadMessageReceived(self, dataDict: list[str]):
		# extract each ASCII word from the keypad message received
		# noinspection PyUnusedLocal
		kmessageLength = dataDict[0]
		kmessageNumber = dataDict[1]
		# noinspection PyUnusedLocal
		kalarmMessage = self.messageAlarmDict(kmessageNumber)
		
		kkeypadAddress = dataDict[2]
		kkeypadValue = dataDict[3]
		
		# parameter byte definition lists
		keypadValueDict = {
			"00": "0", "01": "1", "02": "2", "03": "3", "04": "4", "05": "5", "06": "6", "07": "7", "08": "8",
			"09": "9", "0a": "Stay", "0b": "Chime",
			"0c": "Exit", "0d": "Bypass", "0e": "Cancel", "0f": "Fire", "10": "Medical", "11": "Police", "12": "*",
			"13": "#", "14": "up", "15": "down",
			"80": "Auxiliary 1", "81": "Auxiliary 2"
		}
		# verify binary mapping 
		indigo.server.log("alarm keypad button pressed;  keypad: %r,  button: %s" % (kkeypadAddress, keypadValueDict[kkeypadValue]))
		
	########################################
	# process "Program Data Reply"	(this method is not yet complete)
	########################################
		
	def _programDataReply(self, dataDict: list[str]):
		# extract each ASCII word from the program data reply
		# noinspection PyUnusedLocal
		kmessageLength = dataDict[0]
		kmessageNumber = dataDict[1]
		kdeviceBusAddress = dataDict[2]
		kupperLogicalLocationOffset = dataDict[3]
		klowerLogicalLocationOffset = dataDict[4]
		klocationLengthDataType = dataDict[5]
		kdataTypeByte06 = dataDict[6]
		kdataTypeByte07 = dataDict[7]
		kdataTypeByte08 = dataDict[8]
		kdataTypeByte09 = dataDict[9]
		kdataTypeByte10 = dataDict[10]
		kdataTypeByte11 = dataDict[11]
		kdataTypeByte12 = dataDict[12]
		kdataTypeByte13 = dataDict[13]		
		# noinspection PyUnusedLocal
		kalarmMessage = self.messageAlarmDict(kmessageNumber)
		
		# convert hex to binary map
		bdeviceBusAddress = int(kdeviceBusAddress, 16)
		bupperLogicalLocationOffset = int(kupperLogicalLocationOffset, 16)
		blowerLogicalLocationOffset = int(klowerLogicalLocationOffset, 16)
		blocationLengthDataType = int(klocationLengthDataType, 16)
		bdataTypeByte06 = int(kdataTypeByte06, 16)
		bdataTypeByte07 = int(kdataTypeByte07, 16)
		bdataTypeByte08 = int(kdataTypeByte08, 16)
		bdataTypeByte09 = int(kdataTypeByte09, 16)
		bdataTypeByte10 = int(kdataTypeByte10, 16)
		bdataTypeByte11 = int(kdataTypeByte11, 16)
		bdataTypeByte12 = int(kdataTypeByte12, 16)
		bdataTypeByte13 = int(kdataTypeByte13, 16)
		
		# verify binary mapping 
		self.plugin.debugLog("programDataReply:        decode device bus address: %r" % bdeviceBusAddress)
		self.plugin.debugLog("programDataReply:        decode upper logical location offset: %r" % bupperLogicalLocationOffset)
		self.plugin.debugLog("programDataReply:        decode lower logical location offset: %r" % blowerLogicalLocationOffset)
		self.plugin.debugLog("programDataReply:        decode location length data type: %r" % blocationLengthDataType)
		self.plugin.debugLog("programDataReply:        decode data type byte 06: %r" % bdataTypeByte06)
		self.plugin.debugLog("programDataReply:        decode data type byte 07: %r" % bdataTypeByte07)
		self.plugin.debugLog("programDataReply:        decode data type byte 08: %r" % bdataTypeByte08)
		self.plugin.debugLog("programDataReply:        decode data type byte 09: %r" % bdataTypeByte09)
		self.plugin.debugLog("programDataReply:        decode data type byte 10: %r" % bdataTypeByte10)
		self.plugin.debugLog("programDataReply:        decode data type byte 11: %r" % bdataTypeByte11)
		self.plugin.debugLog("programDataReply:        decode data type byte 12: %r" % bdataTypeByte12)
		self.plugin.debugLog("programDataReply:        decode data type byte 13: %r" % bdataTypeByte13)
		
	########################################
	# process "User Information Reply"	
	########################################
	
	def _userInformationReply(self, dataDict: list[str]):
		# extract each ASCII word from the user information reply
		kmessageLength = dataDict[0]
		kmessageNumber = dataDict[1]
		kalarmMessage = self.messageAlarmDict(kmessageNumber)
		bmessageLength = int(kmessageLength, 16)
		
		kuserNumber = dataDict[2]
		buserNumber = int(kuserNumber, 16)
		user = buserNumber
		kpinDigit1and2 = dataDict[3]
		kpinDigit3and4 = dataDict[4]
		kpinDigit5and6 = dataDict[5]
		
		# format user code length correctly for 4 or 6 digits
		codeLength = float(self.plugin.pluginPrefs['codeLength'])
		if codeLength == 4:
			kuserPin = kpinDigit1and2[1] + kpinDigit1and2[0] + kpinDigit3and4[1] + kpinDigit3and4[0]
		elif codeLength == 6:
			kuserPin = kpinDigit1and2[1] + kpinDigit1and2[0] + kpinDigit3and4[1] + kpinDigit3and4[0] + kpinDigit5and6[1] + kpinDigit5and6[0]
		else:
			kuserPin = None
			indigo.server.log("Program error:  PIN code length defined incorrectly", level=logging.ERROR)
			
		messageStart = 3  # start pointer for valid message data (exclude message length and message number)
		
		# verified message being processed notice
		if self.plugin.messageProcessInfo or self.plugin.debug:
			indigo.server.log("processing message:         %s,  user: %r,  length: %r" % (kalarmMessage, buserNumber, bmessageLength))
			
		# convert hex to binary map
		dmessageLength = int(kmessageLength, 16) - 2					# valid data message length
		buserInformationReplyDict = self.convertByteDictToBinaryMap(messageStart, dmessageLength, dataDict)
		
		# verify binary mapping 
		self.plugin.debugLog("userInformationReply:        decode user PIN: %r" % kuserPin)
		self.plugin.debugLog("userInformationReply:        decode user information bit map dictionary: %r" % buserInformationReplyDict)
			
		# parameter byte definition lists
		authorityFlag1List = [
			"mustBe0", "openCloseReportEnabled", "bypassEnabled", "armDisarmEnabled", "masterProgram",
			"armOnlyDuringCloseWindow", "armOnly", "reservedbit0UserAuthorityFlag1"
		]
		# noinspection PyUnusedLocal
		authorityFlag2List = [
			"mustBe1", "openCloseReportEnabled", "bypassEnabled", "armDisarmEnabled", "output4Enable", "output3Enable",
			"output2Enable", "output1Enable"
		]
		userAuthorisedPartitionList = [
			"authorisedForPartition8", "authorisedForPartition7", "authorisedForPartition6", "authorisedForPartition5",
			"authorisedForPartition4", "authorisedForPartition3", "authorisedForPartition2", "authorisedForPartition1"
		]

		# update Device User Information Configuration UI values from received "User Information Reply"
		if buserInformationReplyDict is not None:
			if user in self.userList.keys():
				dev = self.userList[user]
				localPropsCopy = dev.pluginProps
				localPropsCopy["userPin"] = kuserPin
				self.updateUserInformationStatusConfigUi(localPropsCopy, authorityFlag1List, buserInformationReplyDict[3])
				self.updateUserInformationStatusConfigUi(localPropsCopy, userAuthorisedPartitionList, buserInformationReplyDict[4])
				dev.replacePluginPropsOnServer(localPropsCopy)
				if self.plugin.messageProcessInfo or self.plugin.debug:
					indigo.server.log("update user information:        device configuration ui records successfully updated for user information:  user: %r" % buserNumber)
			else:
				self.plugin.debugLog("update user information:        no record in indigo database (device - config ui) for user: %r." % buserNumber)
		else:
			self.plugin.debugLog("update user information:        no device configuration ui records in message dictionary for user information update.")
				
		# Update User Information Device states values from received "User Information Reply"
		if buserInformationReplyDict is not None:
			if user in self.userList.keys():
				dev = self.userList[user]
				self.addToStatesUpdateList(dev, key="userPin", value=kuserPin)
				self.updateUserInformationStatus(dev, authorityFlag1List, buserInformationReplyDict[3])
				self.updateUserInformationStatus(dev, userAuthorisedPartitionList, buserInformationReplyDict[4])
				if self.plugin.messageProcessInfo or self.plugin.debug:
					indigo.server.log("update user information:        device state records  successfully updated for user information:  user: %r" % buserNumber)
			else:
				self.plugin.debugLog("update user information:        no record in indigo database (device - state) for user: %r." % buserNumber)
		else:
			self.plugin.debugLog("update user information:        no device state records in message dictionary for user information update.")
				
	################################################################################
	# Routines to Support Message Processing methods data conversion methods to support message processing
	################################################################################

	########################################
	# convert valid message Bytes to Bit map dictionary	
	########################################
	
	def convertByteDictToBinaryMap(self, msgStart: int, msgLength: int, messageDict: list[str]) -> list[str] | None:
		if msgLength <= len(messageDict):
			bitmapDict = []
			for i in range(msgStart, (msgStart + msgLength)):
				bitmapDict.append(f"{int(messageDict[i], 16):08b}")
			return bitmapDict
		else:
			self.plugin.debugLog("convertByteDictToBinaryMap:        error in message format,  message byte length: %r,  nibbles: %r" % (msgLength, len(messageDict)))
			return None

	################################################################################
	# Routines for updating Indigo Database States methods update indigo plugin preferences, device configuration ui and device states	
	################################################################################
	# update indigo plugin preferences, device configuration ui and device states
	
	########################################
	# updates indigo variable instance var with new value varValue
	########################################
	
	def updateVariable(self, varName, varValue):
		# indigo.server.log("updateVariable(): -- variable  %s: value  %r: " % (varName,varValue))
		# Todo:  I re-factored this a bit.  Review.
		if self.plugin.pluginPrefs['variableFolderName'] not in indigo.variables.folders:
			caddxVariablesFolder = indigo.variables.folder.create(self.plugin.pluginPrefs['variableFolderName'])
		else:
			caddxVariablesFolder = indigo.variables.folders[self.plugin.pluginPrefs['variableFolderName']]
			
		if varName not in indigo.variables:
			varName_ = indigo.variable.create(name=varName, value="", folder=caddxVariablesFolder)
			indigo.server.log("-- create variable: %s: " % varName_)
			indigo.variable.updateValue(varName_, value=varValue)
		else:
			varName_ = indigo.variables[varName]
			indigo.variable.updateValue(varName_, value=varValue)
			
	########################################
	# update values from "Interface Configuration Message"
	########################################
	
	# update Interface Configuration Plugin Preferences from received "Interface Configuration Message"
	def updateInterfaceConfigPluginPrefs(self, varList, newByte):
		if newByte is not None:
			# Todo:  Test after refactor.
			for i in range(8):
				var = varList[i]
				bit = newByte[i]
				self.plugin.pluginPrefs[var] = bit

	# update Interface Configuration Status States from received "Interface Configuration Message"
	def updateInterfaceConfigStates(self, dev, varList, newByte):
		if newByte is not None:
			# Todo:  Test after refactor
			for i in range(8):
				var = varList[i]
				bit = newByte[i]
				self.addToStatesUpdateList(dev, key=var, value=bit)

	########################################
	# update values from "Zone Status Message"
	########################################
	
	# update Zone Configuration UI pluginProps values from received "Zone Status Message" 
	def updateZoneStatusConfigUi(self, localProps, varList, newByte):
		# Todo: Test after refactor
		for i in range(8):
			var = varList[i]
			bit = newByte[i]
			localProps[var] = bit
		return localProps
		
	# update Zone Device States from received "Zone Status Message" 	
	def updateZoneStatus(self, dev, zoneConditionLevel1, zoneConditionLevel2):
		self.addToStatesUpdateList(dev, key='faultedOrDelayedTrip', value=zoneConditionLevel1[7])
		self.addToStatesUpdateList(dev, key='tampered', value=zoneConditionLevel1[6])
		self.addToStatesUpdateList(dev, key='troubleCondition', value=zoneConditionLevel1[5])
		self.addToStatesUpdateList(dev, key='bypassedCondition', value=zoneConditionLevel1[4])
		self.addToStatesUpdateList(dev, key='inhibitedForceArmed', value=zoneConditionLevel1[3])
		self.addToStatesUpdateList(dev, key='lowBattery', value=zoneConditionLevel1[2])
		self.addToStatesUpdateList(dev, key='lossOfSupervision', value=zoneConditionLevel1[1])
		self.addToStatesUpdateList(dev, key='alarmMemoryCondition', value=zoneConditionLevel2[7])
		self.addToStatesUpdateList(dev, key='bypassMemory', value=zoneConditionLevel2[6])

	########################################
	# update values from "Zone Snapshot Message"
	########################################
	
	# update Zone Device States Snapshot from received "Zone Snapshot Message"
	def updateZoneSnapshot(self, offset, varList, newByte):
		zoneAddress = (offset + 1)
		if newByte is not None:
			for key in newByte:
				# self.plugin.debugLog("updateZoneSnapshot:        updating zone: %r." % zoneAddress)
				if zoneAddress in self.zoneList.keys():
					dev = self.zoneList[zoneAddress] 
					nibble = newByte[key]
					address = 3
					bitLocation = 7
					# Todo: Re-factor this loop
					for i in range(0, 4):
						# self.plugin.debugLog("updateZoneSnapshot:        updating device state,  zone: %r,  variable: %r,  value: %r,  address: %r" % (zoneAddress, var, bit, bitLocation))
						self.addToStatesUpdateList(dev, key=varList[address], value=nibble[bitLocation])
						address -= 1
						bitLocation -= 1
					zoneAddress += 1	
	
				if zoneAddress in self.zoneList.keys():
					dev = self.zoneList[zoneAddress] 
					nibble = newByte[key]
					address = 3
					bitLocation = 3
					# Todo: Re-factor this loop
					for i in range(0, 4):
						# self.plugin.debugLog("updateZoneSnapshot:        updating device state,  zone: %r,  variable: %r,  value: %r,  address: %r" % (zoneAddress, var, bit, bitLocation))
						self.addToStatesUpdateList(dev, key=varList[address], value=nibble[bitLocation])
						address -= 1
						bitLocation -= 1
					zoneAddress += 1	

		else:
			self.plugin.debugLog("updateZoneSnapshot(): -- no device state records in message dictionary for zone snapshot message update.")					

	########################################
	# update values from "Partition Status Message"
	########################################
	
	# update Partition Configuration UI pluginProps values from received "Partition Status Message"

	""" Not implemented?
	def updatePartitionStatusConfigUi(self, localProps, varList, bitList):
		# Todo: Test after refactor
		for i in range(8):
			var = varList[i]
			bit = bitList[i]
			localProps[var] = bit
		return localProps
	"""
		
	# update Partition Status States from received "Partition Status Message" 
	def updatePartitionStatus(self, dev, varList, newByte):
		if newByte is not None:
			# Todo: Verify refactored loop
			for i in range(8):
				self.addToStatesUpdateList(dev, key=varList[i], value=newByte[i])

	########################################
	# update values from "Partition Snapshot Message"
	########################################
	
	# update Partition Configuration UI pluginProps values from received "Partition Snapshot Message"

	""" Not implemented
	def updatePartitionSnapshotConfigUi(self, varList, bitList):
		for key in bitList:
			partitionNumber = (key + 1)
			# self.plugin.debugLog("updatePartitionSnapshotConfigUi:        updating partition: %r" % partitionNumber)
			if partitionNumber in self.partitionList.keys():
				dev = self.partitionList[partitionNumber]
				localPropsCopy = dev.pluginProps 
				nibble = bitList[key]
				address = 7
				bitLocation = 0
				# Todo: Re-factor this loop
				for i in nibble:
					var = varList[address]
					bit = nibble[address]
					# self.plugin.debugLog("updatePartitionSnapshotConfigUi:        updating device state variable: %r,  value: %r,  address: %r" % (var, bit, bitLocation))
					localPropsCopy[var] = bit
					address -= 1
					bitLocation += 1
				dev.replacePluginPropsOnServer(localPropsCopy)	
			else:
				pass
	"""

	# update Partition Device States Snapshot from received "Partition Snapshot Message" 
	def updatePartitionSnapshot(self, varList: list[str], bitList: list[str]):
		partitionNumber = 1
		for entry in bitList:
			# self.plugin.debugLog("updatePartitionSnapshot:        updating partition: %r" % partitionNumber)
			if partitionNumber in self.partitionList.keys():
				dev = self.partitionList[partitionNumber] 
				nibble = entry
				address = 7
				bitLocation = 0
				# Todo: Re-factor this loop
				# noinspection PyUnusedLocal
				for i in nibble:
					# self.plugin.debugLog("updatePartitionSnapshot:        updating device state variable: %r,  value: %r,  address: %r" % (var, bit, bitLocation))
					self.addToStatesUpdateList(dev, key=varList[address], value=nibble[address])
					address -= 1
					bitLocation += 1
			partitionNumber += 1

	########################################
	# update values from "System Status Message"
	########################################
	
	def updateSystemStatusPluginPrefs(self, varList, newByte) -> None:
		"""
		Update System Status Information plugin preferences from received "System Status Message".

		:param varList: TBD
		:param newByte: TBD
		:return: None
		"""
		if newByte is not None:
			# Todo: Test after refactor
			for i in range(8):
				var = varList[i]
				bit = newByte[i]
				# self.plugin.debugLog("updateSystemStatusPluginPrefs:        updating plugin pref variable: %r,  value: %r,  address: %r" % (var, bit, bitLocation))
				self.plugin.pluginPrefs[var] = bit
					
	# update System Status States from received "System Status Message"	
	def updateSystemStatus(self, dev, varList, newByte):
		if newByte is not None:
			# Todo: Test after refactor
			for i in range(8):
				# self.plugin.debugLog("updateSystemStatus:        updating device state variable: %r,  value: %r,  address: %r" % (var, bit, bitLocation))
				self.addToStatesUpdateList(dev, key=varList[i], value=newByte[i])

	########################################
	# update values from "User Information Reply"
	########################################
	
	# update User Information Configuration UI pluginProps values from received "User Information Reply" 	
	def updateUserInformationStatusConfigUi(self, localProps, varList, newByte):
		# Todo: Test after refactor
		for i in range(8):
			var = varList[i]
			bit = newByte[i]
			# self.plugin.debugLog("updateUserInformationStatusConfigUi:        updating device config ui variable: %r,  value: %r,  address: %r" % (var, bit, bitLocation))
			localProps[var] = bit

		return localProps
		
	# update User Information Status States from received "User Information Reply" 	
	def updateUserInformationStatus(self, dev, varList, newByte):
		if newByte is not None:
			# Todo: Test after refactor
			for i in range(8):
				# self.plugin.debugLog("updateUserInformationStatus:        updating device state variable: %r,  value: %r,  address: %r" % (var, bit, bitLocation))
				self.addToStatesUpdateList(dev, key=varList[i], value=newByte[i])

	################################################################################
	# Routine for Alarm Panel Lookup Dictionaries method 	(state translation tables for message number and log events)
	################################################################################
	
	########################################
	# translate message number to message description
	########################################
	def messageAlarmDict(self, kmessageNumber):
		alarmDict = {
			"01": "Interface Configuration Message",
			"03": "Zone Name Message",
			"04": "Zone Status Message",
			"05": "Zones Snapshot Message",
			"06": "Partition Status Message",
			"07": "Partitions Snapshot Message",
			"08": "System Status Message",
			"09": "X-10 Message Received",
			"0a": "Log Event Message",
			"0b": "Keypad Message Received",
			"10": "Program Data Reply",
			"12": "User Information Reply",
			"1c": "Command / Request Failed",
			"1d": "ACK",
			"1e": "NAK",
			"1f": "CAN",
			"21": "Interface Configuration Request",
			"23": "Zone Name Request",
			"24": "Zone Status Request",
			"25": "Zones Snapshot Request",
			"26": "Partition Status Request",
			"27": "Partitions Snapshot Request",
			"28": "System Status Request",
			"29": "Send X-10 Message",
			"2a": "Log Event Request",
			"2b": "Send Keypad Text Message",
			"2c": "Keypad Terminal Mode Request",
			"30": "Program Data Request",
			"31": "Program Data Command",
			"32": "User Information Request with Pin",
			"33": "User Information Request without Pin",
			"34": "Set User Code Command with Pin",
			"35": "Set User Code Command without Pin",
			"36": "Set User Authorisation Command with Pin",
			"37": "Set User Authorisation Command without Pin",
			"3a": "Store Communication Event Command",
			"3b": "Set Date / Time Command",
			"3c": "Primary Keypad Function with Pin",
			"3d": "Primary Keypad Function without Pin",
			"3e": "Secondary Keypad Function",
			"3f": "Zone Bypass Toggle",
			"81": "Interface Configuration Message",
			"83": "Zone Name Message",
			"84": "Zone Status Message",
			"85": "Zones Snapshot Message",
			"86": "Partition Status Message",
			"87": "Partitions Snapshot Message",
			"88": "System Status Message",
			"89": "X-10 Message Received",
			"8a": "Log Event Message",
			"8b": "Keypad Message Received",
			"a9": "Send X-10 Message",
			"ab": "Send Keypad Text Message",
			"ac": "Keypad Terminal Mode Request",
			"b1": "Program Data Command",
			"b4": "Set User Code Command with Pin",
			"b5": "Set User Code Command without Pin",
			"b6": "Set User Authorisation Command with Pin",
			"b7": "Set User Authorisation Command without Pin",
			"ba": "Store Communication Event Command",
			"bb": "Set Clock / Calender Command",
			"bc": "Primary Keypad Function with Pin",
			"bd": "Primary Keypad Function without Pin",
			"be": "Secondary Keypad Function",
			"bf": "Zone Bypass Toggle",
			"ff": "end of file"
		}
		if kmessageNumber in alarmDict:
			message = alarmDict[kmessageNumber]
		else:
			message = "Program Error: No such message"
		return message
		
	########################################
	# translate log event type number to an event description
	########################################
	
	def messageLogEventDict(self, keventType):
		eventDict = {
			"0": "Alarm",
			"1": "Alarm Restore",
			"2": "Bypass",
			"3": "Bypass Restore",
			"4": "Tamper",
			"5": "Tamper Restore",
			"6": "Trouble",
			"7": "Trouble Restore",
			"8": "Tx Low Battery",
			"9": "Tx Low Battery Restore",
			"10": "Zone Lost",
			"11": "Zone Lost Restore",
			"12": "Not Used",
			"13": "Not Used",
			"14": "Not Used",
			"15": "Not Used",
			"16": "Not Used",
			"17": "Special Expansion Event",
			"18": "Duress",
			"19": "Fire Alert (Manual)",
			"20": "Medical Alert",
			"21": "Not Used",
			"22": "Police Panic",
			"23": "Keypad Tamper",
			"24": "Control Box Tamper",
			"25": "Control Box Tamper Restore",
			"26": "AC Failure",
			"27": "AC Failure Restore",
			"28": "Low Battery",
			"29": "Low Battery Restore",
			"30": "Over-current",
			"31": "Over-current Restore",
			"32": "Siren Tamper",
			"33": "Siren Tamper Restore",
			"34": "Telephone Fault",
			"35": "Telephone Fault Restore",
			"36": "Expander Trouble",
			"37": "Expander Trouble Restore",
			"38": "Fail To Communicate",
			"39": "Log Full",
			"40": "Opening",
			"41": "Closing",
			"42": "Exit Error",
			"43": "Recent Closing",
			"44": "Auto Test",
			"45": "Start Program",
			"46": "End Program",
			"47": "Start Download",
			"48": "End Download",
			"49": "Cancel",
			"50": "Ground Fault",
			"51": "Ground Fault Restore",
			"52": "Manual Test",
			"53": "Closed with Zones Bypassed",
			"54": "Start of Listen In",
			"55": "Technician On Site",
			"56": "Technician Left",
			"57": "Control Power Up",
			"119": "Not Used",
			"120": "First To Open",
			"121": "Last to Close",
			"122": "Pin Entered with Bit 7 Set",
			"123": "Begin Walk Test",
			"124": "End Walk Test",
			"125": "Re-Exit",
			"126": "Output Trip",
			"127": "Data Lost"
		}
		if keventType in eventDict:
			event = eventDict[keventType]
		else:
			event = "Program Error: No such event"
		self.plugin.debugLog("messageLogEventDict:        event number \"%s\" " % keventType)
		self.plugin.debugLog("messageLogEventDict:        event description \"%s\" " % event)
		return event
									
	########################################
	# translate log byte 5 to zone, user or device
	########################################
	
	def messageLogByte5Dict(self, keventType):
		eventType = str(keventType)
		byte5Dict = {
			"0": "zone",
			"1": "zone",
			"2": "zone",
			"3": "zone",
			"4": "zone",
			"5": "zone",
			"6": "zone",
			"7": "zone",
			"8": "zone",
			"9": "zone",
			"10": "zone",
			"11": "zone",
			"12": "zone",
			"13": "none",
			"14": "none",
			"15": "none",
			"16": "none",
			"17": "none",
			"18": "none",
			"19": "none",
			"20": "none",
			"21": "none",
			"22": "none",
			"23": "none",
			"24": "device",
			"25": "device",
			"26": "device",
			"27": "device",
			"28": "device",
			"29": "device",
			"30": "device",
			"31": "device",
			"32": "device",
			"33": "device",
			"34": "none",
			"35": "none",
			"36": "device",
			"37": "device",
			"38": "none",
			"39": "none",
			"40": "user",
			"41": "user",
			"42": "user",
			"43": "user",
			"44": "none",
			"45": "none",
			"46": "none",
			"47": "none",
			"48": "none",
			"49": "user",
			"50": "none",
			"51": "none",
			"52": "none",
			"53": "user",
			"54": "none",
			"55": "none",
			"56": "none",
			"57": "none",
			"119": "none",
			"120": "user",
			"121": "user",
			"122": "user",
			"123": "none",
			"124": "none",
			"125": "none",
			"126": "user",
			"127": "none"
		}
		if eventType in byte5Dict:
			byte5Value = byte5Dict[eventType]
		else:
			byte5Value = "Program Error: No such byte5Value"
		self.plugin.debugLog("messageLogByte5Dict:        event number: \"%s\" " % eventType)
		self.plugin.debugLog("messageLogByte5Dict:        zone,  device,  user: \"%s\" " % byte5Value)
		return byte5Value
		
	########################################
	# translate log byte 6 to reference partition or not	
	########################################
	
	def messageLogByte6Dict(self, keventType):
		eventType = str(keventType)
		byte6Dict = {
			"0": True,
			"1": True,
			"2": True,
			"3": True,
			"4": True,
			"5": True,
			"6": True,
			"7": True,
			"8": True,
			"9": True,
			"10": True,
			"11": True,
			"12": True,
			"13": False,
			"14": False,
			"15": False,
			"16": False,
			"17": False,
			"18": True,
			"19": True,
			"20": True,
			"21": False,
			"22": True,
			"23": True,
			"24": False,
			"25": False,
			"26": False,
			"27": False,
			"28": False,
			"29": False,
			"30": False,
			"31": False,
			"32": False,
			"33": False,
			"34": False,
			"35": False,
			"36": False,
			"37": False,
			"38": False,
			"39": False,
			"40": True,
			"41": True,
			"42": True,
			"43": True,
			"44": False,
			"45": False,
			"46": False,
			"47": False,
			"48": False,
			"49": True,
			"50": False,
			"51": False,
			"52": False,
			"53": True,
			"54": False,
			"55": False,
			"56": False,
			"57": False,
			"119": False,
			"120": True,
			"121": True,
			"122": True,
			"123": False,
			"124": False,
			"125": True,
			"126": False,
			"127": False
		}
		if eventType in byte6Dict:
			byte6Valid = byte6Dict[eventType]
		else:
			byte6Valid = "Program Error: No such byte6Valid"
		self.plugin.debugLog("messageLogByte6Dict:        event number: \"%s\" " % eventType)
		self.plugin.debugLog("messageLogByte6Dict:        partition valid: \"%s\" " % byte6Valid)		
		return byte6Valid
		
	########################################
	# translate log device address to a module description
	########################################
	
	def messageLogDeviceAddressDict(self, kdeviceAddress):
		deviceAddress = str(kdeviceAddress)
		deviceDict = {
			"0": "Security Panel",
			"16": "Hardwired Expander NX-216E (start zone 17)",
			"17": "Hardwired Expander NX-216E (start zone 25)",
			"18": "Hardwired Expander NX-216E (start zone 33)",
			"19": "Hardwired Expander NX-216E (start zone 41)",
			"20": "Hardwired Expander NX-216E (start zone 49)",
			"21": "Hardwired Expander NX-216E (start zone 57)",
			"23": "Hardwired Expander NX-216E (start zone 09)",
			"24": "Relay Expander NX-507E or Output Expander NX-508E (module 1)",
			"25": "Relay Expander NX-507E or Output Expander NX-508E (module 2)",
			"26": "Relay Expander NX-507E or Output Expander NX-508E (module 3)",
			"27": "Relay Expander NX-507E or Output Expander NX-508E (module 4)",
			"28": "Relay Expander NX-507E or Output Expander NX-508E (module 5)",
			"29": "Relay Expander NX-507E or Output Expander NX-508E (module 6)",
			"30": "Relay Expander NX-507E or Output Expander NX-508E (module 7)",
			"31": "Relay Expander NX-507E or Output Expander NX-508E (module 8)",
			"32": "Wireless Receiver NX-448E (module 6)",
			"33": "Wireless Receiver NX-448E (module 7)",
			"34": "Wireless Receiver NX-448E (module 8)",
			"35": "Wireless Receiver NX-448E (module 1)",
			"36": "Wireless Receiver NX-448E (module 2)",
			"37": "Wireless Receiver NX-448E (module 3)",
			"38": "Wireless Receiver NX-448E (module 4)",
			"39": "Wireless Receiver NX-448E (module 5)",
			"84": "Remote Power Supply NX-320E (module 1)",
			"85": "Remote Power Supply NX-320E (module 2)",
			"86": "Remote Power Supply NX-320E (module 3)",
			"87": "Remote Power Supply NX-320E (module 4)",
			"88": "Remote Power Supply NX-320E (module 5)",
			"89": "Remote Power Supply NX-320E (module 6)",
			"90": "Remote Power Supply NX-320E (module 7)",
			"91": "Remote Power Supply NX-320E (module 8)",
			"96": "Hardwired Expander NX-216E (start zone 65)",
			"97": "Hardwired Expander NX-216E (start zone 73)",
			"98": "Hardwired Expander NX-216E (start zone 81)",
			"99": "Hardwired Expander NX-216E (start zone 89)",
			"100": "Hardwired Expander NX-216E (start zone 97)",
			"101": "Hardwired Expander NX-216E (start zone 105)",
			"102": "Hardwired Expander NX-216E (start zone 113)",
			"103": "Hardwired Expander NX-216E (start zone 121)",
			"104": "Hardwired Expander NX-216E (start zone 129)",
			"105": "Hardwired Expander NX-216E (start zone 137)",
			"106": "Hardwired Expander NX-216E (start zone 145)",
			"107": "Hardwired Expander NX-216E (start zone 153)",
			"108": "Hardwired Expander NX-216E (start zone 161)",
			"109": "Hardwired Expander NX-216E (start zone 169)",
			"110": "Hardwired Expander NX-216E (start zone 177)",
			"111": "Hardwired Expander NX-216E (start zone 185)",
			"192": "Keypad (1)",
			"193": "Keypad (1)",
			"194": "Keypad (1)",
			"195": "Keypad (1)",
			"196": "Keypad (1)",
			"197": "Keypad (1)",
			"198": "Keypad (1)",
			"199": "Keypad (1)",
			"200": "Keypad (2)",
			"201": "Keypad (2)",
			"202": "Keypad (2)",
			"203": "Keypad (2)",
			"204": "Keypad (2)",
			"205": "Keypad (2)",
			"206": "Keypad (2)",
			"207": "Keypad (2)",
			"208": "Keypad (3)",
			"209": "Keypad (3)",
			"210": "Keypad (3)",
			"211": "Keypad (3)",
			"212": "Keypad (3)",
			"213": "Keypad (3)",
			"214": "Keypad (3)",
			"215": "Keypad (3)",
			"216": "Keypad (4)",
			"217": "Keypad (4)",
			"218": "Keypad (4)",
			"219": "Keypad (4)",
			"220": "Keypad (4)",
			"221": "Keypad (4)",
			"222": "Keypad (4)",
			"223": "Keypad (4)",
			"224": "Keypad (5)",
			"225": "Keypad (5)",
			"226": "Keypad (5)",
			"227": "Keypad (5)",
			"228": "Keypad (5)",
			"229": "Keypad (5)",
			"230": "Keypad (5)",
			"231": "Keypad (5)",
			"232": "Keypad (6)",
			"233": "Keypad (6)",
			"234": "Keypad (6)",
			"235": "Keypad (6)",
			"236": "Keypad (6)",
			"237": "Keypad (6)",
			"238": "Keypad (6)",
			"239": "Keypad (6)",
			"240": "Keypad (7)",
			"241": "Keypad (7)",
			"242": "Keypad (7)",
			"243": "Keypad (7)",
			"244": "Keypad (7)",
			"245": "Keypad (7)",
			"246": "Keypad (7)",
			"247": "Keypad (7)",
			"248": "Keypad (8)",
			"249": "Keypad (8)",
			"250": "Keypad (8)",
			"251": "Keypad (8)",
			"252": "Keypad (8)",
			"253": "Keypad (8)",
			"254": "Keypad (8)",
			"255": "Keypad (8)"
		}
		if deviceAddress in deviceDict:
			device = deviceDict[deviceAddress]
		else:
			device = "Program Error: No such device"
		self.plugin.debugLog("messageLogEventDict:        device: \"%s\" " % device)
		return device		

	def addToStatesUpdateList(self, dev, key: str, value: int | str) -> None:
		"""
		Collect all devices states to be updated.
		Will update collected state changes in executeUpdateStatesList().

		:param dev: The device handle.
		:param key: The key for the device state.
		:param value: The value to which the device state is set.
		:return: None
		"""
		devId = str(dev.id)
		local = copy.copy(self.devStateChangeList)
		if devId not in local:
			local[devId] = {}
		local[devId][key] = value
		self.devStateChangeList = copy.copy(local)

	def executeUpdateStatesList(self) -> None:
		if not self.devStateChangeList:
			return
		local = copy.copy(self.devStateChangeList)
		self.devStateChangeList = {}
		changedOnly = {}

		for devId in local:
			if local[devId]:
				dev = indigo.devices[int(devId)]
				for key in local[devId]:
					if key not in dev.states:
						indigo.server.log(f"device: {dev.name}  does not have state: {key}, value: {local[devId][key]}")
						continue
					if local[devId][key] != dev.states[key]:
						if devId not in changedOnly:
							changedOnly[devId] = []
						changedOnly[devId].append({"key": key, "value": local[devId][key]})

						if key == "zoneState":
							self.plugin.triggerEvent("zoneChanged")
							if local[devId][key].find(u"normal") > -1:
								dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
								changedOnly[devId].append(
									{"key": "lastNormal", "value": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
							elif local[devId][key].find(u"triggered") > -1:
								dev.updateStateImageOnServer(indigo.kStateImageSel.SensorTripped)
								changedOnly[devId].append(
									{"key": "lastTriggered", "value": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
							else:
								dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
							changedOnly[devId].append({u"key": "zoneDisplay", "value": self.plugin.padDisplay(
								local[devId][key]) + datetime.datetime.now().strftime("%m-%d %H:%M:%S")})

				if devId in changedOnly and changedOnly[devId] != []:
					dev.updateStatesOnServer(changedOnly[devId])
