#! /usr/bin/env python
# -*- coding: utf-8 -*-
################################################################################
# This is an Indigo 5.0 plugin to support the "Caddx NetworX NX-8e Alarm System"
# Written 2011 by Ian Sibley
################################################################################

################################################################################
# Python Imports
################################################################################
import os
import sys
import functools
import time
import re
import Queue

import serial
import datetime
import binascii

import indigo

################################################################################
# Local Imports
################################################################################
from string	import atoi, atof

################################################################################
# Globals
################################################################################
panelFirmware = ""						# used as a comm alive flag on initiate comms
keypadDisplayName = " "					# used to store temporary zoneDipslayName for Keypad Display Name used in creating zone devices

# Simple Requests and Commands		message format[0x7e, msg_length, msg_number, {msg_contents}, checksum1, checksum2,]
ACK = "\x01\x1d"
NAK = "\x01\x1e"
CAN = "\x01\x1f"

interfaceConfigurationRequest = "\x01\x21"
partitionSnapshotRequest = "\x01\x27"
systemStatusRequest = "\x01\x28"

# Keypad Commands
cmdArmStay = "\x04\xbd\x03\x01\x01"
cmdArmAway = "\x04\xbd\x02\x01\x01"
cmdDisarm = "\x04\xbd\x01\x01\x01"
cmdFirePanic = "\x03\xbe\x04\x01"
cmdMedicalPanic = "\x03\xbe\x05\x01"
cmdPolicePanic = "\x03\xbe\x06\x01"
cmdTurnOffSounderOrAlarm = "\x04\xbd\x00\x01\x01"
cmdCancel = "\x04\xbd\x04\x01\x01"
cmdInitiateAutoArm = "\x04\xbd\x05\x01\x01"
cmdStartWalkTestMode = "\x04\xbd\x06\x01\x01"
cmdStopWalkTestMode = "\x04\xbd\x07\x01\x01"
cmdStay1ButtonArmToggleInteriors = "\x03\xbe\x00\x01"
cmdChimeToggleChimeMode = "\x03\xbe\x01\x01"
cmdExitButtonArmToggleInstant = "\x03\xbe\x02\x01"
cmdBypassInteriors = "\x03\xbe\x03\x01"
cmdSmokeDetectorReset = "\x03\xbe\x07\x01"
cmdAutoCallbackDownload = "\x03\xbe\x08\x01"
cmdManualPickupDownload = "\x03\xbe\x09\x01"
cmdEnableSilentExitForThisArmCycle = "\x03\xbe\x0a\x01"
cmdPerformTest = "\x03\xbe\x0b\x01"
cmdGroupBypass = "\x03\xbe\x0c\x01"
cmdAuxiliaryFunction1 = "\x03\xbe\x0d\x01"
cmdAuxiliaryFunction2 = "\x03\xbe\x0e\x01"
cmdStartKeypadSounder = "\x03\xbe\x0f\x01"

cmdInterfaceConfigurationRequest = "\x01\x21"
cmdZoneNameRequest = "\x02\x23"
cmdZoneStatusRequest = "\x02\x24"
cmdZonesSnapshotRequest = "\x02\x25"
cmdPartitionStatusRequest = "\x02\x26"
cmdPartitionSnapshotRequest = "\x01\x27"
cmdSystemStatusRequest = "\x01\x28"
cmdUserInformationRequestWithoutPin = "\x02\x33"

cmdZoneBypassToggle = "\x02\xbf"

# Spoken Text Comments
sayArmingStay = "alarm system arming in Stay Mode"
sayArmedStay = "alarm system armed in Stay Mode"
sayArmingAway = "alarm system arming in Away Mode"
sayArmedAway = "alarm system armed in Away Mode"
sayArmed = "alarm system Armed"
sayDisarmed = "alarm system Disarmed. Welcome Home"
sayExitDelayWarning = "Warning - exit delay expires in 10 seconds"
sayFailedToArm = "alarm system Failed To Arm"
sayZoneTripped = "Intruder Alert, sensor tripped in"
sayActivateFire = "The fire alarm has been activated. Please evacuated the building immediately"
sayActivateMedical = "The medical emergency has been activated. An Ambelance has been called"
sayActivatePolice = "The duress alert has been activate. The police have been called"

################################################################################
class Caddx(object):
	
	########################################
	
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
		
		self.commandQueue = ""
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
		
		self.createVariables = False
		self.repeatAlarmTripped = False

	########################################
	def __del__(self):
		pass
		
	################################################################################
	# Actions command method routines <action.xml>
	################################################################################

	
	########################################
	# Primary & Secondary Keypad Commands routines
	########################################
	
	def _actionGeneric(self, pluginAction, action):
		dev = indigo.devices[pluginAction.deviceId]
		partition = int(dev.pluginProps["address"])
		keypad = int(dev.pluginProps["associatedKeypad"])
		if action == "Arm in Stay Mode":
			logPrintMessage = u"execute action:        Arm Alarm in Stay Mode"
			self.sendMsgToQueue(cmdArmStay)
			if self.plugin.enableSpeakPrompts:	
				indigo.server.speak(sayArmingStay)
		elif action == "Arm in Away Mode":
			logPrintMessage = u"execute action:        Arm Alarm in Away Mode"
			self.sendMsgToQueue(cmdArmAway)
			if self.plugin.enableSpeakPrompts:
				indigo.server.speak(sayArmingAway)
		elif action == "Disarm System":
			logPrintMessage = u"execute action:        Disarm System"
			self.sendMsgToQueue(cmdDisarm)
		elif action == "Activate Fire Panic":
			logPrintMessage = u"execute action:        Activate Fire Alert"
			self.sendMsgToQueue(cmdFirePanic)
			if self.plugin.enableSpeakPrompts:
				indigo.server.speak(sayActivateFire)
		elif action == "Activate Medical Panic":
			logPrintMessage = u"execute action:        Activate Medical Alert"
			self.sendMsgToQueue(cmdMedicalPanic)
			if self.plugin.enableSpeakPrompts:
				indigo.server.speak(sayActivateMedical)
		elif action == "Activate Police Duress":
			logPrintMessage = u"execute action:        Activate Police Duress"
			self.sendMsgToQueue(cmdPolicePanic)
			if self.plugin.enableSpeakPrompts:
				indigo.server.speak(sayActivatePolice)
		elif action == "Turn Off Any Sounder or Alarm":
			logPrintMessage = u"execute action:        Turn Off Any Sounder or Alarm"
			self.sendMsgToQueue(cmdTurnOffSounderOrAlarm)
		elif action == "Cancel":
			logPrintMessage = u"execute action:        Cancel"
			self.sendMsgToQueue(cmdCancel)
		elif action == "Initiate Auto Arm":
			logPrintMessage = u"execute action:        Initiate Auto Arm"
			self.sendMsgToQueue(cmdInitiateAutoArm)
		elif action == "Start Walk Test Mode":
			logPrintMessage = u"execute action:        Start Walk Test Mode"
			self.sendMsgToQueue(cmdStartWalkTestMode)
		elif action == "Stop Walk Test Mode":
			logPrintMessage = u"execute action:        Stop Walk Test Mode"
			self.sendMsgToQueue(cmdStopWalkTestMode)
		elif action == "Stay 1 Button Arm Toggle Interiors":
			logPrintMessage = u"execute action:        Stay (1 button arm / toggle Interiors)"
			self.sendMsgToQueue(cmdStay1ButtonArmToggleInteriors)
		elif action == "Toggle Chime Mode":
			logPrintMessage = u"execute action:        Chime (toggle Chime Mode)"
			self.sendMsgToQueue(cmdChimeToggleChimeMode)
		elif action == "Exit 1 Button Arm Toggle Instant":
			logPrintMessage = u"execute action:        Exit (1 button arm / toggle Instant)"
			self.sendMsgToQueue(cmdExitButtonArmToggleInstant)
		elif action == "Bypass Interiors":
			logPrintMessage = u"execute action:        Bypass Interiors"
			self.sendMsgToQueue(cmdBypassInteriors)
		elif action == "Reset Smoke Detectors":
			logPrintMessage = u"execute action:        Reset Smoke Detectors"
			self.sendMsgToQueue(cmdSmokeDetectorReset)
		elif action == "Auto Callback Download":
			logPrintMessage = u"execute action:        Auto Callback Download"
			self.sendMsgToQueue(cmdAutoCallbackDownload)
		elif action == "Manual Pickup Download":
			logPrintMessage = u"execute action:        Manual Pickup Download"
			self.sendMsgToQueue(cmdManualPickupDownload)
		elif action == "Enable Silent Exit for this Arm Cycle":
			logPrintMessage = u"execute action:        Enable Silent Exit (for this arm cycle)"
			self.sendMsgToQueue(cmdEnableSilentExitForThisArmCycle)
		elif action == "Perform Test":
			logPrintMessage = u"execute action:        Perform Test"
			self.sendMsgToQueue(cmdPerformTest)
		elif action == "Group Bypass":
			logPrintMessage = u"execute action:        Group Bypass"
			self.sendMsgToQueue(cmdGroupBypass)
		elif action == "Auxiliary Function 1":
			logPrintMessage = u"execute action:        Auxiliary Function 1"
			self.sendMsgToQueue(cmdAuxiliaryFunction1)
		elif action == "Auxiliary Function 2":
			logPrintMessage = u"execute action:        Auxiliary Function 2"
			self.sendMsgToQueue(cmdAuxiliaryFunction2)
		elif action == "Start Keypad Sounder":
			logPrintMessage = u"execute action:        Start Keypad Sounder"
			self.sendMsgToQueue(cmdStartKeypadSounder)			
		else:
			indigo.server.log(u"execute action:        Requested Action %s not defined." % action)
		if self.plugin.commandActInfo or self.plugin.debug:
			indigo.server.log(u"%s" % logPrintMessage)
		
	########################################
	# Supported Requests and Commands routines
	########################################
	
	def _actionCmdMessage(self, pluginAction, action):
		if action == "Interface Configuration Request":
			logPrintMessage = u"execute action:        Interface Configuration Request"
			self.sendMsgToQueue(cmdInterfaceConfigurationRequest)
		elif action == "Zone Name Request":
			value = int(pluginAction.props["zone"])
			kmessagestart = binascii.b2a_hex(cmdZoneNameRequest)
			kzone = self.convertDecToHex(int(value - 1))		# 0 = zone 1
			kzoneNameRequest = kmessagestart + kzone
			zoneNameRequest = binascii.a2b_hex(kzoneNameRequest)
			logPrintMessage = u"execute action:        Zone Name Request,  zone: %s" % value
			self.sendMsgToQueue(zoneNameRequest)
		elif action == "Zone Status Request":
			value = int(pluginAction.props["zone"])
			kmessagestart = binascii.b2a_hex(cmdZoneStatusRequest)
			kzone = self.convertDecToHex(int(value - 1))		# 0 = zone 1
			kzoneStatusRequest = kmessagestart + kzone
			zoneStatusRequest = binascii.a2b_hex(kzoneStatusRequest)
			logPrintMessage = u"execute action:        Zone Status Request,  zone: %s" % value
			self.sendMsgToQueue(zoneStatusRequest)
		elif action == "Zones Snapshot Request":
			value = int(pluginAction.props["zoneOffset"])
			kmessagestart = binascii.b2a_hex(cmdZonesSnapshotRequest)
			kzoneOffSet = self.convertDecToHex(int(value))	
			kzonesSnapshotRequest = kmessagestart + kzoneOffSet
			zonesSnapshotRequest = binascii.a2b_hex(kzonesSnapshotRequest)
			logPrintMessage = u"execute action:        Zones Snapshot Request,  block address: %s" % value
			self.sendMsgToQueue(zonesSnapshotRequest)
		elif action == "Partition Status Request":
			value = int(pluginAction.props["partition"])
			kmessagestart = binascii.b2a_hex(cmdPartitionStatusRequest)
			kpartition = self.convertDecToHex(int(value - 1))		# 0 = partition 1
			kpartitionStatusRequest = kmessagestart + kpartition
			partitionStatusRequest = binascii.a2b_hex(kpartitionStatusRequest)
			logPrintMessage = u"execute action:        Partition Status Request,  partition: %s" % value
			self.sendMsgToQueue(partitionStatusRequest)
		elif action == "Partition Snapshot Request":
			logPrintMessage = u"execute action:        Partition Snapshot Request"
			self.sendMsgToQueue(cmdPartitionSnapshotRequest)					
		elif action == "System Status Request":
			logPrintMessage = u"execute action:        System Status Request"
			self.sendMsgToQueue(cmdSystemStatusRequest)
		elif action == "Send X-10 Command":
			logPrintMessage = u"execute action:        Send X-10 Command"
			self.sendMsgToQueue(cmdSystemStatusRequest)
		elif action == "Log Event Request":
			logPrintMessage = u"execute action:        Log Event Request"
			self.sendMsgToQueue(cmdSystemStatusRequest)
		elif action == "Send Keypad Text Message":
			logPrintMessage = u"execute action:        Send Keypad Text Message"
			self.sendMsgToQueue(cmdSystemStatusRequest)
		elif action == "Keypad Terminal Mode Request":
			logPrintMessage = u"execute action:        Keypad Terminal Mode Request"
			self.sendMsgToQueue(cmdSystemStatusRequest)
		elif action == "Program Data Request":
			logPrintMessage = u"execute action:        Program Data Request"
			self.sendMsgToQueue(cmdSystemStatusRequest)
		elif action == "Program Data Command":
			logPrintMessage = u"execute action:        Program Data Command"
			self.sendMsgToQueue(cmdSystemStatusRequest)
		elif action == "User Information Request with Pin":
			logPrintMessage = u"execute action:        User Information Request with Pin"
			self.sendMsgToQueue(cmdSystemStatusRequest)
		elif action == "User Information Request without Pin":
			value = int(pluginAction.props["user"])
			kmessagestart = binascii.b2a_hex(cmdUserInformationRequestWithoutPin)
			kuser = self.convertDecToHex(int(value))	
			kuserInformationRequestWithoutPin = kmessagestart + kuser
			userInformationRequestWithoutPin = binascii.a2b_hex(kuserInformationRequestWithoutPin)
			logPrintMessage = u"execute action:        User Information Request without Pin,  user: %s" % value
			self.sendMsgToQueue(userInformationRequestWithoutPin)
		elif action == "Set User Code Command with Pin":
			logPrintMessage = u"execute action:        Set User Code Command with Pin"
			self.sendMsgToQueue(userInformationRequestWithoutPin)
		elif action == "Set User Code Command without Pin":
			logPrintMessage = u"execute action:        et User Code Command without Pin"
			self.sendMsgToQueue(cmdSystemStatusRequest)
		elif action == "Set User Authorisation with Pin":
			logPrintMessage = u"execute action:        Set User Authorisation with Pin"
			self.sendMsgToQueue(cmdSystemStatusRequest)
		elif action == "Set User Authorisation without Pin":
			logPrintMessage = u"execute action:        Set User Authorisation without Pin"
			self.sendMsgToQueue(cmdSystemStatusRequest)
		elif action == "Store Communication Event Command":
			logPrintMessage = u"execute action:        Store Communication Event Command"
			self.sendMsgToQueue(cmdSystemStatusRequest)	
		elif action == "Set Clock and Calender":
			logPrintMessage = u"execute action:        Set Clock and Calender"
			self.sendMsgToQueue(cmdSystemStatusRequest)															
		elif action == "Zone Bypass toggle":
			value = int(pluginAction.props["bypassZone"])
			kmessagestart = binascii.b2a_hex(cmdZoneBypassToggle)
			kzone = self.convertDecToHex(int(value - 1))		# 0 = zone 1
			kzoneBypassToggle = kmessagestart + kzone
			zoneBypassToggle = binascii.a2b_hex(kzoneBypassToggle)
			logPrintMessage = u"execute action:        Zone Bypass Toggle : zone %s :" % value
			self.sendMsgToQueue(zoneBypassToggle)	
		else:
			logPrintMessage = u"execute action:        Requested Action: \"%s\" is not defined." % action
		if self.plugin.commandActInfo or self.plugin.debug:
			indigo.server.log(u"%s" % logPrintMessage)	
	
	########################################
	# system action requests for database synchronisation
	########################################	
	
	def _actionInterfaceConfigurationRequest(self, action):
		if self.plugin.commandActInfo or self.plugin.debug:
			indigo.server.log(u"execute action:        Interface Configuration Request")
		self.sendMsgToQueue(cmdInterfaceConfigurationRequest)
		time.sleep(self.plugin.sleepBetweenComm)
		
	def _actionZoneNameRequest(self, action):
		for key in range(0,action):
			kmessagestart = binascii.b2a_hex(cmdZoneNameRequest)
			kzone = self.convertDecToHex(int(key))		# 0 = zone 1
			kzoneNameRequest = kmessagestart + kzone
			zoneNameRequest = binascii.a2b_hex(kzoneNameRequest)
			if self.plugin.commandActInfo or self.plugin.debug:
				indigo.server.log(u"execute action:        Zone Name Request: %s,   %s  (zone %s)" % (kzone, kzoneNameRequest, (key +1)))
			self.sendMsgToQueue(zoneNameRequest)
			time.sleep(self.plugin.sleepBetweenComm)

	def _actionZoneStatusRequest(self, action):
		for key in range(0,action):
			kmessagestart = binascii.b2a_hex(cmdZoneStatusRequest)
			kzone = self.convertDecToHex(int(key))		# 0 = zone 1
			kzoneStatusRequest = kmessagestart + kzone
			zoneStatusRequest = binascii.a2b_hex(kzoneStatusRequest)
			if self.plugin.commandActInfo or self.plugin.debug:
				indigo.server.log(u"execute action:        Zone Status Request: %s,  %s  (zone %s)" % (kzone, kzoneStatusRequest, (key + 1)))
			self.sendMsgToQueue(zoneStatusRequest)
			time.sleep(self.plugin.sleepBetweenComm)
									
	def _actionZonesSnapshotRequest(self, action):
		for key in range(0,action):
			kmessagestart = binascii.b2a_hex(cmdZonesSnapshotRequest)
			kzoneOffSet = self.convertDecToHex(int(key))	
			kzonesSnapshotRequest = kmessagestart + kzoneOffSet
			zonesSnapshotRequest = binascii.a2b_hex(kzonesSnapshotRequest)
			if self.plugin.commandActInfo or self.plugin.debug:
				indigo.server.log(u"execute action:        Zones Snapshot Request: %s,  %s  (block %s)" % (kzoneOffSet, kzonesSnapshotRequest, key))
			self.sendMsgToQueue(zonesSnapshotRequest)
			time.sleep(self.plugin.sleepBetweenComm)
		
	def _actionPartitionStatusRequest(self, action):
		for key in range(0,action):
			kmessagestart = binascii.b2a_hex(cmdPartitionStatusRequest)
			kpartition = self.convertDecToHex(int(key))		# 0 = partition 1
			kpartitionStatusRequest = kmessagestart + kpartition
			partitionStatusRequest = binascii.a2b_hex(kpartitionStatusRequest)
			if self.plugin.commandActInfo or self.plugin.debug:
				indigo.server.log(u"execute action:        Partition Status Request: %s  %s  (partition %s)" % (kpartition, kpartitionStatusRequest, (key + 1)))
			self.sendMsgToQueue(partitionStatusRequest)
			time.sleep(self.plugin.sleepBetweenComm)
		
	def _actionPartitionSnapshotRequest(self, action):
		if self.plugin.commandActInfo or self.plugin.debug:
			indigo.server.log(u"execute action:        Partition Snapshot Request: Partition 1 - 8")
		self.sendMsgToQueue(cmdPartitionSnapshotRequest)
		time.sleep(self.plugin.sleepBetweenComm)
		
	def _actionSystemStatusRequest(self, action):
		if self.plugin.commandActInfo or self.plugin.debug:
			indigo.server.log(u"execute action:        System Status Request")
		self.sendMsgToQueue(cmdSystemStatusRequest)
		time.sleep(self.plugin.sleepBetweenComm)		

	def _actionLogEventRequest(self, action):
		action = 25
		for key in range(0,action):
			kmessagestart = binascii.b2a_hex('\x02\x2a')
			keventNumber = self.convertDecToHex(int(key + 1))	
			klogEventRequest = kmessagestart + keventNumber
			logEventRequest = binascii.a2b_hex(klogEventRequest)
			if self.plugin.commandActInfo or self.plugin.debug:
				indigo.server.log(u"execute action:        Log Event Request: %s,  %s" % (keventNumber, klogEventRequest))
			self.sendMsgToQueue(logEventRequest)
			time.sleep(self.plugin.sleepBetweenComm)
		
	def _actionUserInformationRequestWithoutPin(self, action):
		for key in range(0,action):
			kmessagestart = binascii.b2a_hex('\x02\x33')
			kuser = self.convertDecToHex(int(key +1))	
			kuserInformationRequestWithoutPin = kmessagestart + kuser
			userInformationRequestWithoutPin = binascii.a2b_hex(kuserInformationRequestWithoutPin)
			if self.plugin.commandActInfo or self.plugin.debug:
				indigo.server.log(u"execute action:        User Information Request without Pin: %s,  %s  (user %s)" % (kuser, kuserInformationRequestWithoutPin, (key + 1)))
			self.sendMsgToQueue(userInformationRequestWithoutPin)
			time.sleep(self.plugin.sleepBetweenComm)					
	
	def _actionSetClockCalenderCommand(self, action):
		kmessagestart = binascii.b2a_hex('\x07\x3b')
		timeStamp = time.localtime(time.time())
		kyear = int((timeStamp[0]) - 2000)
		kdate  = self.convertDecToHex(kyear) + self.convertDecToHex(int(timeStamp[1])) + self.convertDecToHex(int(timeStamp[2]))
		ktime =  self.convertDecToHex(int(timeStamp[3])) + self.convertDecToHex(int(timeStamp[4]))
		day = (timeStamp[6]) -1
		correctWeekdayList = ['3', '4', '5', '6', '7', '1', '2']		# correct timeStamp (1 = Tuesday) where as alarm panel (1 = Sunday)
		cday = correctWeekdayList[day]
		kday = self.convertDecToHex(int(cday))
		kSetClockCalenderCommand = kmessagestart + kdate + ktime + kday
		SetClockCalenderCommand = binascii.a2b_hex(kSetClockCalenderCommand)
		self.sendMsgToQueue(SetClockCalenderCommand)
		time.sleep(self.plugin.sleepBetweenComm)

	#	poll each zone for Keypad Display Name to use in Create Zone Device name
	def _singleZoneNameRequest(self, action):
		key = action
		kmessagestart = binascii.b2a_hex('\x02\x23')
		kzone = self.convertDecToHex(int(key))		# 0 = zone 1
		kzoneNameRequest = kmessagestart + kzone
		zoneNameRequest = binascii.a2b_hex(kzoneNameRequest)
		self.plugin.debugLog(u"execute action:        Zone Name Request: %s,  %s  (zone %s)" % (kzone, kzoneNameRequest, (key +1)))
		self.sendMsgDirect(zoneNameRequest)
		time.sleep(self.plugin.sleepBetweenCreateZone)
											
	################################################################################	
	# Routines for Serial Communication Process methods 
	################################################################################
	
	########################################
	# Device Start and Stop methods	
	########################################
	
	def deviceStart(self, dev):
		self.plugin.debugLog(u"deviceStart:        adding device %s." % dev.name)
			
		if dev.deviceTypeId == u'zone':
			zone = int(dev.pluginProps['address'])
			if zone not in self.zoneList.keys():
				self.zoneList[zone] = dev
				dev.updateStateOnServer(key=u'zoneNumber', value=zone)	
		elif dev.deviceTypeId == u'partition':
			partition = int(dev.pluginProps['address'])
			if partition not in self.partitionList.keys():
				self.partitionList[partition] = dev
				dev.updateStateOnServer(key=u'partitionNumber', value=partition)			
		elif dev.deviceTypeId == u'user':
			user = int(dev.pluginProps['address'])
			if user not in self.userList.keys():
				self.userList[user] = dev
				dev.updateStateOnServer(key=u'userNumber', value=user)
		elif dev.deviceTypeId == u'keypad':
			keypad = int(dev.pluginProps['address'])
			if keypad not in self.keypadList.keys():
				self.keypadList[keypad] = dev
				dev.updateStateOnServer(key=u'keypadNumber', value=keypad)		
		elif dev.deviceTypeId == u'panel':
			panel = int(self.systemId)
			if panel not in self.panelList.keys():
				self.panelList[panel] = dev
				dev.updateStateOnServer(key=u'panelNumber', value=panel)
		elif dev.deviceTypeId == u'statusInfo':
			system = int(self.systemId)
			if system not in self.systemStatusList.keys():
				self.systemStatusList[system] = dev
				dev.updateStateOnServer(key=u'systemNumber', value=system)
	
	def deviceStop(self, dev):
		self.plugin.debugLog(u"deviceStop:        removing device %s." % dev.name)
		
		if dev.deviceTypeId == u'zone':
			zone = int(dev.pluginProps['address'])
			if zone in self.zoneList.keys():
				del self.zoneList[zone]
		elif dev.deviceTypeId == u'partition':
			partition = int(dev.pluginProps['address'])
			if partition in self.partitionList.keys():
				del self.partitionList[partition]
		elif dev.deviceTypeId == u'user':
			user = int(dev.pluginProps['address'])
			if user in self.userList.keys():
				del self.userList[user]
		elif dev.deviceTypeId == u'keypad':
			keypad = int(dev.pluginProps['address'])
			if keypad in self.keypadList.keys():
				del self.keypadList[keypad]		
		elif dev.deviceTypeId == u'panel':
			panel = int(self.systemId)
			if panel in self.panelList.keys():
				del self.panelList[panel]
		elif dev.deviceTypeId == u'statusInfo':
			system = int(self.systemId)
			if system in self.systemStatusList.keys():
				del self.systemStatusList[system]		
	
	########################################
	# Communication Start and Stop methods
	#######################################
	
	# Start Communication method
	def startComm(self):	
		self.plugin.debugLog(u"startComm:        entering process")
		
		devicePort = (self.plugin.devicePort)
		baudRate = atoi(self.plugin.pluginPrefs[u'serialBaudRate'])
		serialTimeout = atof(self.plugin.pluginPrefs['serialTimeout'])
		
		self.devicePort = devicePort
		indigo.server.log(u"initialing connection to Caddx NetworX security devices . . .")
		
		# open serial communication port
		conn = self.plugin.openSerial(u"Caddx Security System", devicePort, baudRate, timeout=serialTimeout, writeTimeout=1)
		if conn:
			self.commStatusUp()
			indigo.server.log(u"connection initialised to Caddx NetworX security devices on %s {baud: %s bps, timeout: %s seconds}." % (devicePort, baudRate, serialTimeout))
			self.conn = conn
			commandQueue = Queue.Queue()
			self.commandQueue = commandQueue
			self.plugin.debugLog(u"startComm:        connection: %s  commandQuene: %s" % (devicePort, commandQueue))
			self.activeCommLoop(devicePort, conn, commandQueue)
		else:
			self.plugin.errorLog(u"startComm:        connection attempt failure to Caddx NetworX Security device on %s" % (devicePort))	
	
	# Stop Communication method
	def stopComm(self):	
		self.plugin.debugLog(u"stopComm:        entering process")
		self.plugin.debugLog(u"stopComm:        initiating stop looping communication to device %s" % (self.devicePort))
		commandQueue = self.commandQueue
		self.commStatusDown()
		
		while not commandQueue.empty():
			command = commandQueue.get()
			self.plugin.debugLog(u"stopComm:        command Queue contains: %s" % command)
		commandQueue.put("stopSerialCommunication")
		del commandQueue
	
	########################################
	# Communication Process method
	#######################################

	def activeCommLoop(self, devicePort, conn, commandQueue):
		try:
			indigo.server.log(u"starting looping communication to caddx security devices.")
			self.suspendInterfaceConfigMessageDisplay = False							# allow interface configuration print to log for the first initialise
			messageDict = {}	
			action = ""
			indigo.server.log(u"set security system date / time to %s. " % self.getCurrentDate())
			self._actionSetClockCalenderCommand(action)									# set current time and date
			
			# start active serial communication looping
			while True:
				self.readCommPort(conn)	
				
				while not commandQueue.empty():
					lenQueue = commandQueue.qsize()
					self.plugin.debugLog(u"activeCommLoop:        || queue has %s command(s) waiting." % str(lenQueue))
					command = commandQueue.get()
							
					if command == "stopSerialCommunication":
						indigo.server.log(u"raising exception \"self.shutdown\" to stop conn communication.")
						raise self.shutdown
							
					self.plugin.debugLog(u"activeCommLoop:        || processing command: %s" % command)		
					self.sendCommPort(conn, command)	
					self.plugin.debugLog(u"activeCommLoop:        || command completed: %s" % command)
					self.commandQueue.task_done()	
				time.sleep(self.plugin.sleepBetweenIdlePoll)							# sleep between read cycles to reduce CPU load			
				
				# trigger to periodically poll data and keep alive (at least 15 minute intervals)
				timeNow = time.time()													# timeNow to current time
				self.commContinuityCheck(timeNow)

		except self.shutdown:
			indigo.server.log(u"closing connection to conn device %s (shutdown process)." % devicePort)
			pass																		# silently fall into finally: section below
		except Exception, e:
			self.plugin.exceptionLog()
		except:
			self.plugin.exceptionLog()
		finally:
			indigo.server.log(u"closed connection to conn device %s (finally)." % devicePort)
			conn.close()	
			pass																		# finally, exit thread.
	
	################################################################################
	# Routines for Communication Protocol methods (commmunication message validation and checksum)
	################################################################################	
	
	#######################################
	# Add new command to queue, which is polled and emptied by concurrentSerialThread funtion
	#######################################
	
	def sendMsgToQueue(self, transmitData):
		commandQueue = self.commandQueue
		
		messageStartFlag = '7e'															# assemble transmit message
		messageNumber = binascii.b2a_hex(transmitData[1])
		alarmMessage = self.messageAlarmDict(messageNumber)
		transmitDataAscii = binascii.b2a_hex(transmitData)
		checksum = self.generateChecksum(transmitDataAscii)
		transmitDataAscii += checksum
		transmitDataAscii = self.insertBitStuffing(transmitDataAscii)					# substitute '7e' or '7d' within the transmit data stream
		transmitDataAscii = messageStartFlag + transmitDataAscii						# insert message start flag
		if self.messageACK == True:														# send transmit message data
			if self.plugin.messageActInfo or self.plugin.debug:
				indigo.server.log(u"sendCmdToQueue:          || queue send message: %s  "  % str(transmitDataAscii))
			commandQueue.put(transmitDataAscii)
		partition = 1																	# update partition deivce state - lastFunction with the last transmited message
		if partition in self.partitionList.keys():
			dev = self.partitionList[partition]
			dev.updateStateOnServer(key="lastFunction", value="%r  >> %r  ** %s  "  % (alarmMessage, messageNumber, self.timestamp()))
		variableID = "sendingMessage"														# update indigo variable "caddx.sendMsgToQueue" with last transmited message
		sendMessageVariable = (u" >> %s --  %s     %r  " % (messageNumber, alarmMessage, transmitDataAscii))
		self.updateVariable(variableID, sendMessageVariable)		
		
	#######################################
	# Send queued command to serial port, then read reply.
	#######################################
	
	def sendCommPort(self, conn, transmitDataAscii):
		if self.plugin.messageActInfo or self.plugin.debug:
			indigo.server.log(u"sendCommPort:            >> sending message: %s" % str(transmitDataAscii))
		transmitMessageHex = binascii.a2b_hex(transmitDataAscii)	
		conn.write(transmitMessageHex)
		self.waitForResponse(conn, False)
		
	#######################################
	# Check to see if serial port has any incoming information.
	#######################################
	
	def readCommPort(self, conn):
		receivedData = conn.read(25)
		if len(receivedData) != 0:
			receivedDataAscii = binascii.b2a_hex(receivedData)	
			if self.plugin.messageActInfo or self.plugin.debug:
				indigo.server.log(u"readCommPort:            << receive message: %s" % receivedDataAscii)
			self.processReceivedData(receivedDataAscii)		
			
	#######################################
	# Wait for reply to sent queued command to serial port.	
	#######################################
	
	def waitForResponse(self, conn, response):
		listenSerialReceiveCount = 5
			
		while listenSerialReceiveCount != 0:
			receivedData = conn.read(25)
			if len(receivedData) != 0:
				receivedDataAscii = binascii.b2a_hex(receivedData)	
				if self.plugin.messageActInfo or self.plugin.debug:
					indigo.server.log(u"waitForResponse:         << receive message: %s" % receivedDataAscii)
				self.processReceivedData(receivedDataAscii)
				return
			else:
				time.sleep(self.plugin.sleepBetweenIdlePoll)	
				listenSerialReceiveCount -= 1	
				
	#######################################
	# Send command directly to serial port, and bypass the command queue.
	#######################################
				
	def sendMsgDirect(self, transmitData):
		messageStartFlag = '7e'															# assemble transmit message
		messageNumber = binascii.b2a_hex(transmitData[1])
		alarmMessage = self.messageAlarmDict(messageNumber)
		transmitDataAscii = binascii.b2a_hex(transmitData)
		checksum = self.generateChecksum(transmitDataAscii)
		transmitDataAscii += checksum
		transmitDataAscii = self.insertBitStuffing(transmitDataAscii)					# substitute '7e' or '7d' within the transmit data stream
		transmitDataAscii = messageStartFlag + transmitDataAscii						# insert message start flag
		if self.messageACK == True:														# send transmit message data
			transmitMessage = binascii.a2b_hex(transmitDataAscii)		
			self.plugin.debugLog(u"sendMsgDirect:           >> sending message: %s,  %s,  %s"  % (messageNumber, alarmMessage, transmitDataAscii))
			self.conn.write(transmitMessage)			
				
	########################################
	# validate Recieved message
	########################################
	
	def processReceivedData(self, receivedDataAscii):
	#	self.plugin.debugLog(u"processReceivedData(): --  receive data: %s :" % receivedData)
		# verify valid message
		if re.match('7e', receivedDataAscii): 											# test for start of message flag '7e'	
			receivedDataAscii = self.removeBitStuffing(receivedDataAscii)				# test and remove bit stuffing from the received data stream
			messageDict = self.verifyChecksum(receivedDataAscii)						# test for valid message (correct message length and valid checksum)		
			messageLength = messageDict[0]												# read alarm message length
			messageNumber = messageDict[1]												# read alarm message type
			alarmMessage = self.messageAlarmDict(messageNumber)							# convert message number to message description	
			if self.receivedValidMessage == True:										# valid message received; process recieved message
				self.messageACK = True
				if self.plugin.messageActInfo or self.plugin.debug:
					indigo.server.log(u"processReceivedData:     || message: %s,  %s: %s" % (messageNumber, alarmMessage, receivedDataAscii))					
				self.decodeReceivedData(messageNumber, messageDict)						# decode and process vaild alarm message	
		else:
			self.plugin.errorLog(u"processReceivedData:     || invalid or incomplete message received.")
			self.sendMsgDirect(NAK)
			if self.plugin.messageActInfo or self.plugin.debug:
				indigo.server.log(u"decodeReceivedData:      >> sending message: NAK")			
	
	########################################
	# generate Checksum for Transmit message
	########################################
	
	def generateChecksum(self, transmitData):
		
		messageStart = 0																# extract message length
		messageLength = transmitData[messageStart:(messageStart+2)]
		dmessageLength = self.convertHexToDec(messageLength)							# determine start and end of message
		kmessageLength = (dmessageLength + 1)											# offset required to verify checksum (includes message length in calc)
		messageEnd = (messageStart + (2 * kmessageLength))
		message = transmitData[messageStart:messageEnd]
		messageDict = self.convertMessageToByteDict(kmessageLength, message)			# convert ascii message string into hex format dictionary
		self.plugin.debugLog(u"generateChecksum:        || message dictionary: %s" % messageDict)
		sum1 = 0																		# 16 bit Fletcher checksum algorithm
		sum2 = 0
		for i in range(0, len(messageDict)):
			dByte = self.convertHexToDec(messageDict[i])
			sum1 = (sum1 + dByte) % 255
			sum2 = (sum2 + sum1) % 255
		calcSum = self.convertDecToHex(sum1) + self.convertDecToHex(sum2)
		self.plugin.debugLog(u"generateChecksum:        || transmit data: %s,  checksum: %s,  length: %s,  dictionary: %s" % (transmitData, calcSum, dmessageLength, messageDict))
		return calcSum
		
	########################################
	# validate Recieved message Length and message Checksum
	########################################
	
	def verifyChecksum(self, receivedData):
		messageNumber = receivedData[4:6]
		alarmMessage = self.messageAlarmDict(messageNumber)
		partition = 1																	# update partition deivce state - statusLastFunction with the last received message	
		if partition in self.partitionList.keys():
			dev = self.partitionList[partition]
			dev.updateStateOnServer(key="statusLastFunction", value="%r  <<  %r  ** %r  "  % (alarmMessage, messageNumber, self.timestamp()))
		variableID = "receiveMessage"													# update indigo variable "caddx.receiveMessage" with last received message
		receiveMessageVariable = (u" << %s -- %s     %r  " % (messageNumber, alarmMessage, receivedData))
		self.updateVariable(variableID, receiveMessageVariable)
		self.receivedValidMessage = False
		self.acknownledgeFlag = False
		messageStart = 2																# extract message length
		messageLength = receivedData[messageStart:(messageStart+2)]
		dmessageLength = self.convertHexToDec(messageLength)
		self.plugin.debugLog(u"verifyChecksum:          || message length: %s  (decimal)" % dmessageLength)
		kmessageLength = (dmessageLength + 1)											# offset required to verify checksum (includes message length in calc)
		messageEnd = (messageStart + (2 * kmessageLength))								# determine start and end of message
		message = receivedData[messageStart:messageEnd]
		self.plugin.debugLog(u"verifyChecksum:          || message: %s" % message)
		messageChecksum1 = receivedData[messageEnd:(messageEnd + 2)]					# extract message checksum1 and checksum2 values
		messageChecksum2 = receivedData[(messageEnd + 2):(messageEnd + 4)]
		messageDict = self.convertMessageToByteDict(kmessageLength, message)			# convert ascii message string into hex format dictionary
		self.plugin.debugLog(u"verifyChecksum:          || message dictionary: %s" % messageDict)
		sum1 = 0																		# 16 bit Fletcher checksum algorithm
		sum2 = 0
		for i in range(0, len(messageDict)):
			dByte = self.convertHexToDec(messageDict[i])
			sum1 = (sum1 + dByte) % 255
			sum2 = (sum2 + sum1) % 255
		if sum1 == self.convertHexToDec(messageChecksum1) and sum2 == self.convertHexToDec(messageChecksum2):
			self.receivedValidMessage = True
			self.plugin.debugLog(u"verifyChecksum:          || received; valid message.")
		else:
			self.receivedValidMessage = False	
			indigo.server.log(u"verifyChecksum:          || received; invalid message.")
		return (messageDict)
		
	########################################
	# insert Bit Stuffing to Transmit message 
	########################################
	
	def insertBitStuffing(self, dataStream):
		messageStart = 0																# dataStream has no '7e' start message flag
		messageLength = dataStream[messageStart:(messageStart+2)]
		dmessageLength = self.convertHexToDec(messageLength)
		self.plugin.debugLog(u"insertBitStuffing:       || message length: %s  (decimal)" % dmessageLength)
		kmessageLength = (dmessageLength + 3)											# offset required to include checksum and message length in calc
		messageEnd = (messageStart + (2 * kmessageLength))								# determine start and end of message
		message = dataStream[messageStart:messageEnd]
		self.plugin.debugLog(u"insertBitStuffing:       || message: %s" % message)
		messageDict = self.convertMessageToByteDict(kmessageLength, message)			# convert ascii message string into hex format dictionary
		self.plugin.debugLog(u"insertBitStuffing:       || message dictionary: %s" % messageDict)
		dataStreamDict = {}																# loop thru data stream for '7e' or '7d' and replace with '7d5e' or 7d5d' respectively
		for key in messageDict:
			if messageDict[key] == '7e':
				dataStreamDict[key] = '7d5e'
			elif messageDict[key] == '7d':	
				dataStreamDict[key] ='7d5d'
			else:
				dataStreamDict[key] = messageDict[key]
		self.plugin.debugLog(u"insertBitStuffing:       || bit stuffed dataStream dictionary: %s" % dataStreamDict)
		dataStream = ""																	# reasseble data stream
		for key in dataStreamDict:
			dataStream += dataStreamDict[key]
		return dataStream
		
	########################################		
	# remove Stuffed Bits from  Received message	
	########################################
	
	def removeBitStuffing(self, dataStream):
		if re.search('7d5e', dataStream):
			for m in re.finditer('7d5e', dataStream):
				dataStream = re.sub('7d5e', '7e', dataStream)
			self.plugin.debugLog(u"removeBitStuffing:        || remove /'7d5e/' from data receive data stream: %s" %dataStream)
		if re.search('7d5d', dataStream):
			for m in re.finditer('7d5d', dataStream):
				dataStream = re.sub('7d5d', '7d', dataStream)
			self.plugin.debugLog(u"removeBitStuffing:        || remove /'7d5d/' from data receive data stream: %s" %dataStream)
		return dataStream	
					
	########################################
	# create Byte message dictionary for Transmit and Receive message processing
	########################################
	
	def convertMessageToByteDict(self, msgLength, message):
		byteDict = {}		
		byteLocation = 0	
		byte1Location = 0
		byte2Location = 1
		for i in range (0,msgLength):
			byte1 = message[byte1Location]
			byte2 = message[byte2Location]
			byteDict[byteLocation] = byte1 + byte2
			byteLocation += 1
			byte1Location += 2
			byte2Location += 2
		return byteDict
		
	########################################		
	# create Date/Time stamp for log event  message processing
	########################################
	
	def getCurrentDate(self):
		currentDate = time.asctime( time.localtime(time.time()) )
		return currentDate
		
	########################################
	# returns a friendly formated current timestamp for event logging and device status event updates
	########################################
	
	def timestamp(self):	
		timeLogged = time.localtime( time.time() )
		timeLogEvent = "%r/%r/%r   %02d:%02d:%02d" % (timeLogged[2], timeLogged[1], timeLogged[0], timeLogged[3], timeLogged[4], timeLogged[5] )
		return timeLogEvent		
		 
	########################################	 	
	# convert Hexidecimal value to a single Byte
	########################################
				
	def HexToByte(self, hexStr):
		bytes = []
		hexStr = ''.join( hexStr.split(" ") )
		for i in range(0, len(hexStr), 2):
			bytes.append(chr(int(hexStr[i:i+2],16)))
		return ' '.join(bytes)
		
	########################################	
	# convert a single Byte string to Hexidecimal value
	########################################
	
	def ByteToHex(self, byteStr):
		return ' '.join([ "%02X" % ord( x ) for x in byteStr])
		
	################################################################################	
	# Routines for Keypad Display Processing methods (decode partition snapshot status for LCD display messages)
	################################################################################
	
	########################################	
	# update Alarm Display from received "Partition Snapshot Message" method 
	########################################	
	
	def updateAlarmDisplay(self, varList, newByte):
		partition = 1																	# assumes control keypad is always in partition 1
		if partition in self.partitionList.keys():
			dev = self.partitionList[partition]
			
			partition1 = newByte[0]
			self.plugin.debugLog(u"updateAlarmDisplay:        display message byte: %s" % partition1)
			timestamp = self.timestamp()
			partitionState = 0
							
			# display lists
			displayLCDLine1List = ['Unknown', 'System Ready', 'System Not Ready', 'System Arming ...', 'Alarm Intruder', 'System Armed', 'Type code to', 'Alarm Intruder', 'System Arming ...', 'Alarm Intruder ', 'System Armed', 'Type code to', 'Alarm Intruder' ]
			displayLCDLine2List = ['Unknown', 'Type code to arm',  'For help, press ->', 'Zone(s) Bypassed', '       ', 'Zone(s) Bypassed', 'Disarm', '        ', 'All Zones Secure', '        ', ' Away Mode', 'Disarm', '        ' ]
		
			# display conditions
			displayLCDLine1 = " "
			displayLCDLine2 = " "
		
			# anaylsis partition state conditions for Common Mode  {Chime Mode Off)
			if partition1 == '00000011' :  												# Disarmed, System Ready, Chime Off
				partitionState = 1
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]
				self.breachedZone = " "													# Reset breached zone on disarm cycle		
			elif partition1 == '00000001' :												# Disarmed, System Not Ready, Chime Off
				partitionState = 2
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]			
			
			# anaylsis partition state conditions for Stay Mode	
			elif partition1 == '01001111' :												# Arming Stay Mode, System Ready, Chime Off
				partitionState = 3
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]		
			elif partition1 == '11001111' :												# Arming Stay Mode (exit delay timed), Security Alert Parimeter, Chime Off
				partitionState = 4
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = self.breachedZone		
			elif partition1 == '00001111' :												# Armed Stay Mode , System Secure, Chime Off
				partitionState = 5
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]	
			elif partition1 == '00101101'  or partition1 == '00101111':					# Armed Stay Mode (entry delay timed), Security Alert (entry zone), Chime Off
				partitionState = 6
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]	
			elif partition1 == '10001111' :												# Armed Stay Mode , Security Alert Parimeter, Chime Off
				partitionState = 7
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = self.breachedZone	
			
			# anaylsis partition state conditions for Away Mode
			elif partition1 == '01000111' :												# Arming Away Mode , System Ready, Chime Off
				partitionState = 8
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]
			elif partition1 == '11000101' or partition1 == '11000111' :					# Arming Away Mode (exit delay timed), Security Alert Parimeter, Chime Off
				partitionState = 9
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = self.breachedZone
			elif partition1 == '00000111' :												# Armed Away Mode, System Secure, Chime Off
				partitionState = 10
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]
			elif partition1 == '00100101'  or partition1 == '00100111' :				# Armed Away Mode (entry delay timed), Security Alert (entry zone), Chime Off
				partitionState = 11
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]
			elif partition1 == '10000101'  or partition1 == '10000111' :				# Armed Away Mode , Security Alert Parimeter, Chime Off
				partitionState = 12	
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = self.breachedZone
			
			##anaylsis partition state conditions for Common Mode  {Chime Mode On)	
			elif partition1 == '00010011' :  											# Disarmed, System Ready, Chime Off
				partitionState = 1
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]
				self.breachedZone = " "													# Reset breached zone on disarm cycle
			elif partition1 == '00010001' :												# Disarmed, System Not Ready, Chime On
				partitionState = 2
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]
			
			# anaylsis partition state conditions for Stay Mode	
			elif partition1 == '01011111' :												# Arming Stay Mode, System Ready, Chime On
				partitionState = 3
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]
			elif partition1 == '11011111' :												# Arming Stay Mode (exit delay timed), Security Alert Parimeter, Chime On
				partitionState = 4
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = self.breachedZone
			elif partition1 == '00011111' :												# Armed Stay Mode , System Secure, Chime On
				partitionState = 5
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]
			elif partition1 == '00111101' or partition1 == '00111111' :					# Armed Stay Mode (entry delay timed), Security Alert (entry zone), Chime On
				partitionState = 6
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]
			elif partition1 == '10011111' :												# Armed Stay Mode , Security Alert Parimeter, Chime On
				partitionState = 7
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = self.breachedZone
			
			# anaylsis partition state conditions for Away Mode
			elif partition1 == '01010111' :												# 	Arming Away Mode , System Ready, Chime On
				partitionState = 8
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]
			elif partition1 == '11010101'  or partition1 == '11010111':					# Arming Away Mode (exit delay timed), Security Alert Parimeter, Chime On
				partitionState = 9
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = self.breachedZone
			elif partition1 == '00010111' :												# Armed Away Mode, System Secure, Chime On
				partitionState = 10
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]
			elif partition1 == '00110101' or partition1 == '00110111' :					# Armed Away Mode (entry delay timed), Security Alert (entry zone), Chime On
				partitionState = 11
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = displayLCDLine2List[partitionState]
			elif partition1 == '10010101' or partition1 == '10010111' :					# Armed Away Mode , Security Alert Parimeter, Chime On
				partitionState = 12
				displayLCDLine1 = displayLCDLine1List[partitionState]
				displayLCDLine2 = self.breachedZone
				
			# update Partition State variables
			partitionStateList = ['Multiple State Changes', 'Disarmed', 'Not Ready', 'Arming (exit)', 'Arming Not Ready', 'Armed Stay', 'Alarm (entry)', 'ALARM Intruder', 'Arming (exit)', 'ALARM Intruder', 'Armed Away',  'Alarm (entry)', 'ALARM Intruder' ]
			partitionConditionList = ['multipleChanges', 'disarmed', 'notReady', 'armingExit', 'armingNotReady', 'armedStay', 'alarmEntry', 'alarmIntruder', 'armingExit', 'alarmIntruder', 'armedAway',  'alarmEntry', 'alarmIntruder' ]
			pstate = partitionStateList[partitionState]
			pcondition = partitionConditionList[partitionState]
	#		localPropsCopy = dev.pluginProps
			if dev.states['delayExpirationWarning'] == "1" :
				if self.plugin.enableSpeakPrompts:
					indigo.server.speak(sayExitDelayWarning)	
				if self.plugin.partitionActInfo or self.plugin.debug:
					indigo.server.log(u"partition 1:       \'Warning - exit delay expires in 10 sec!\' ")
			else:	
	#			localPropsCopy[u"partitionState"] = pstate
	#			localPropsCopy[u"lastStateChange"] = "Partition (1) %r  ** %s " % (pstate, self.timestamp())
	#			dev.replacePluginPropsOnServer(localPropsCopy)
				dev.updateStateOnServer(key="partitionState", value=pstate)
				dev.updateStateOnServer(key="partitionStatus", value=pcondition)
				dev.updateStateOnServer(key="lastStateChange", value= "Partition (1) %r  ** %s " % (pstate, self.timestamp()))
				if self.plugin.partitionActInfo or self.plugin.debug:
					indigo.server.log(u"partition 1:       \'%s!\' " % pstate)
			
			# update Display Messages for Keypad device
			keypad = int(dev.pluginProps['associatedKeypad'])
			if keypad in self.keypadList.keys():
				dev = self.keypadList[keypad]
				dev.updateStateOnServer(key="LCDMessageLine1", value=displayLCDLine1)
				dev.updateStateOnServer(key="LCDMessageLine2", value=displayLCDLine2)
				if self.plugin.partitionActInfo or self.plugin.debug:
					indigo.server.log(u"keypad %s:           LCD message line 1: \"%s\",  LCD message line 2: \"%s\"" % (keypad, displayLCDLine1, displayLCDLine2))
			
			# update indigo variable "partitionState"  from Display Conditions above
			variableID = "partitionState"
			partitionStateVariable = (u"%s   ** %s "% (pstate, self.timestamp()))
			self.updateVariable(variableID, partitionStateVariable)		
				
	########################################								
	# update Breached Zone for Alarm Display from received "Log Event Message" method 
	########################################
			
	def updateAlarmDisplayZoneBreached(self, partition, zoneBreached):
		if partition in self.partitionList.keys():
			dev = self.partitionList[partition]
			keypad = int(dev.pluginProps['associatedKeypad'])
			if keypad in self.keypadList.keys():
				dev = self.keypadList[keypad]
				displayLCDLine1 = "Security Breach"
				displayLCDLine2 = zoneBreached
				dev.updateStateOnServer(key="LCDMessageLine1", value=displayLCDLine1)
				dev.updateStateOnServer(key="LCDMessageLine2", value=displayLCDLine2)
				if self.plugin.partitionActInfo or self.plugin.debug:
					indigo.server.log(u"keypad %s:           LCD message line 1: \"%s\",   LCD message line 2: \"%s\"" % (displayLCDLine1, displayLCDLine2))
			if self.plugin.enableSpeakPrompts:
				say = sayZoneTripped + zoneBreached
				indigo.server.speak(say)
			
	########################################			
	# update Breached Zone Name for Alarm Display from device config ui "Zone Name" method
	########################################
	 		
	def updateZoneNameBreached(self, zone):
		zoneDisplayName = ""		
		if zone in self.zoneList.keys():
			dev = self.zoneList[zone]
			localPropsCopy = dev.pluginProps
			zoneDisplayName = localPropsCopy['zoneDisplayName']
			if zoneDisplayName == None:
				zoneDisplayName = 'zone %r' % zone	
		return zoneDisplayName	
													
	################################################################################	
	# Routines for Zone Group Type Processing methods (decode zone group type configuration and add zone description)
	################################################################################
	
	########################################
	# determine the zone group type number	
	########################################
	
	def zoneGroupType(self, zoneTypeDict):
		if zoneTypeDict == '000000000001001111110100' :
			zoneType = '01'
		elif zoneTypeDict == '000000100001001111000000' :
			zoneType = '02'		
		elif zoneTypeDict == '000100000001101111110000' :
			zoneType = '03'	
		elif zoneTypeDict == '000110000001001111110000' :
			zoneType = '04'	
		elif zoneTypeDict == '010110000001001111110000' :
			zoneType = '05'	
		elif zoneTypeDict == '000000000001101111110000' :
			zoneType = '06'	
		elif zoneTypeDict == '000000100000000011000000' :
			zoneType = '07'
		elif zoneTypeDict == '000000010000010111000100' :
			zoneType = '08'	
		elif zoneTypeDict == '001000000001101111110000' :
			zoneType = '09'	
		elif zoneTypeDict == '000010100001000011000000' :
			zoneType = '10'		
		elif zoneTypeDict == '000001000000000000000000' :
			zoneType = '11'		
		elif zoneTypeDict == '010110000001001111111000' :
			zoneType = '12'	
		elif zoneTypeDict == '000000001001101111110000' :
			zoneType = '13'
		elif zoneTypeDict == '000100000011101111110000' :
			zoneType = '14'	
		elif zoneTypeDict == '010110000011001111110000' :
			zoneType = '15'	
		elif zoneTypeDict == '000000000011101111110000' :
			zoneType = '16'	
		elif zoneTypeDict == '000100000001101111110010' :
			zoneType = '17'	
		elif zoneTypeDict == '010110000001001111110010' :
			zoneType = '18'	
		elif zoneTypeDict == '000000000001101111110010' :
			zoneType = '19'
		elif zoneTypeDict == '001000000001101111110010' :
			zoneType = '20'	
		elif zoneTypeDict == '000010100001000111000000' :
			zoneType = '21'		
		elif zoneTypeDict == '000010100001000111000000' :
			zoneType = '22'	
		elif zoneTypeDict == '000010100001000111000000' :
			zoneType = '23'
		elif zoneTypeDict == '000000010000010111000100' :
			zoneType = '24'	
		elif zoneTypeDict == '100010100001100000000000' :
			zoneType = '25'
		elif zoneTypeDict == '011010000001001111110000' :
			zoneType = '26'	
		elif zoneTypeDict == '010110000101001111110000' :
			zoneType = '27'		
		elif zoneTypeDict == '001000000101101111110000' :
			zoneType = '28'	
		elif zoneTypeDict == '010110000001001111110000' :
			zoneType = '29'
		elif zoneTypeDict == '000100000001101111110000' :
			zoneType = '30'
		else:
			zoneType = 'no zone group match'	
		return zoneType
	
	########################################	
	# determine the zone group type description label	
	########################################
	
	def zoneGroupDescription(self, zoneTypeDict):
		if zoneTypeDict == '000000000001001111110100' :
			zoneType = '01'
			zoneDescription = 'Day/Night Alarm'
		elif zoneTypeDict == '000000100001001111000000' :
			zoneType = '02'	
			zoneDescription = 'Panic Alarm'	
		elif zoneTypeDict == '000100000001101111110000' :
			zoneType = '03'	
			zoneDescription = 'Entry/Exit (delay1)'
		elif zoneTypeDict == '000110000001001111110000' :
			zoneType = '04'	
			zoneDescription = 'Interior Alarm'	
		elif zoneTypeDict == '010110000001001111110000' :
			zoneType = '05'	
			zoneDescription = 'Interior Alarm'
		elif zoneTypeDict == '000000000001101111110000' :
			zoneType = '06'	
			zoneDescription = 'Perimeter Alarm'	
		elif zoneTypeDict == '000000100000000011000000' :
			zoneType = '07'
			zoneDescription = 'Silent Panic'	
		elif zoneTypeDict == '000000010000010111000100' :
			zoneType = '08'	
			zoneDescription = 'Fire Alarm'	
		elif zoneTypeDict == '001000000001101111110000' :
			zoneType = '09'	
			zoneDescription = 'Entry/Exit (delay2)'
		elif zoneTypeDict == '000010100001000011000000' :
			zoneType = '10'	
			zoneDescription = 'Tamper Alarm'	
		elif zoneTypeDict == '000001000000000000000000' :
			zoneType = '11'	
			zoneDescription = 'Arm/Disarm (momentary keyswitch)'	
		elif zoneTypeDict == '010110000001001111111000' :
			zoneType = '12'	
			zoneDescription = 'Interior Alarm (cross zone)'	
		elif zoneTypeDict == '000000001001101111110000' :
			zoneType = '13'
			zoneDescription = 'Perimeter Alarm (entry guard)'
		elif zoneTypeDict == '000100000011101111110000' :
			zoneType = '14'	
			zoneDescription = 'Entry/Exit (delay1, group bypass)'
		elif zoneTypeDict == '010110000011001111110000' :
			zoneType = '15'	
			zoneDescription = 'Interior Alarm (group bypass)'	
		elif zoneTypeDict == '000000000011101111110000' :
			zoneType = '16'	
			zoneDescription = 'Perimeter Alarm (group bypass)'	
		elif zoneTypeDict == '000100000001101111110010' :
			zoneType = '17'	
			zoneDescription = 'Arm/Disarm (maintained keyswitch)'
		elif zoneTypeDict == '010110000001001111110010' :
			zoneType = '18'	
			zoneDescription = 'Entry/Exit (delay1, force armable)'
		elif zoneTypeDict == '000000000001101111110010' :
			zoneType = '19'
			zoneDescription = 'Entry/Exit (delay2, force armable)'
		elif zoneTypeDict == '001000000001101111110010' :
			zoneType = '20'	
			zoneDescription = 'Entry/Exit (delay2, chime enabled)'	
		elif zoneTypeDict == '000010100001000111000000' :
			zoneType = '21"'	
			zoneDescription = 'Gas Detected or Low/High Temp'	
		elif zoneTypeDict == '000010100001000111000000' :
			zoneType = '22'	
			zoneDescription = 'Freeze Alarm'	
		elif zoneTypeDict == '000010100001000111000000' :
			zoneType = '23'
			zoneDescription = 'Interior Alarm'
		elif zoneTypeDict == '000000010000010111000100' :
			zoneType = '24'	
			zoneDescription = 'Perimeter Alarm'	
		elif zoneTypeDict == '100010100001100000000000' :
			zoneType = '25'
			zoneDescription = 'Interior Alarm'	
		elif zoneTypeDict == '011010000001001111110000' :
			zoneType = '26'	
			zoneDescription = 'Burglary Alarm (supervised local)'
		elif zoneTypeDict == '010110000101001111110000' :
			zoneType = '27'
			zoneDescription = 'Perimeter Alarm (activity monitor)'		
		elif zoneTypeDict == '001000000101101111110000' :
			zoneType = '28'	
			zoneDescription = 'Perimeter Alarm (request to exit)'
		elif zoneTypeDict == '010110000001001111110000' :
			zoneType = '29'
			zoneDescription = 'Interior Alarm (request access to entry)'	
		elif zoneTypeDict == '000100000001101111110000' :
			zoneType = '30'
			zoneDescription = 'Medical Alarm'
		else:
			zoneDescription = 'no zone group match'	
		return zoneDescription		
																							
	################################################################################	
	# Routines for Zone State Update method  (update zoneState value condition from received "Zone Status Message")
	################################################################################
	
	########################################
	# determine and update zoneState value condition 
	########################################
	
	def updateZoneStateCondition(self, dev, zoneNum, zoneCondition):
		
		# test if zoneDisplayName exists in pluginProps dictionary
		zone = self.adjustZoneNumberDigits(zoneNum)
		if dev.pluginProps['zoneDisplayName']:
			zoneName = dev.pluginProps['zoneDisplayName']
		else:
			zoneName = "Zone " + zone
		newByte = zoneCondition
				
		# test for condition of zoneState device state for Group Trigger Plugin
		if zoneCondition == '00000001' :
			zoneState = "triggered"
			zoneCondition = 0
		elif zoneCondition == '00000010' :
			zoneState = "tampered"
			zoneCondition = 1
		elif zoneCondition == '00000100' :
			zoneState = "trouble"	
			zoneCondition = 2
		elif zoneCondition == '00001000' :
			zoneState = "bypassed"
			zoneCondition = 3	
		elif zoneCondition == '00010000' :
			zoneState = "inhibited"
			zoneCondition = 4
		elif zoneCondition == '00100000' :
			zoneState = "lowBattery"
			zoneCondition = 5
		elif zoneCondition == '01000000' :
			zoneState = "supervisionLoss"
			zoneCondition = 6
		elif zoneCondition == '00000000' :
			zoneState = "normal"
			zoneCondition = 7
		else:	
			zoneState = "multipleChanges"
			zoneCondition = 8
			
		# update zoneState device state
		zoneStateList =  ['Triggered', 'Tampered', 'Trouble', 'Bypassed', 'Inhibited (Force Armed)', 'Low Battery', 'Loss Of Supervision', 'Normal', 'Multiple State Changes'] 	
		stateList =  [True, True, True, False, False, False, False, False, False]																
		zstate = zoneStateList[zoneCondition]
		state = stateList[zoneCondition]
		dev.updateStateOnServer(key="zoneState", value=zoneState)
		dev.updateStateOnServer(key="onOffState", value=state)	
		if self.plugin.zoneActInfo or self.plugin.debug:
			indigo.server.log(u"zone %s:          \'%s!\' {%s }" % (zone, zstate, zoneName))	
		
		# update partition lastZoneTrigger device state and variable
		if zoneState == "triggered" :
			partition = 1
			if partition in self.partitionList.keys():
				dev = self.partitionList[partition]
				dev.updateStateOnServer(key="lastZoneTrigger", value="Zone %s  ** %s " % (zone, self.timestamp()))
			# update indigo variable "lastZoneTrigger"
				variableID = "lastZoneTrigger"
				lastZoneTriggerVariable = (u"Zone %s  ** %s " % (zone, self.timestamp()))
				self.updateVariable(variableID, lastZoneTriggerVariable)
		
	################################################################################	
	# Routines for Communication Status Update methods (update comm status in plugin config preferences)
	################################################################################

	
	########################################
	# update: comm state active 
	########################################
	
	def commStatusUp(self):
		self.plugin.pluginPrefs[u'portStatus'] = 'Port (opened)'
		self.plugin.pluginPrefs[u'communicationFailure'] = False	
		self.plugin.pluginPrefs[u'activeCommunication'] = True	
		self.plugin.pluginPrefs[u'panelStatus'] = "Connected  ** %s"  % self.timestamp()
		variableID = "portStatus"
		portStatusVariable = (u"Port (opened)")
		self.updateVariable(variableID, portStatusVariable)
		variableID = "panelStatus"
		panelStatusVariable = (u"Connected  ** %s " % self.timestamp())
		self.updateVariable(variableID, panelStatusVariable)
		partition = 1																	# update partition status variables config ui and device state
		if partition in self.partitionList.keys():
			dev = self.partitionList[partition]
	#		dev.updateStateOnServer(key="partitionState", value="Connected")
			dev.updateStateOnServer(key="securityState", value="Connected")
			dev.updateStateOnServer(key="lastStateChange", value= "Partition 1  Connected  ** %s" % self.timestamp())
			variableID = "securityState"
			securityStateVariable = (u"Connected")
			self.updateVariable(variableID, securityStateVariable)
			variableID = "lastStateChange"
			lastStateChangeVariable = (u"Partition 1  Connected  ** %s" % self.timestamp())
			self.updateVariable(variableID, lastStateChangeVariable)
		
	########################################
	# update: comm state down  	
	########################################
	
	def commStatusDown(self):
		self.plugin.pluginPrefs[u'portStatus'] = 'Port(closed)'
		self.plugin.pluginPrefs[u'communicationFailure'] = True
		self.plugin.pluginPrefs[u'lastFailureTime'] = "Failed ** %s" % self.timestamp()	
		self.plugin.pluginPrefs[u'activeCommunication'] = False	
		self.plugin.pluginPrefs[u'panelStatus'] = "Disconnected  ** %s"  % self.timestamp()
		self.plugin.pluginPrefs[u'synchronised'] = False
		variableID = "portStatus"
		portStatusVariable = (u"Port (closed)")
		self.updateVariable(variableID, portStatusVariable)
		variableID = "panelStatus"
		panelStatusVariable = (u"Disconnected  ** %s " % self.timestamp())
		self.updateVariable(variableID, panelStatusVariable)	
		partition = 1																	# update partition status variables config ui and device state
		if partition in self.partitionList.keys():
			dev = self.partitionList[partition]
	#		dev.updateStateOnServer(key="partitionState", value="Disconnected")
			dev.updateStateOnServer(key="securityState", value="Disconnected")
			dev.updateStateOnServer(key="lastStateChange", value=  "Partition 1  Disconnected  ** %s" % self.timestamp())
			variableID = "securityState"
			securityStateVariable = (u"Disconnected")
			self.updateVariable(variableID, securityStateVariable)
			variableID = "lastStateChange"
			lastStateChangeVariable = (u"Partition 1  Disconnected  ** %s" % self.timestamp())
			self.updateVariable(variableID, lastStateChangeVariable)
	
	########################################
	# update: perdiodic test with comm continuity check to security system  	
	########################################
	
	def commContinuityCheck(self, timeNow):
		if self.plugin.watchdogTimerPeriod != 0:										# test if watchdog timer disabled
			if self.plugin.pluginPrefs[u'isSynchronising'] == False:					# abort if Synchronising Database process running
				if timeNow >= self.watchdogTimer:										# test if watchdog timer expired
					if self.plugin.messageProcessInfo or self.plugin.debug:
						indigo.server.log(u"watchdog timer triggered:        Interface Configuration Message: %s" % timeNow)
					if self.plugin.pluginPrefs[u'firmware'] == '*****':					# test for communication failure, update plugin prefs
						self.plugin.pluginPrefs[u'portStatus'] = "Port (open failure)"
						self.plugin.pluginPrefs[u'communicationFailure'] = True
						self.plugin.pluginPrefs[u'lastFailureTime'] = "Failed ** %s" % self.timestamp()
						self.errorCountComm += 1										# if error , increment counter
						indigo.server.log(u"error: communication continuity test FAILURE to Caddx Security System, error count %s" % self.errorCountComm)
					self.watchdogTimer = timeNow + self.plugin.watchdogTimerPeriod		# reset watchdog timer
					self.plugin.pluginPrefs[u'firmware'] = '*****'						# reset firmware to test communication loop
					self.sendMsgToQueue(interfaceConfigurationRequest)						# command action : Interface Configuration Request
			else:
				return
		else:
			return		
			
	########################################
	# adjust the log event number to 3 digits 	
	########################################
	
	def adjustLogEventNumberDigits(self, logEventNum):
		key = int(logEventNum)
		if key <= 9:
			logEventNum = "00" + str(key)
		elif key <= 99:
			logEventNum = "0" + str(key)
		else:	
			logEventNum = str(key)
		return logEventNum
			
	########################################
	# adjust the zone number to 2 digits   	
	########################################
			
	def adjustZoneNumberDigits(self, zone):		
		key = int(zone)
		if key <= 9:
			zone = "00" + str(key)
		elif key <= 99:
			zone = "0" + str(key)	
		else:
			zone = str(key)
		return zone
	
	################################################################################	
	# Routines for Received Message Processing method (decode Received messages and call update process)
	################################################################################
	
	########################################
	# process received messages and call associated decode and update method
	########################################
	
	def decodeReceivedData(self, messageNumber, messageDict):
		if messageNumber == "01":												# Interface Configuration Message
			self._interfaceConfigurationMessage(messageDict)
		elif messageNumber == "03":												# Zone Name Message
			self._zoneNameMessage(messageDict)				
		elif messageNumber == "04":												# Zone Status Message
			self._zoneStatusMessage(messageDict)
		elif messageNumber == "05":												# Zone Snapshot Message
			self._zoneSnapshotMessage(messageDict)
		elif messageNumber == "06":												# Partition Status Message
			self._partitionStatusMessage(messageDict)
		elif messageNumber == "07":												# Partition Snapshot Message
			self._partitionSnapshotMessage(messageDict)
		elif messageNumber == "08":												# System Status Message
			self._systemStatusMessage(messageDict)
		elif messageNumber == "09":												# X-10 Message Received
			self._x10MessageReceived(messageDict)
		elif messageNumber == "0a":												# Log Event Message
			self._logEventMessage(messageDict)
		elif messageNumber == "0b":												# Keypad Message Received
			self._keypadMessageReceived(messageDict)
		elif messageNumber == "10":												# Program Data Reply
			self._programDataReply(messageDict)
		elif messageNumber == "12":												# User Information Reply
			self._userInformationReply(messageDict)	
		elif messageNumber == "1c":												# Command / Request Failed
			pass
		elif messageNumber == "1d":												# Positive Acknownledge
			pass
		elif messageNumber == "1e":												# Negative Acknownledge
			pass
		elif messageNumber == "1f":												# Message Rejected
			pass
		elif messageNumber == "81":												# Interface Configuration Message (with acknownledge request)
			self.sendMsgDirect(ACK)
			if self.plugin.messageActInfo or self.plugin.debug:
				indigo.server.log(u"decodeReceivedData:      >> sending message: ACK")
			self._interfaceConfigurationMessage(messageDict)
		elif messageNumber == "83":												# Zone Name Message (with acknownledge request)
			self.sendMsgDirect(ACK)
			if self.plugin.messageActInfo or self.plugin.debug:
				indigo.server.log(u"decodeReceivedData:      >> sending message: ACK")
			self._zoneNameMessage(messageDict)				
		elif messageNumber == "84":												# Zone Status Message (with acknownledge request)
			self.sendMsgDirect(ACK)
			if self.plugin.messageActInfo or self.plugin.debug:
				indigo.server.log(u"decodeReceivedData:      >> sending message: ACK")
			self._zoneStatusMessage(messageDict)
		elif messageNumber == "85":												# Zone Snapshot Message (with acknownledge request)
			self.sendMsgDirect(ACK)
			if self.plugin.messageActInfo or self.plugin.debug:
				indigo.server.log(u"decodeReceivedData:      >> sending message: ACK")
			self._zoneSnapshotMessage(messageDict)
		elif messageNumber == "86":												# Partition Status Message (with acknownledge request)
			self.sendMsgDirect(ACK)
			if self.plugin.messageActInfo or self.plugin.debug:
				indigo.server.log(u"decodeReceivedData:      >> sending message: ACK")
			self._partitionStatusMessage(messageDict)
		elif messageNumber == "87":												# Partition Snapshot Message (with acknownledge request)
			self.sendMsgDirect(ACK)
			if self.plugin.messageActInfo or self.plugin.debug:
				indigo.server.log(u"decodeReceivedData:      >> sending message: ACK")
			self._partitionSnapshotMessage(messageDict)
		elif messageNumber == "88":												# System Status Message (with acknownledge request)
			self.sendMsgDirect(ACK)
			if self.plugin.messageActInfo or self.plugin.debug:
				indigo.server.log(u"decodeReceivedData:      >> sending message: ACK")
			self._systemStatusMessage(messageDict)
		elif messageNumber == "89":												# X-10 Message Received (with acknownledge request)
			self.sendMsgDirect(ACK)
			if self.plugin.messageActInfo or self.plugin.debug:
				indigo.server.log(u"decodeReceivedData:      >> sending message: ACK")
			self._x10MessageReceived(messageDict)
		elif messageNumber == "8a":												# Log Event Message (with acknownledge request)
			self.sendMsgDirect(ACK)
			if self.plugin.messageActInfo or self.plugin.debug:
				indigo.server.log(u"decodeReceivedData:      >> sending message: ACK")
			self._logEventMessage(messageDict)
		elif messageNumber == "8b":												# Keypad Message Received (with acknownledge request)
			self.sendMsgDirect(ACK)
			if self.plugin.messageActInfo or self.plugin.debug:
				indigo.server.log(u"decodeReceivedData:      >> sending message: ACK")
			self._keypadMessageReceived(messageDict)
		else:
			self.sendMsgDirect(CAN)
			indigo.server.log(u"startComm:        error received message number: %r,  (not valid or not supported)." % messageNumber)
		
	########################################
	# process "Interface Configuration Message"
	########################################
	
	def _interfaceConfigurationMessage(self, dataDict):
		# extract each ASCII word from the system status message
		kmessageLength = dataDict [0]
		kmessageNumber = dataDict [1]
		kalarmMessage = self.messageAlarmDict(kmessageNumber)							# convert message number to message description
		bmessageLength = self.convertHexToDec(kmessageLength)							# convert message length from hex to dec
		
		panel = int(self.systemId)														# system panel type number for updating state values
		messageStart = 6																# start pointer for valid message data (exclude message length and message number)
				
		# verified message being processed notice
		if self.plugin.messageProcessInfo or self.plugin.debug:
			indigo.server.log(u"processing message:         %s,  system model: %s,  length: %r" % (kalarmMessage, self.model, bmessageLength))

		# convert hex to binary map
		dmessageLength = int(self.convertHexToDec(kmessageLength) -5)					# valid data message length
		binterfaceConfigurationMessageDict = self.convertByteDictToBinaryMap(messageStart, dmessageLength, dataDict)
		
		# convert hex to ascii
		panelFirmware = "%s%s%s%s" % (binascii.a2b_hex(dataDict[2]), binascii.a2b_hex(dataDict[3]), binascii.a2b_hex(dataDict[4]), binascii.a2b_hex(dataDict[5]))
	
		# verify message word value and binary mapping
		self.plugin.debugLog(u"interfaceConfigurationMessage:        interface configuration message dictionary: %r" % dataDict)
		self.plugin.debugLog(u"interfaceConfigurationMessage:        interface configuration message bit map dictionary: %r" % binterfaceConfigurationMessageDict)
				
		# parameter byte definition lists
		transitionMessageFlags1List = ["partitionSnapshotMessage", "partitionStatusMessage", "zoneSnapshotMessage", "zoneStatusMessage", "zreservedBit3TransitionMessageFlags1", "zreservedBit2TransitionMessageFlags1", "interfaceConfigurationMessage", "zreservedBit0TransitionMessageFlags1"]
		transitionMessageFlags2List = ["zreservedBit7TransitionMessageFlags2", "zreservedBit6TransitionMessageFlags2", "zreservedBit5TransitionMessageFlags2", "zreservedBit4TransitionMessageFlags2", "keypadMessageReceived", "logEventReceived", "receivedX10Message", "systemStatusMessage"]
		requestCommandFlags1List = ["partitionSnapshotRequest", "partitionStatusRequest", "zoneSnapshotRequest", "zoneStatusRequest", "zoneNameRequest", "zreservedBit2RequestCommandFlags1", "interfaceConfigurationRequest", "zreservedBit0RequestCommandFlags1"]
		requestCommandFlags2List = ["zreservedBit7RequestCommandFlags2", "zreservedBit6RequestCommandFlags2", "zreservedBit5RequestCommandFlags2", "keypadTerminalModeRequest", "sendKeypadTextMessage", "logEventRequest", "sendX10Message", "systemStatusRequest"]
		requestCommandFlags3List = ["setUserAuthorisationCommandWithoutPin", "setUserAuthorisationCommandWithPin", "setUserCodeCommandWithoutPin", "setUserCodeCommandWithPin", "userInformationRequestWithoutPin", "userInformationRequestWithPin", "programDataCommand", "programDataRequest"]
		requestCommandFlags4List = ["zoneBypassToggle", "secondaryKeypadFunction", "primaryKeypadFunctionWithoutPin", "primaryKeypadFunctionWithPin", "setClockCalenderCommand", "storeCommunicationEventCommand", "zreservedBit1RequestCommandFlags4", "zreservedBit0RequestCommandFlags4"]
		
		# update Interface Configuration Status Plugin Preferences "Interface Configuration Message"
		if binterfaceConfigurationMessageDict != None:
			self.plugin.pluginPrefs[u"firmware"] = panelFirmware
			self.updateInterfaceConfigPluginPrefs(transitionMessageFlags1List, binterfaceConfigurationMessageDict[0])
			self.updateInterfaceConfigPluginPrefs(transitionMessageFlags2List, binterfaceConfigurationMessageDict[1])
			self.updateInterfaceConfigPluginPrefs(requestCommandFlags1List, binterfaceConfigurationMessageDict[2])
			self.updateInterfaceConfigPluginPrefs(requestCommandFlags2List, binterfaceConfigurationMessageDict[3])
			self.updateInterfaceConfigPluginPrefs(requestCommandFlags3List, binterfaceConfigurationMessageDict[4])
			self.updateInterfaceConfigPluginPrefs(requestCommandFlags4List, binterfaceConfigurationMessageDict[5])
			if self.plugin.messageProcessInfo or self.plugin.debug:
				indigo.server.log(u"update interface configuration:        plugin preferences sucessfully updated with alarm panel interface configuration settings.")
			
			# copy "Transition Based Broadcast" message state values that are currently "enabled" to Indigo Log	
			if self.suspendInterfaceConfigMessageDisplay == False:
				indigo.server.log(u"Caddx NetworX Security System:        System Model: %s        Firmware: %s " % (self.model, panelFirmware))
				indigo.server.log(u"")
				localPrefsCopy = self.plugin.pluginPrefs
				indigo.server.log(u"Transition Based Broadcast messages currently enabled:")
				prefsInterfaceConfigList = ["interfaceConfigurationMessage", "zoneStatusMessage", "zoneSnapshotMessage", "partitionStatusMessage", "partitionSnapshotMessage",
											 "systemStatusMessage", "receivedX10Message", "logEventReceived", "keypadMessageReceived"]	
				item = 0
				for i in prefsInterfaceConfigList:
					var = localPrefsCopy[prefsInterfaceConfigList[item]]
					if var == '1' :
						indigo.server.log(u"    . . %s " % prefsInterfaceConfigList[item])
					item += 1
				
				# copy "Command / Request" message state values that are currently "enabled" to Indigo Log	
				indigo.server.log(u"")
				indigo.server.log(u"Command / Request messages currently enabled:")
				prefsInterfaceConfigList = ["interfaceConfigurationRequest", "zoneNameRequest",
											 "zoneStatusRequest", "zoneSnapshotRequest", "partitionStatusRequest", "partitionSnapshotRequest", "systemStatusRequest", "sendX10Message",
											 "logEventRequest", "sendKeypadTextMessage", "keypadTerminalModeRequest", "programDataRequest", "programDataCommand", "userInformationRequestWithPin",							 
											 "userInformationRequestWithoutPin", "setUserCodeCommndWithPin", "setUserCodeCommndWithoutPin", "setUserAuthorisationCommandWithPin", 						 
											 "setUserAuthorisationCommandWithoutPin", "storeCommunicationEventCommand", "setClockCalenderCommand", "primaryKeypadFunctionWithPin",
											 "primaryKeypadFunctionWithoutPin", "secondaryKeypadFunction", "zoneBypassToggle"]	
				item = 0
				for i in prefsInterfaceConfigList:
					var = localPrefsCopy[prefsInterfaceConfigList[item]]
					if var == '1' :
						indigo.server.log(u"    . . %s " % prefsInterfaceConfigList[item])
					item += 1		
				self.suspendInterfaceConfigMessageDisplay = True
	
		# update Interface Configuration Status States from received "Interface Configuration Message"
		if binterfaceConfigurationMessageDict != None:
			if panel in self.panelList.keys():
				dev = self.panelList[panel]
				dev.updateStateOnServer(key=u'firmware', value=panelFirmware)
				self.updateInterfaceConfigStates(dev, transitionMessageFlags1List, binterfaceConfigurationMessageDict[0])
				self.updateInterfaceConfigStates(dev, transitionMessageFlags2List, binterfaceConfigurationMessageDict[1])
				self.updateInterfaceConfigStates(dev, requestCommandFlags1List, binterfaceConfigurationMessageDict[2])
				self.updateInterfaceConfigStates(dev, requestCommandFlags2List, binterfaceConfigurationMessageDict[3])
				self.updateInterfaceConfigStates(dev, requestCommandFlags3List, binterfaceConfigurationMessageDict[4])
				self.updateInterfaceConfigStates(dev, requestCommandFlags4List, binterfaceConfigurationMessageDict[5])
				if self.plugin.messageProcessInfo or self.plugin.debug:
					indigo.server.log(u"update interface configuration:        device state records sucessfully updated with alarm panel interface configuration settings.")
			else:
				self.plugin.debugLog(u"update interface configuration:        no record in indigo database (device - state) for alarm panel interface configuration settings.")
		else:
			self.plugin.debugLog(u"update interface configuration:        no device state records in message dictionary for alarm panel interface configuration settings update.")
					
	########################################
	# process "Zone Name Message"
	########################################
	
	def _zoneNameMessage(self, dataDict):
		# extract each ASCII word from the system status message
		kmessageLength = dataDict [0]
		kmessageNumber = dataDict [1]
		kalarmMessage = self.messageAlarmDict(kmessageNumber)							# convert message number to message description
		bmessageLength = self.convertHexToDec(kmessageLength)							# convert message length from hex to dec
		
		kzoneNumber = dataDict [2]
		kzoneName1 = dataDict[3] + dataDict[4] + dataDict[5] + dataDict[6] + dataDict[7] + dataDict[8] + dataDict[9] + dataDict[10]
		kzoneName2 = dataDict[11] + dataDict[12] + dataDict[13] + dataDict[14] + dataDict[15] + dataDict[16] + dataDict[17] + dataDict[18]
		kzoneName = kzoneName1 + kzoneName2
		dzoneNumber = self.convertHexToDec(kzoneNumber)									# convert zone number from hex to dec for indexing
		dzoneNumber = (int(dzoneNumber) + 1)											# zone numbers start from 0 ie.(0 = zone 1)
		
		# convert hex to ascii
		displayName = binascii.a2b_hex(kzoneName)
		
		# verified message being processed notice
		if self.plugin.messageProcessInfo or self.plugin.debug:
			indigo.server.log(u"processing message:         %s,  zone: %r,  {%s}" % (kalarmMessage, dzoneNumber, displayName))
		
		# verify message word value and binary mapping
		self.plugin.debugLog(u"zoneNameMessage:        zone name message dictionary: %r" % dataDict)
		
		# update Device Zone configuration UI displayName
		zone = dzoneNumber
		if displayName != None:
			if zone in self.zoneList.keys():
				dev = self.zoneList[zone]
				localPropsCopy = dev.pluginProps
				localPropsCopy["zoneDisplayName"] = displayName
				dev.replacePluginPropsOnServer(localPropsCopy)
		#		dev.updateStateOnServer(key="zoneDisplayName", value=displayName)
				if self.plugin.messageProcessInfo or self.plugin.debug:
					indigo.server.log(u"update zone name:        device configuration ui and device state records sucessfully updated with zone: %r,  {%s}" % (dzoneNumber, displayName))	
			else:
				self.plugin.debugLog(u"update zone name:        no record in indigo database (device) for zone: %r" % dzoneNumber)
		else:
			self.plugin.debugLog(u"update zone name:        no device configuration ui records in message dictionary for zone name message update.")
		self.keypadDisplayName = displayName
			
	########################################
	# process "Zone Status Message"
	########################################
		
	def _zoneStatusMessage(self, dataDict):
		# extract each ASCII word from the system status message
		kmessageLength = dataDict [0]
		kmessageNumber = dataDict [1]
		kalarmMessage = self.messageAlarmDict(kmessageNumber)							# convert message number to message description
		bmessageLength = self.convertHexToDec(kmessageLength)							# convert message length from hex to dec
				
		kzoneNumber = dataDict [2]
		dzoneNumber = self.convertHexToDec(kzoneNumber)									# convert zone number from hex to dec for indexing
		dzoneNumber = (int(dzoneNumber) + 1)											# zone numbers start from 0 ie.(0 = zone 1)

		messageStart = 3
		
		# verified message being processed notice
		if self.plugin.messageProcessInfo or self.plugin.debug:
			indigo.server.log(u"processing message:         %s,  zone: %r,  length: %r" % (kalarmMessage, dzoneNumber, bmessageLength))
		
		# convert hex to binary map
		dmessageLength = int(self.convertHexToDec(kmessageLength) -2)	# valid data message length
		bzoneStatusMessageDict = self.convertByteDictToBinaryMap(messageStart, dmessageLength, dataDict)
		
		# verify message word value and binary mapping
		self.plugin.debugLog(u"zoneStatusMessage:        zone status message dictionary: %r" % dataDict)
		self.plugin.debugLog(u"zoneStatusMessage:        zone status message bit map dictionary: %r" % bzoneStatusMessageDict)
				
		# parameter byte definition lists
		partitionMaskList = ["partition8", "partition7", "partition6", "partition5", "partition4", "partition3", "partition2", "partition1"]
		typeFlag1List = ["localOnly", "interior", "entryExitDelay2","entryExitDelay1", "follower", "keySwitch", "in24HourFormat", "fire"]
		typeFlag2List = ["entryGuard", "forceArmable", "groupBypassable","bypassableType", "chime", "steadySiren", "yelpingSiren", "keypadSounder"]
		typeFlag3List = ["listenIn", "restoreable", "swingerShutdown","dialerDelay", "crossZone", "troubleZoneType", "doubleEOLTamper", "fastLoopResponse"]
		conditionFlag1List = ["zreservedbit7ConditionFlag1","lossOfSupervision", "lowBattery", "inhibitedForceArmed","bypassedCondition", "troubleCondition", "tampered", "faultedOrDelayedTrip"]
		conditionFlag2List = ["zreservedbit7ConditionFlag2", "zreservedbit6ConditionFlag2", "zreservedbit5ConditionFlag2","zreservedbit4ConditionFlag2", "zreservedbit3ConditionFlag2", "zreservedbit2ConditionFlag2", "bypassMemory", "alarmMemoryCondition"]
			
		# update Device Zone Configuration UI values from received "Zone Status Message"
		zone = dzoneNumber
		if bzoneStatusMessageDict != None:
			if zone in self.zoneList.keys():
				dev = self.zoneList[zone]
				localPropsCopy = dev.pluginProps
				self.updateZoneStatusConfigUi(localPropsCopy, partitionMaskList, bzoneStatusMessageDict[0])
				self.updateZoneStatusConfigUi(localPropsCopy, typeFlag1List, bzoneStatusMessageDict[1])
				self.updateZoneStatusConfigUi(localPropsCopy, typeFlag2List, bzoneStatusMessageDict[2])
				self.updateZoneStatusConfigUi(localPropsCopy, typeFlag3List, bzoneStatusMessageDict[3])			
				#	determine configured panel 'zone group type'
				zoneGroupTypeDict = bzoneStatusMessageDict[1] + bzoneStatusMessageDict[2] + bzoneStatusMessageDict[3]
				zoneGroupType = self.zoneGroupType(zoneGroupTypeDict)
				zoneGroupDescription = self.zoneGroupDescription(zoneGroupTypeDict)
				self.plugin.debugLog(u"zoneStatusMessage:        zone group type %r,  %s  dictionary: %r" % (zoneGroupType, zoneGroupDescription, zoneGroupTypeDict))
				# update zone configuration UI for zone group type and description
				localPropsCopy[u"zoneGroupType"] = zoneGroupType	
				localPropsCopy[u"zoneGroupDescription"] = zoneGroupDescription			
				dev.replacePluginPropsOnServer(localPropsCopy)
				# update zone device state for zone group type and description
		#		dev.updateStateOnServer(key="zoneGroupType", value=zoneGroupType)
		#		dev.updateStateOnServer(key="zoneGroupDescription", value=zoneGroupDescription)
				if self.plugin.messageProcessInfo or self.plugin.debug:
					indigo.server.log(u"update zone status:        device configuration ui records sucessfully updated with zone status message:  zone: %r" % dzoneNumber)	
			else:
				self.plugin.debugLog(u"update zone status:        no record in indigo database (device - config ui) for zone; %r." % dzoneNumber)
		else:
			self.plugin.debugLog(u"update zone status:        no device configuration ui records in message dictionary for zone status message update.")
			
		# update Zone Device states values from received "Zone Status Message"
		if bzoneStatusMessageDict != None:
			if zone in self.zoneList.keys():
				dev = self.zoneList[zone]
				self.updateZoneStatus(dev, bzoneStatusMessageDict[4], bzoneStatusMessageDict[5])
				if self.plugin.messageProcessInfo or self.plugin.debug:
					indigo.server.log(u"update zone status:        device state records sucessfully updated with zone status message:  zone: %r" % dzoneNumber)
			else:
				self.plugin.debugLog(u"update zone status:        no record in indigo database (device - state) for zone: %r." % dzoneNumber)
		else:
			self.plugin.debugLog(u"update zone status:        no device state records in message dictionary for zone status message update.")	
			
		# update zoneState value condition from received "Zone Status Message"
		if bzoneStatusMessageDict != None:
			zoneCondition = bzoneStatusMessageDict[4]
			if zone in self.zoneList.keys():
				dev = self.zoneList[zone]
				self.updateZoneStateCondition(dev, zone, zoneCondition)
				if self.plugin.messageProcessInfo or self.plugin.debug:
					indigo.server.log(u"update zone status:        zoneState device state value sucessfully updated with zone status message:  zone: %r" % dzoneNumber)
			else:
				self.plugin.debugLog(u"update zone status:        no record in indigo database (device - state 'zoneState') for zone: %r." % dzoneNumber)
		else:
			self.plugin.debugLog(u"update zone status:        no device state records in message dictionary for zone status message update.")	
				
	########################################
	# process "Zones Snapshot Message"
	########################################
	
	def _zoneSnapshotMessage(self, dataDict):
		# extract each ASCII word from the system status message
		kmessageLength = dataDict [0]
		kmessageNumber = dataDict [1]
		kalarmMessage = self.messageAlarmDict(kmessageNumber)							# convert message number to message description
		bmessageLength = self.convertHexToDec(kmessageLength)							# convert message length from hex to dec
			
		kzoneOffset = dataDict [2]
		bzoneOffset = self.convertHexToDec(kzoneOffset)									# convert hex to binary map for zone blocks 1 - 16 + (offset)
		
		messageStart = 3
		zoneGroups = {0:"zone 1 - zone 16", 1:"zone 17 - zone 32", 2:"zone 33 - zone 48", 3:"zone 49 - zone 64", 4:"zone 65 - zone 80", 5:"zone 81 - zone 96",
					6:"zone 97 - zone 112", 7:"zone 113 - zone 128", 8:"zone 129 - zone 144", 9:"zone 145 - zone 160", 10:"zone 161 - zone 176", 11:"zone 177 - zone 192"}
		
		# verified message being processed notice
		if self.plugin.messageProcessInfo or self.plugin.debug:
			indigo.server.log(u"processing message:         %s,  block address: %r,  group: %s" % (kalarmMessage, bzoneOffset, zoneGroups[bzoneOffset]))		
		
		# convert hex to binary map
		dmessageLength = int(self.convertHexToDec(kmessageLength) -2)					# valid data message length
		bzoneSnapshotMessageDict = self.convertByteDictToBinaryMap(messageStart, dmessageLength, dataDict)
		
		# verify binary mapping 
		self.plugin.debugLog(u"zoneSnapshotMessage:        zone snapshot message dictionary: %r" % dataDict)
		self.plugin.debugLog(u"zoneSnapshotMessage:        zone snapshot message bit map dictionary: %r" % bzoneSnapshotMessageDict)
		
		# parameter byte definition lists
		zoneSnapshotList = ["alarmMemory", "trouble", "bypass", "triggered"]
		
		# update Zone Device states values from received "Zone Snapshot Message"
	#	dzoneOffset = self.convertHexToDec(kzoneOffset)									# convert zone offset number from hex to dec for indexing
	#	if bzoneSnapshotMessageDict != None:
	#		self.updateZoneSnapshot(bzoneOffset, zoneSnapshotList, bzoneSnapshotMessageDict)
	#		if self.plugin.messageProcessInfo or self.plugin.debug:
	#			indigo.server.log(u"update zone snapshot:        device state records sucessfully updated with zone snapshot message: %s" % zoneGroups[bzoneOffset])
	#	else:
	#		self.plugin.debugLog(u"update zone snapshot:        no device state records in message dictionary for zone snapshot message update.")
		
	########################################
	# process "Partition Status Message"
	########################################
	
	def _partitionStatusMessage(self, dataDict):
		# extract each ASCII word from the partition status message
		kmessageLength = dataDict [0]
		kmessageNumber = dataDict [1]
		kalarmMessage = self.messageAlarmDict(kmessageNumber)							# convert message number to message description
		bmessageLength = self.convertHexToDec(kmessageLength)							# convert message length from hex to dec
		
		kpartitionNumber = dataDict [2]
		dpartitionNumber = self.convertHexToDec(kpartitionNumber)						# convert zone number from hex to dec for indexing
		dpartitionNumber = (int(dpartitionNumber) + 1)									# partition numbers start from 0 ie.(0 = partition 1)
		partition = dpartitionNumber
		partitionLastUserNumber = self.convertHexToDec(dataDict [7])
		
		messageStart = 3																# start pointer for valid message data (exclude message length and message number)
		
		# verified message being processed notice	
		if self.plugin.messageProcessInfo or self.plugin.debug:
			indigo.server.log(u"processing message:          %s,  partition: %r,  length: %r" % (kalarmMessage, dpartitionNumber, bmessageLength))

		# convert hex to binary map
		dmessageLength = int(self.convertHexToDec(kmessageLength) -2)					# valid data message length
		bpartitionStatusMessageDict = self.convertByteDictToBinaryMap(messageStart, dmessageLength, dataDict)
		
		# verify message word value and binary mapping 
		self.plugin.debugLog(u"partitionStatusMessage:        partition status message dictionary: %r" % dataDict)
		self.plugin.debugLog(u"partitionStatusMessage:        partition status message bit map dictionary: %r" % bpartitionStatusMessageDict)
		
		# parameter byte definition lists
		partitionConditionFlag1List = ["instant", "armedSystem", "reservedbit5ConditionFlag1", "tLMFaultMemory", "firePulsingBuzzer", "fire", "fireTrouble", "bypassCodeRequired"]
		partitionConditionFlag2List = ["cancelPending", "codeEntered", "cancelCommandEntered", "tamper", "alarmMemoryCondition", "steadySirenOn", "sirenOn", "previousAlarm"]
		partitionConditionFlag3List = ["exit2", "exit1", "delayExpirationWarning", "entry", "chimeModeOn", "entryGuardStayMode", "silentExitEnabled", "reservedbit0ConditionFlag3"]
		partitionConditionFlag4List = ["sensorLostSupervision", "sensorLowBattery", "autoHomeInhibited", "exitErrorTriggered", "reservedbit3ConditionFlag4", "recentClosingBeingTimed", "crossTiming", "ledExtinguish"]
		partitionConditionFlag5List = ["toneOnActivationTone", "errorBeepTripleBeep", "chimeOnSounding", "validPinAccepted", "readyToForceArm", "readyToArm", "forceArmTriggeredByAutoArm", "zoneBypass"]
		partitionConditionFlag6List = ["delayTripInProgressCommonZone", "keySwitchArmed", "cancelReportIsInTheStack", "alarmSendUsingPhoneNumber3", "alarmSendUsingPhoneNumber2", "alarmSendUsingPhoneNumber1", "openPeriod", "entry1"]
		
		# update Partition Device states values from received "Partition Status Message"
		if bpartitionStatusMessageDict != None:
			if partition in self.partitionList.keys():
				dev = self.partitionList[partition]
				dev.updateStateOnServer(key="lastUserNumber", value=partitionLastUserNumber)
				self.updatePartitionStatus(dev, partitionConditionFlag1List, bpartitionStatusMessageDict[0])
				self.updatePartitionStatus(dev, partitionConditionFlag2List, bpartitionStatusMessageDict[1])
				self.updatePartitionStatus(dev, partitionConditionFlag3List, bpartitionStatusMessageDict[2])
				self.updatePartitionStatus(dev, partitionConditionFlag4List, bpartitionStatusMessageDict[3])
				self.updatePartitionStatus(dev, partitionConditionFlag5List, bpartitionStatusMessageDict[5])
				self.updatePartitionStatus(dev, partitionConditionFlag6List, bpartitionStatusMessageDict[6])
				if self.plugin.messageProcessInfo or self.plugin.debug:
					indigo.server.log(u"update partition status:        device state records sucessfully updated with partition status message:  partition: %r" % partition)
				
				# update Keypad Device states values from received "Partition Status Message"
				systemArmed = dev.states['armedSystem']
				systemReady = dev.states['readyToArm']
				fireAlert = dev.states['fire']
				acPowerOn = dev.states['reservedbit5ConditionFlag1']
				stayArmed = dev.states['entryGuardStayMode']
				chimeMode = dev.states['chimeModeOn']
				exitDelay = dev.states['exit1']
				bypassZone = dev.states['zoneBypass']
		#		cancel = dev.states['cancelPending']
				keypad = int(dev.pluginProps['associatedKeypad'])
				if keypad in self.keypadList.keys():
					dev = self.keypadList[keypad]
					dev.updateStateOnServer(key='armedSystem', value=systemArmed)
					dev.updateStateOnServer(key='readyToArm', value=systemReady)
					dev.updateStateOnServer(key='fire', value=fireAlert)
					dev.updateStateOnServer(key='acPowerOn', value=acPowerOn)
					dev.updateStateOnServer(key='stayMode', value=stayArmed)
					dev.updateStateOnServer(key='chimeMode', value=chimeMode)
					dev.updateStateOnServer(key='exitDelay', value=exitDelay)
					dev.updateStateOnServer(key='zoneBypass', value=bypassZone)
			#		dev.updateStateOnServer(key='cancelPending', value=cancelPending)
					if self.plugin.messageProcessInfo or self.plugin.debug:
						indigo.server.log(u"update keypad status:        device state records sucessfully updated with partition status message:  keypad: %r" % keypad)
			else:
				self.plugin.debugLog(u"update partition status:        no record in indigo database (device - state) for partition: %r." % partition)
		else:
			self.plugin.debugLog(u"update partition status:        no device state records in message dictionary for partition status message update.")
		
	########################################
	# process "Partitions Snapshot Message"
	########################################
	
	def _partitionSnapshotMessage(self, dataDict):
		# extract each ASCII word from the partition status message
		kmessageLength = dataDict [0]
		kmessageNumber = dataDict [1]
		kalarmMessage = self.messageAlarmDict(kmessageNumber)							# convert message number to message description
		bmessageLength = self.convertHexToDec(kmessageLength)							# convert message length from hex to dec
						
		messageStart = 2																# start pointer for valid message data (exclude message length and message number)
		
		# verified message being processed notice
		if self.plugin.messageProcessInfo or self.plugin.debug:
			indigo.server.log(u"processing message:         %s,  partition 1 - 8,  length: %r" % (kalarmMessage, bmessageLength))

		# convert hex to binary map for partitions 1 - 8
		dmessageLength = int(self.convertHexToDec(kmessageLength) -1)					# valid data message length
		bpartitionSnapshotMessageDict = self.convertByteDictToBinaryMap(messageStart, dmessageLength, dataDict)
		
		# verify binary mapping 
		self.plugin.debugLog(u"partitionSnapshotMessage:        snapshot partition message dictionary: %r" % dataDict)
		self.plugin.debugLog(u"partitionSnapshotMessage:        snapshot partition message bit map dictionary: %r" % bpartitionSnapshotMessageDict)
		
		# parameter byte definition lists
		partitionSnapshotList = ["partitionPreviousAlarm", "anyExitDelay", "anyEntryDelay", "chimeMode", "stayArm", "exitArm", "securityReady", "validPartition"]
		
		# update Device Partition Configuration UI values from received "Partition Snapshot Message"
	#	if bpartitionSnapshotMessageDict != None:
	#		self.updatePartitionSnapshotConfigUi(partitionSnapshotList, bpartitionSnapshotMessageDict)
	#		if self.plugin.messageProcessInfo or self.plugin.debug:
	#			indigo.server.log(u"update partition snapshot . device configurtion ui records sucessfully updated for partition snapshot message: partition: all active partitions :")
	#	else:
	#		self.plugin.debugLog(u"update partition snapshot . no device configurtion ui records in message dictionary for partition status message update.")
							
		# update Device Partition State values from received "Partition Snapshot Message"
		if bpartitionSnapshotMessageDict != None:
			self.updatePartitionSnapshot(partitionSnapshotList, bpartitionSnapshotMessageDict)
			if self.plugin.messageProcessInfo or self.plugin.debug:
				indigo.server.log(u"update partition snapshot:        device state records sucessfully updated with partition snapshot message: all active partitions :")
		else:
			self.plugin.debugLog(u"update partition snapshot:        no device state records in message dictionary for partition snapshot message update.")
			
		# Update Alaram Dispaly from received "Partition Snapshot Message"
		if bpartitionSnapshotMessageDict != None:
			self.updateAlarmDisplay(partitionSnapshotList, bpartitionSnapshotMessageDict)	
		
	########################################
	# process "System Status Message"
	########################################
	
	def _systemStatusMessage(self, dataDict):
		# extract each ASCII word from the system status message
		kmessageLength = dataDict [0]
		kmessageNumber = dataDict [1]
		ksystemNumber = dataDict [2]
		kalarmMessage = self.messageAlarmDict(kmessageNumber)							# convert message number to message description
		bmessageLength = self.convertHexToDec(kmessageLength)							# convert message length from hex to dec
		systemPanelId = int(self.convertHexToDec(ksystemNumber))						# convert system number from hex to dec
		
		modelList = ['None', 'NX-4', 'NX-6', 'NX-8', 'NX-8e']
		self.model = modelList[systemPanelId]
		
		kpanelByte12 = dataDict [12]
		bpanelByte12 = self.convertHexToDec(kpanelByte12)								# convert communicator stack pointer length from hex to dec
		
		system = int(self.systemId)														# system panel type number for updating state values
		messageStart = 3																# start pointer for valid message data (exclude message length and message number)
		
		# verified message being processed notice
		if self.plugin.messageProcessInfo or self.plugin.debug:
			indigo.server.log(u"processing message:         %s,  system model: %s,  length: %r" % (kalarmMessage, self.model, bmessageLength))
			
		# convert hex to binary map
		dmessageLength = int(self.convertHexToDec(kmessageLength) -2)					# valid data message length
		bsystemStatusMessageDict = self.convertByteDictToBinaryMap(messageStart, dmessageLength, dataDict)

		# verify message word value and binary mapping
		self.plugin.debugLog(u"systemStatusMessage:        system status message dictionary: %r" % dataDict)
		self.plugin.debugLog(u"systemStatusMessage:        system status message bit map dictionary: %r" % bsystemStatusMessageDict)
		
		# parameter byte definition lists
		panelByte03List = ["twoWayLockout", "listenInActive", "usingBackupPhone", "dialerDelayInProgress", "downloadInProgress", "initialHandshakeReceived", "offHook", "lineSeizure"]
		panelByte04List = ["acFail", "lowBattery", "sirenTamper", "boxTamper", "fuseFault", "failToCommunicate", "phoneFault", "groundFault"]
		panelByte05List = ["zreservedbit7PanelByte5", "expanderBellFault", "auxiliaryCommChannelFailure", "expanderAuxOverCurrent", "expanderLossOffSupervision", "expanderLowBattery", "expanderACFailure", "expanderBoxTamper"]
		panelByte06List = ["busDeviceRequestedSniffMode", "busDeviceHasLineSeized", "globalSteadySiren", "globalSirenOn", "globalPulsingBuzzer", "pinRequiredForLocalDownload", "programmingTokenInUse", "enable6DigitPin"]
		panelByte07List = ["timingHighVoltageBatteryCharge", "linePowerDetected50Hz", "smokePowerReset", "fireAlarmVerificationBeingTimed", "groundFaultMemory", "lowBatteryMemory", "acPowerOn", "dynamicBatteryTest"]
		panelByte08List = ["timingACancelWindow", "controlShutdownMode", "testFixtureMode", "enrollRequested", "lossOfSystemTime", "walkTestMode", "powerUpDelayInProgress", "communicationSinceLastAutoTest"]
		panelByte09List = ["callBackInProgress", "zreservedbit6PanelByte9", "zreservedbit5PanelByte9", "zreservedbit4PanelByte9", "zreservedbit3PanelByte9", "zreservedbit2PanelByte9", "zreservedbit1PanelByte9", "zreservedbit0PanelByte9"]
		panelByte10List = ["listenInTrigger", "listenInRequested", "lastReadWasOffHook", "sniffing", "phoneLineMonitorEnabled", "housePhoneOffHook", "voltagePresentInterruptActive", "phoneLineFaulted"]
		panelByte11List = ["validPartition8", "validPartition7", "validPartition6", "validPartition5", "validPartition4", "validPartition3", "validPartition2", "validPartition1"]
		panelByte12List = ["communicatorStackPointer"]
		
		# update System Status Message Plugin Preferences "System Status Message"
		if bsystemStatusMessageDict != None:
			self.plugin.pluginPrefs[u"communicatorStackPointer"] = bpanelByte12
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
				indigo.server.log(u"update system status:        plugin preferences sucessfully updated with alarm panel system status message information.")
		
		# update System Status States from received "System Status Message"
		if bsystemStatusMessageDict != None:
			if system in self.systemStatusList.keys():
				dev = self.systemStatusList[system]
				dev.updateStateOnServer(key=u'systemNumber', value=systemPanelId)
				dev.updateStateOnServer(key=u'model', value=self.model)
				dev.updateStateOnServer(key=u'communicatorStackPointer', value=bpanelByte12)
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
					indigo.server.log(u"update system status:        device state records sucessfully updated with alarm panel system status message information.")
			else:
				self.plugin.debugLog(u"update system status:        no record in indigo database (device - state) for alarm panel system status message information.")
		else:
			self.plugin.debugLog(u"update system status:        no device state records in message dictionary for alarm panel system status message information update.")
	
	########################################
	# process "X10 Messages Received" (this method is not yet complete)
	########################################
	
	def _x10MessageReceived(self, dataDict):
		# extract each ASCII word from the x-10 message received
		kmessageLength = dataDict [0]
		kmessageNumber = dataDict [1]
		khouseCode = dataDict [2]
		kunitCode = dataDict [3]
		kx10FunctionCode = dataDict [4]
		kalarmMessage = self.messageAlarmDict(kmessageNumber)
		
		# convert hex to binary map
		bhouseCode = self.convertHexToDec(khouseCode)
		bunitCode = self.convertHexToDec(kunitCode)
		bx10FunctionCode = self.convertHexToDec(kx10FunctionCode)
		
		# verify binary mapping 
		self.plugin.debugLog(u"x10MessageReceived:        decode X-10 house code: %r" % bhouseCode)
		self.plugin.debugLog(u"x10MessageReceived:        decode X-10 unit code: %r" % bunitCode)
		self.plugin.debugLog(u"x10MessageReceived:        decode X-10 function code: %r" % bx10FunctionCode)
		
		# parameter byte definition lists
		x10FunctionCodeDict = {"\x68":"allLightsOff", "\x58":"bright", "\x48":"dim", "\x38":"off", "\x28":"on", "\x18":"allLightsOn", "\x08":"allUnitsOff"}
		
	########################################
	# process "Log Event Message"
	########################################
	
	def _logEventMessage(self, dataDict):
		# extract each ASCII word from the log event message
		kmessageLength = dataDict [0]
		kmessageNumber = dataDict [1]
		kalarmMessage = self.messageAlarmDict(kmessageNumber)
						
		# convert hex to ascii map
		deventNum = self.convertHexToDec(dataDict [2])									# specific sequence event number
		dtotalLogSize = self.convertHexToDec(dataDict [3])								# total size of the event log queue
		deventType = self.convertHexToDec(dataDict [4])									# event type number to translated to event scription
		dzoneUserDevice = (self.convertHexToDec(dataDict [5])	+1)						# event effects zone (0 = zone 1), user (0 = user 1) or device reference
		dpartitionNumber = (int(self.convertHexToDec(dataDict [6])) + 1)				# partition numbers start from 0 ie.(0 = partition 1)
	
		timeStamp = time.asctime( time.localtime(time.time()) )
		deventNumber = self.adjustLogEventNumberDigits(deventNum)
		dzoneUserDeviceNumber = self.adjustZoneNumberDigits(dzoneUserDevice)
		
		# verified message being processed notice
		if self.plugin.messageProcessInfo or self.plugin.debug:
			indigo.server.log(u"processing message:         %s,  alarm event: %r,  %s" % (kalarmMessage, deventType, timeStamp))
		
		# use computer day/time clock for the Log Event timestamp
		timeLogEvent = self.timestamp()
	
		if deventType <= 127:
			# look up dictionary event number for description, byte 5 and byte 6 values
			eventDescription = self.messageLogEventDict(deventType)
			eventZoneUserDeviceValid = self.messageLogByte5Dict(deventType)
			eventPartitionNumberValid = self.messageLogByte6Dict(deventType)
		
			# conditional log event format statements
			if eventZoneUserDeviceValid == "zone" and eventPartitionNumberValid == True:
				zoneName = self.updateZoneNameBreached(dzoneUserDevice)
				logEventMessagePrint = u"log event %s:      %s,  partition: %s  zone: %s  {%s}   ** %s" % (deventNumber ,eventDescription, dpartitionNumber, dzoneUserDeviceNumber, zoneName, timeLogEvent)	
				# Keypad LCD Display Message for Zone Security Breach
				if deventType == 0 :
					self.breachedZone = self.updateZoneNameBreached(dzoneUserDevice)
					self.updateAlarmDisplayZoneBreached(dpartitionNumber, self.breachedZone)	
			elif eventZoneUserDeviceValid == "none" and eventPartitionNumberValid == True:
				logEventMessagePrint = u"log event %s:      %s,  partition: %s   ** %s" % (deventNumber ,eventDescription, dpartitionNumber, timeLogEvent)
			elif eventZoneUserDeviceValid == "device" and eventPartitionNumberValid == False:
				logEventMessagePrint = u"log event %s:      %s,  device: %s   ** %s" % (deventNumber ,eventDescription, dzoneUserDevice, timeLogEvent)
			elif eventZoneUserDeviceValid == "none" and eventPartitionNumberValid == False:
				logEventMessagePrint = u"log event %s:      %s,   ** %s" % (deventNumber ,eventDescription, timeLogEvent)
			elif eventZoneUserDeviceValid == "user" and eventPartitionNumberValid == True:
				logEventMessagePrint = u"log event %s:      %s,  partition: %s  user: %r   ** %s" % (deventNumber ,eventDescription, dpartitionNumber, dzoneUserDevice, timeLogEvent)
			elif eventZoneUserDeviceValid == "user" and eventPartitionNumberValid == False:
				logEventMessagePrint = u"log event %s :      %s,  user: %s   ** %s" % (deventNumber ,eventDescription, dzoneUserDevice, timeLogEvent)
				
		# for special conditional log events not defined in the dictionary			
		else:
			if deventType == 138:
				eventDeviceDescription = self.messageLogDeviceAddressDict(dzoneUserDevice -1)
				logEventMessagePrint = u"log event %s:      Loss of Supervision (wireless): %s,  zone: %s,  partition: %s  ** %s" % (deventNumber, eventDeviceDescription, (dzoneUserDevice -1), dpartitionNumber , timeLogEvent)
			if deventType == 139:
				eventDeviceDescription = self.messageLogDeviceAddressDict(dzoneUserDevice -1)
				logEventMessagePrint = u"log event %s:      Loss of Supervision RESTORED (wireless): %s,  zone: %s,  partition: %s  ** %s" % (deventNumber, eventDeviceDescription, (dzoneUserDevice -1), dpartitionNumber , timeLogEvent)
			if deventType == 168:
				eventDeviceDescription = self.messageLogDeviceAddressDict(dzoneUserDevice -1)
				logEventMessagePrint = u"log event %s:      system DISARMED: %s,  address: %s,  partition: %s  ** %s" % (deventNumber, eventDeviceDescription, (dzoneUserDevice -1), dpartitionNumber , timeLogEvent)
				if self.plugin.enableSpeakPrompts:
					indigo.server.speak(sayDisarmed)
			elif deventType == 169:
				eventDeviceDescription = self.messageLogDeviceAddressDict(dzoneUserDevice -1)
				logEventMessagePrint = u"log event %s:      system ARMED: %s,  address: %s,  partition: %s  ** %s" % (deventNumber, eventDeviceDescription, (dzoneUserDevice -1), dpartitionNumber , timeLogEvent)
				if self.plugin.enableSpeakPrompts:
					indigo.server.speak(sayArmed)
			elif deventType == 173:
				eventDeviceDescription = self.messageLogDeviceAddressDict(dzoneUserDevice -1)
				logEventMessagePrint = u"log event %s:      entering program mode: %s,  address: %s,  partition: %s  ** %s" % (deventNumber, eventDeviceDescription, (dzoneUserDevice -1), dpartitionNumber , timeLogEvent)
				# update enter keypad program mode states in plugin perferences
				self.plugin.pluginPrefs[u"isKeypadProgramming"] = True
				self.plugin.pluginPrefs[u"panelStatus"] = "Program Mode (enter)  ** %s " % self.timestamp()
				variableID = "panelStatus"
				panelStatusVariable = (u"Program Mode (enter)  ** %s " % self.timestamp())
				self.updateVariable(variableID, panelStatusVariable)
			elif deventType == 174:
				eventDeviceDescription = self.messageLogDeviceAddressDict(dzoneUserDevice -1)
				logEventMessagePrint = u"log event %s:        exiting program mode: %s,  address: %s,  partition: %s  ** %s" % (deventNumber, eventDeviceDescription, (dzoneUserDevice -1),  dpartitionNumber , timeLogEvent)
				# update exit keypad program mode states in plugin perferences
				self.plugin.pluginPrefs[u"isKeypadProgramming"] = False
				self.plugin.pluginPrefs[u"panelStatus"] = "Program Mode (exit)  ** %s " % self.timestamp()
				variableID = "panelStatus"
				panelStatusVariable = (u"Program Mode (exit)  ** %s " % self.timestamp())
				self.updateVariable(variableID, panelStatusVariable)
			elif deventType == 245:
				eventDeviceDescription = self.messageLogDeviceAddressDict(dzoneUserDevice -1)
				logEventMessagePrint = u"log event %s:      registering module: %s,  address: %s,  partition: %s  ** %s" % (deventNumber, eventDeviceDescription, (dzoneUserDevice -1),  dpartitionNumber , timeLogEvent)
			elif deventType == 247:
				logEventMessagePrint = u"log event %s:      confirm alarm system time and date set: %s  ** %s" % (deventNumber, timeStamp, timeLogEvent)
			else:
				logEventMessagePrint = u"log event %s:      alarm event: (%s)  is out of range of event dictionary definitions byte 5: (device address %s),  byte 6: (partition %s)  ** %s" % (deventNumber, deventType, (dzoneUserDevice -1), dpartitionNumber, timeLogEvent)
				if self.plugin.alarmEventInfo or self.plugin.debug:
					indigo.server.log(u"log event %s:      data dictionary: %s " % (deventNumber, dataDict))

					
		# log event to indigo log history (last 25 entries)
		logEventHistoryList = ["zlogEventHistory01", "zlogEventHistory02", "zlogEventHistory03", "zlogEventHistory04", "zlogEventHistory05", "zlogEventHistory06", "zlogEventHistory07",
									"zlogEventHistory08", "zlogEventHistory09", "zlogEventHistory10", "zlogEventHistory11", "zlogEventHistory12", "zlogEventHistory13", "zlogEventHistory14",
									"zlogEventHistory15", "zlogEventHistory16", "zlogEventHistory17", "zlogEventHistory18", "zlogEventHistory19", "zlogEventHistory20", "zlogEventHistory21",
									"zlogEventHistory22", "zlogEventHistory23", "zlogEventHistory24", "zlogEventHistory25" ]							 		 							 
		item = 0
		for i in range(0,24):
			newVariable = logEventHistoryList[item] 
			oldVariable = logEventHistoryList[item +1 ]
			self.plugin.pluginPrefs[newVariable] = self.plugin.pluginPrefs[oldVariable]
			item += 1	
		self.plugin.pluginPrefs[u"zlogEventHistory25"] = logEventMessagePrint
			
		# update indigo eventLog variable		
		if self.plugin.alarmEventInfo or self.plugin.debug:
			indigo.server.log(u"%s" % logEventMessagePrint)
			variableID = "eventLogMessage"
			eventLogVariable = logEventMessagePrint
			self.updateVariable(variableID, eventLogVariable)
			
	########################################
	# process "Keypad Message Received"
	########################################
	
	def _keypadMessageReceived(self, dataDict):
		# extract each ASCII word from the keypad message received
		kmessageLength = dataDict [0]
		kmessageNumber = dataDict [1]
		kalarmMessage = self.messageAlarmDict(kmessageNumber)
		
		kkeypadAddress = dataDict [2]
		kkeypadValue = dataDict [3]
		
		# parameter byte definition lists
		keypadValueDict = {"00":"0", "01":"1", "02":"2", "03":"3", "04":"4", "05":"5", "06":"6", "07":"7", "08":"8", "09":"9", "0a":"Stay", "0b":"Chime",
							"0c":"Exit", "0d":"Bypass", "0e":"Cancel", "0f":"Fire", "10":"Medical", "11":"Police", "12":"*", "13":"#", "14":"up", "15":"down",
							"80":"Auxiliary 1", "81":"Auxiliary 2"}
		# verify binary mapping 
		indigo.server.log(u"alarm keypad button pressed;  keypad: %r,  button: %s" % (kkeypadAddress, keypadValueDict[kkeypadValue]))
		
	########################################
	# process "Progam Data Reply"	(this method is not yet complete)
	########################################
		
	def _programDataReply(self, dataDict):
		# extract each ASCII word from the program data reply
		kmessageLength = dataDict [0]
		kmessageNumber = dataDict [1]
		kdeviceBusAddressdataDictdata [2]
		kupperLogicalLocationOffset = dataDict [3]
		klowerLogicalLocationOffset = dataDict [4]
		klocationLengthDataType = data [5]
		kdataTypeByte06 = dataDict [6]
		kdataTypeByte07 = dataDict [7]
		kdataTypeByte08 = dataDict [8]
		kdataTypeByte09 = dataDict [9]
		kdataTypeByte10 = dataDict [10]
		kdataTypeByte11 = dataDict [11]
		kdataTypeByte12 = dataDict [12]
		kdataTypeByte13 = dataDict [13]		
		kalarmMessage = self.messageAlarmDict(kmessageNumber)
		
		# convert hex to binary map
		bdeviceBusAddress = self.convertHexToDec(kdeviceBusAddress)
		bupperLogicalLocationOffset = self.convertHexToDec(kupperLogicalLocationOffset)
		blowerLogicalLocationOffset = self.convertHexToDec(klowerLogicalLocationOffset)
		blocationLengthDataType = self.convertHexToDec(klocationLengthDataType)
		bdataTypeByte06 = self.convertHexToDec(kdataTypeByte06)
		bdataTypeByte07 = self.convertHexToDec(kdataTypeByte07)
		bdataTypeByte08 = self.convertHexToDec(kdataTypeByte08)
		bdataTypeByte09 = self.convertHexToDec(kdataTypeByte09)
		bdataTypeByte10 = self.convertHexToDec(kdataTypeByte10)
		bdataTypeByte11 = self.convertHexToDec(kdataTypeByte11)
		bdataTypeByte12 = self.convertHexToDec(kdataTypeByte12)
		bdataTypeByte13 = self.convertHexToDec(kdataTypeByte13)
		
		# verify binary mapping 
		self.plugin.debugLog(u"programDataReply:        decode device bus address: %r" % bdeviceBusAddress)
		self.plugin.debugLog(u"programDataReply:        decode upper logical location offset: %r" % bupperLogicalLocationOffset)
		self.plugin.debugLog(u"programDataReply:        decode lower logical location offset: %r" % blowerLogicalLocationOffset)
		self.plugin.debugLog(u"programDataReply:        decode location length data type: %r" % blocationLengthDataType)
		self.plugin.debugLog(u"programDataReply:        decode data type byte 06: %r" % bdataTypeByte06)
		self.plugin.debugLog(u"programDataReply:        decode data type byte 07: %r" % bdataTypeByte07)
		self.plugin.debugLog(u"programDataReply:        decode data type byte 08: %r" % bdataTypeByte08)
		self.plugin.debugLog(u"programDataReply:        decode data type byte 09: %r" % bdataTypeByte09)
		self.plugin.debugLog(u"programDataReply:        decode data type byte 10: %r" % bdataTypeByte10)
		self.plugin.debugLog(u"programDataReply:        decode data type byte 11: %r" % bdataTypeByte11)
		self.plugin.debugLog(u"programDataReply:        decode data type byte 12: %r" % bdataTypeByte12)
		self.plugin.debugLog(u"programDataReply:        decode data type byte 13: %r" % bdataTypeByte13)
		
	########################################
	# process "User Information Reply"	
	########################################
	
	def _userInformationReply(self, dataDict):
		# extract each ASCII word from the user information reply
		kmessageLength = dataDict [0]
		kmessageNumber = dataDict [1]
		kalarmMessage = self.messageAlarmDict(kmessageNumber)
		bmessageLength = self.convertHexToDec(kmessageLength)
		
		kuserNumber = dataDict [2]
		buserNumber = self.convertHexToDec(kuserNumber)
		user = buserNumber
		kpinDigit1and2 = dataDict [3]
		kpinDigit3and4 = dataDict [4]
		kpinDigit5and6 = dataDict [5]
		
		# format user code length correctly for 4 or 6 digits
		codeLength = atof(self.plugin.pluginPrefs['codeLength'])
		if codeLength == 4:
			kuserPin = kpinDigit1and2[1] +  kpinDigit1and2[0] + kpinDigit3and4[1] +  kpinDigit3and4[0]
		if codeLength == 6:	
			kuserPin = kpinDigit1and2[1] +  kpinDigit1and2[0] + kpinDigit3and4[1] +  kpinDigit3and4[0] + kpinDigit5and6[1] +  kpinDigit5and6[0]
			
		messageStart = 3																# start pointer for valid message data (exclude message length and message number)
		
		# verified message being processed notice
		if self.plugin.messageProcessInfo or self.plugin.debug:
			indigo.server.log(u"processing message:         %s,  user: %r,  length: %r" % (kalarmMessage, buserNumber, bmessageLength))
			
		# convert hex to binary map
		dmessageLength = int(self.convertHexToDec(kmessageLength) -2)					# valid data message length
		buserInformationReplyDict = self.convertByteDictToBinaryMap(messageStart, dmessageLength, dataDict)	
		
		# verify binary mapping 
		self.plugin.debugLog(u"userInformationReply:        decode user PIN: %r" % kuserPin)
		self.plugin.debugLog(u"userInformationReply:        decode user information bit map dictionary: %r" % buserInformationReplyDict)
			
		# parameter byte definition lists
		authorityFlag1List = ["mustBe0", "openCloseReportEnabled", "bypassEnabled", "armDisarmEnabled", "masterProgram", "armOnlyDuringCloseWindow", "armOnly", "reservedbit0UserAuthorityFlag1"]
		authorityFlag2List = ["mustBe1", "openCloseReportEnabled", "bypassEnabled", "armDisarmEnabled", "output4Enable", "output3Enable", "output2Enable", "output1Enable"]
		userAuthorisedPartitionList = ["authorisedForPartition8", "authorisedForPartition7", "authorisedForPartition6", "authorisedForPartition5", "authorisedForPartition4", "authorisedForPartition3", "authorisedForPartition2", "authorisedForPartition1"]

		# update Device User Information Configuration UI values from received "User Information Reply"
		if buserInformationReplyDict != None:
			if user in self.userList.keys():
				dev = self.userList[user]
				localPropsCopy = dev.pluginProps
				localPropsCopy["userPin"] = kuserPin
				self.updateUserInformationStatusConfigUi(localPropsCopy, authorityFlag1List, buserInformationReplyDict[3])
				self.updateUserInformationStatusConfigUi(localPropsCopy, userAuthorisedPartitionList, buserInformationReplyDict[4])
				dev.replacePluginPropsOnServer(localPropsCopy)
				if self.plugin.messageProcessInfo or self.plugin.debug:
					indigo.server.log(u"update user information:        device configurtion ui records sucessfully updated for user information:  user: %r" % buserNumber)
			else:
				self.plugin.debugLog(u"update user information:        no record in indigo database (device - config ui) for user: %r." % buserNumber)
		else:
			self.plugin.debugLog(u"update user information:        no device configuration ui records in message dictionary for user information update.")
				
		# Update User Information Device states values from received "User Information Reply"
		if buserInformationReplyDict != None:
			if user in self.userList.keys():
				dev = self.userList[user]
				dev.updateStateOnServer(key="userPin", value=kuserPin)
				self.updateUserInformationStatus(dev, authorityFlag1List, buserInformationReplyDict[3])
				self.updateUserInformationStatus(dev, userAuthorisedPartitionList, buserInformationReplyDict[4])
				if self.plugin.messageProcessInfo or self.plugin.debug:
					indigo.server.log(u"update user information:        device state records sucessfully updated for user information:  user: %r" % buserNumber)
			else:
				self.plugin.debugLog(u"update user information:        no record in indigo database (device - state) for user: %r." % buserNumber)
		else:
			self.plugin.debugLog(u"update user information:        no device state records in message dictionary for user information update.")
				
	################################################################################	
	# Routines to Support Message Processing methods data conversion methods to supprt message processing	
	################################################################################
	# data conversion methods to support message processing
	
	########################################
	# convert Hexdecimal value to Decimal integer value 
	########################################
	
	def convertHexToDec(self, s):
		return int(s,16)
		
	########################################		
	# convert Byte value to Decimal string value 	
	########################################
	
	def convertByteToDec(self, byte):
		decString = ""
		bit0 = 0
		bit1 = 1
		for i in range(0, 3):
			var = int("%d%d" % (byte[bit0], byte[bit0]))
			dec = chr(byte[var])
			decString  = "".join(dec)
			bit0 += 2
			bit1 += 2
		return decString	
		
	########################################		
	# convert Decimal value to Hexidecimal value 	
	########################################
	
	def convertDecToHex(self, n):
		return "%02x" % n
		
	########################################			
	# convert Hexdecimal value to 2 byte Binary word map 
	########################################
	
	def convertWordHexToBin(self, word):
		byte1 = word[0]
		byte2 = word[1]
		byteA = self.convertByteHexToBin(byte1)
		byteB = self.convertByteHexToBin(byte2)
		self.word = byteA + byteB
		return word
		
	########################################
	# convert Hexdecimal to Nibble map dictionary for snapshot zones (offset) + (1 - 16) message 
	########################################
	
	def convertNibbleHexToBin(self, nibbles):
		nibbleDict = {}
		bitLocation = 0
		for i in nibbles:
			byte = nibbles[bitLocation]
			nibble = self.convertByteHexToBin(byte)
			nibbleDict[bitLocation] = nibble
			bitLocation += 1
		return nibbleDict
		
	########################################
	# convert Hexdecimal to Byte map dictionary for (zone status message & snapshot partitions 1 - 8 message)
	########################################
	 
	def convertNibbleByteHexToBin(self, msgLength, nibbles):
		if (msgLength *2) <= len(nibbles):
			nibbleDict = {}
			byteDict = {}
			bitLocation = 0
			for i in nibbles:
				byte = nibbles[bitLocation]
				nibble = self.convertByteHexToBin(byte)
				nibbleDict[bitLocation] = nibble
				bitLocation += 1
			byteLocation = 0	
			byte1Location = 0
			byte2Location = 1
			self.plugin.debugLog(u"convertNibbleByteHexToBin:        valid data message length: %r" % msgLength)
			self.plugin.debugLog(u"convertNibbleByteHexToBin:        nibbleDict: %r" % nibbleDict)
			for i in range (0,msgLength):
				byte1 = nibbleDict[byte1Location]
				byte2 = nibbleDict[byte2Location]
				byteDict[byteLocation] = byte1 + byte2
				byteLocation += 1
				byte1Location += 2
				byte2Location += 2
			return byteDict
		else:
			indigo.server.log(u"convertNibbleByteHexToBin:        error in message format,  message byte length: %r,  nibbles: %r" % (msgLength, len(nibbles)))	
				
	########################################
	# convert valid message Bytes to Bit map dictionary	
	########################################
	
	def convertByteDictToBinaryMap(self, msgStart, msgLength, messageDict):
		if msgLength <= len(messageDict):
	#		self.plugin.debugLog(u"convertByteDictToBinaryMap:        message start location: %r,  valid data message length: %r" % (msgStart, msgLength))
	#		self.plugin.debugLog(u"convertByteDictToBinaryMap:        passed message dictionary: %r" % messageDict)
			bitmapDict = {}
			byteDict = {}
			byteLocation = msgStart
			for i in range (msgStart, (msgLength + msgStart)):
				byte = messageDict[byteLocation]
				nibble0 = byte [0]
				nibble1 = byte [1]
				nibbleMSB = self.convertByteHexToBin(nibble0)
				nibbleLSB = self.convertByteHexToBin(nibble1)
				bitmapDict[(byteLocation - msgStart)] = nibbleMSB + nibbleLSB
				byteLocation += 1
	#		self.plugin.debugLog(u"convertByteDictToBinaryMap:        bit map dictionary: %r" % bitmapDict)
			return bitmapDict
		else:
			self.plugin.debugLog(u"convertByteDictToBinaryMap:        error in message format,  message byte length: %r,  nibbles: %r" % (msgLength, len(messageDict)))	
			
	########################################
	# convert each Hexdecimal value to Binary bit map 	
	########################################
		
	def convertByteHexToBin(self, byte):
		if byte == "f":
			byte = "1111"
		if byte == "e":
			byte = "1110"
		if byte == "d":
			byte = "1101"
		if byte == "c":
			byte = "1100"
		if byte == "b":
			byte = "1011"
		if byte == "a":
			byte = "1010"
		if byte == "9":
			byte = "1001"
		if byte == "8":
			byte = "1000"
		if byte == "7":
			byte = "0111"
		if byte == "6":
			byte = "0110"
		if byte == "5":
			byte = "0101"
		if byte == "4":
			byte = "0100"
		if byte == "3":
			byte = "0011"
		if byte == "2":
			byte = "0010"
		if byte == "1":
			byte = "0001"
		if byte == "0":
			byte = "0000"						
		return byte	    

	################################################################################	
	# Routines for updating Indigo Database States methods update indigo plugin preferences, device configuration ui and device states	
	################################################################################
	# update indigo plugin preferences, device configuration ui and device states
	
	########################################
	# updates indigo variable instance var with new value varValue
	########################################
	
	def updateVariable(self, varName, varValue):
	# 	indigo.server.log(u"updateVariable(): -- variable  %s : value  %r :" % (varName,varValue))
	 	
		if "Caddx Security System" not in indigo.variables.folders:
			self.caddxVariablesFolder = indigo.variables.folder.create("Caddx Security System")
		else:
			self.caddxVariablesFolder = indigo.variables.folders["Caddx Security System"]
			
		if varName not in indigo.variables:
			self.varName = indigo.variable.create(name = varName, value ="", folder = self.caddxVariablesFolder)
			indigo.server.log(u"-- create variable : %s :" % varName)
			indigo.variable.updateValue(self.varName, value=varValue)
		else:
			self.varName = indigo.variables[varName]		
			indigo.variable.updateValue(self.varName, value=varValue)
			
	########################################
	# update values from "Interface Configuration Message"
	########################################
	
	# update Interface Configuration Plugin Preferences from received "Interface Configuration Message"
	def updateInterfaceConfigPluginPrefs(self, varList, newByte):
		if newByte != None:
			address = 7
			bitLocation = 0
			for i in newByte:
				var = varList[address]
				bit = newByte[address]
	#			self.plugin.debugLog(u"updateInterfaceConfiguration:        updating plugin pref variable: %r,  value: %r,  address: %r" % (var, bit, bitLocation))
				self.plugin.pluginPrefs[var] = bit
				address -= 1
				bitLocation += 1
		
	# update Interface Configuration Status States from received "Interface Configuration Message"
	def updateInterfaceConfigStates(self, dev, varList, newByte):
		if newByte != None:
			address = 7
			bitLocation = 0
			for i in newByte:
				var = varList[address]
				bit = newByte[address]
	#			self.plugin.debugLog(u"updateInterfaceConfiguration:        updating device state variable: %r,  value: %r,  address: %r" % (var, bit, bitLocation))
				dev.updateStateOnServer(key=var, value=bit)
				address -= 1
				bitLocation += 1	
						
	########################################
	# update values from "Zone Status Message"
	########################################
	
	# update Zone Configuration UI pluginProps values from received "Zone Status Message" 
	def updateZoneStatusConfigUi(self, localProps, varList, newByte):
		address = 7
		bitLocation = 0
		for i in varList:
			var = varList[address]
			bit = newByte[address]
	#		self.plugin.debugLog(u"updateZoneStatusConfigUi:        pdating device config ui variable: %r,  value: %r,  address: %r" % (var, bit, bitLocation))
			localProps[var] = bit
			address -= 1
			bitLocation += 1
		return localProps
		
	# update Zone Device States from received "Zone Status Message" 	
	def updateZoneStatus(self, dev, zoneConditionLevel1, zoneConditionLevel2):
			var = 'faultedOrDelayedTrip'
			bit = zoneConditionLevel1[7]
			dev.updateStateOnServer(key=var, value=bit)
			var = 'tampered'
			bit = zoneConditionLevel1[6]
			dev.updateStateOnServer(key=var, value=bit)		
			var = 'troubleCondition'
			bit = zoneConditionLevel1[5]
			dev.updateStateOnServer(key=var, value=bit)
			var = 'bypassedCondition'
			bit = zoneConditionLevel1[4]
			dev.updateStateOnServer(key=var, value=bit)
			var = 'inhibitedForceArmed'
			bit = zoneConditionLevel1[3]
			dev.updateStateOnServer(key=var, value=bit)
			var = 'lowBattery'
			bit = zoneConditionLevel1[2]
			dev.updateStateOnServer(key=var, value=bit)
			var = 'lossOfSupervision'
			bit = zoneConditionLevel1[1]
			dev.updateStateOnServer(key=var, value=bit)
			var = 'alarmMemoryCondition'
			bit = zoneConditionLevel2[7]
			dev.updateStateOnServer(key=var, value=bit)
			var = 'bypassMemory'
			bit = zoneConditionLevel2[6]
			dev.updateStateOnServer(key=var, value=bit)
	
	########################################
	# update values from "Zone Snapshot Message"
	########################################
	
	# update Zone Device States Snapshot from received "Zone Snapshot Message"
	def updateZoneSnapshot(self, offset, varList, newByte):
		zoneAddress = (offset + 1)
		if newByte != None:
			for key in newByte:
	#			self.plugin.debugLog(u"updateZoneSnapshot:        updating zone: %r." % zoneAddress)
				if zoneAddress in self.zoneList.keys():
					dev = self.zoneList[zoneAddress] 
					nibble = newByte[key]
					address = 3
					bitLocation = 7
					for i in range(0,4):
						var = varList[address]
						bit = nibble[bitLocation]
	#					self.plugin.debugLog(u"updateZoneSnapshot:        updating device state,  zone: %r,  variable: %r,  value: %r,  address: %r" % (zoneAddress, var, bit, bitLocation))
						dev.updateStateOnServer(key=var, value=bit)
						address -= 1
						bitLocation -= 1
					zoneAddress += 1	
	
				if zoneAddress in self.zoneList.keys():
					dev = self.zoneList[zoneAddress] 
					nibble = newByte[key]
					address = 3
					bitLocation = 3
					for i in range(0,4):
						var = varList[address]
						bit = nibble[bitLocation]
	#					self.plugin.debugLog(u"updateZoneSnapshot:        updating device state,  zone: %r,  variable: %r,  value: %r,  address: %r" % (zoneAddress, var, bit, bitLocation))
						dev.updateStateOnServer(key=var, value=bit)
						address -= 1
						bitLocation -= 1
					zoneAddress += 1	

		else:
			self.plugin.debugLog(u"updateZoneSnapshot(): -- no device state records in message dictionary for zone snapshot message update.")					

	########################################
	# update values from "Partition Status Message"
	########################################
	
	# update Partition Configuration UI pluginProps values from received "Partition Status Message"
	def updatePartitionStatusConfigUi(self, localProps, varList, newByte):
		address = 7
		bitLocation = 0
		for i in varList:
			var = varList[address]
			bit = newByte[address]
	#		self.plugin.debugLog(u"updatePartitionStatusConfigUi:        updating device config ui variable: %r,  value: %r,  address: %r" % (var, bit, bitLocation))
			localProps[var] = bit
			address -= 1
			bitLocation += 1
		return localProps
		
	# update Partition Status States from received "Partition Status Message" 
	def updatePartitionStatus(self, dev, varList, newByte):
		if newByte != None:
			address = 7
			bitLocation = 0
			for i in newByte:
				var = varList[address]
				bit = newByte[address]
	#			self.plugin.debugLog(u"updatePartitionStatus:        pdating device state variable: %r,  value: %r,  address: %r" % (var, bit, bitLocation))
				dev.updateStateOnServer(key=var, value=bit)
				address -= 1
				bitLocation += 1	
				
	########################################
	# update values from "Partition Snapshot Message"
	########################################
	
	# update Partition Configuration UI pluginProps values from received "Partition Snapshot Message" 
	def updatePartitionSnapshotConfigUi(self, varList, newByte):
		for key in newByte:
			partitionNumber = (key + 1)
	#		self.plugin.debugLog(u"updatePartitionSnapshotConfigUi:        updating partition: %r" % partitionNumber)
			if partitionNumber in self.partitionList.keys():
				dev = self.partitionList[partitionNumber]
				localPropsCopy = dev.pluginProps 
				nibble = newByte[key]
				address = 7
				bitLocation = 0
				for i in nibble:
					var = varList[address]
					bit = nibble[address]
	#				self.plugin.debugLog(u"updatePartitionSnapshotConfigUi:        updating device state variable: %r,  value: %r,  address: %r" % (var, bit, bitLocation))
					localPropsCopy[var] = bit
					address -= 1
					bitLocation += 1
				dev.replacePluginPropsOnServer(localPropsCopy)	
			else:
				pass

	# update Partition Device States Snapshot from received "Partition Snapshot Message" 
	def updatePartitionSnapshot(self, varList, newByte):
		for key in newByte:
			partitionNumber = (key + 1)
	#		self.plugin.debugLog(u"updatePartitionSnapshot:        updating partition: %r" % partitionNumber)
			if partitionNumber in self.partitionList.keys():
				dev = self.partitionList[partitionNumber] 
				nibble = newByte[key]
				address = 7
				bitLocation = 0
				for i in nibble:
					var = varList[address]
					bit = nibble[address]
	#				self.plugin.debugLog(u"updatePartitionSnapshot:        pdating device state variable: %r,  value: %r,  address: %r" % (var, bit, bitLocation))
					dev.updateStateOnServer(key=var, value=bit)
					address -= 1
					bitLocation += 1
			else:
				pass
		
	########################################
	# update values from "System Status Message"
	########################################
	
	# update System Status Information Plugin Preferences from received "System Status Message"	
	def updateSystemStatusPluginPrefs(self, varList, newByte):
		if newByte != None:
			address = 7
			bitLocation = 0
			for i in newByte:
				var = varList[address]
				bit = newByte[address]
	#			self.plugin.debugLog(u"updateSystemStatusPluginPrefs:        updating plugin pref variable: %r,  value: %r,  address: %r" % (var, bit, bitLocation))
				self.plugin.pluginPrefs[var] = bit
				address -= 1
				bitLocation += 1
					
	# update System Status States from received "System Status Message"	
	def updateSystemStatus(self, dev, varList, newByte):
		if newByte != None:
			address = 7
			bitLocation = 0
			for i in newByte:
				var = varList[address]
				bit = newByte[address]
	#			self.plugin.debugLog(u"updateSystemStatus:        updating device state variable: %r,  value: %r,  address: %r" % (var, bit, bitLocation))
				dev.updateStateOnServer(key=var, value=bit)
				address -= 1
				bitLocation += 1
				
	########################################
	# update values from "User Information Reply"
	########################################
	
	# update User Information Configuration UI pluginProps values from received "User Information Reply" 	
	def updateUserInformationStatusConfigUi(self, localProps, varList, newByte):
		address = 7
		bitLocation = 0
		for i in varList:
			var = varList[address]
			bit = newByte[address]
	#		self.plugin.debugLog(u"updateUserInformationStatusConfigUi:        updating device config ui variable: %r,  value: %r,  address: %r" % (var, bit, bitLocation))
			localProps[var] = bit
			address -= 1
			bitLocation += 1
		return localProps
		
	# update User Information Status States from received "User Information Reply" 	
	def updateUserInformationStatus(self, dev, varList, newByte):
		if newByte != None:
			address = 7
			bitLocation = 0
			for i in newByte:
				var = varList[address]
				bit = newByte[address]
	#			self.plugin.debugLog(u"updateUserInformationStatus:        updating device state variable: %r,  value: %r,  address: %r" % (var, bit, bitLocation))
				dev.updateStateOnServer(key=var, value=bit)
				address -= 1
				bitLocation += 1	
				
	################################################################################	
	# Routine for Alarm Panel Lookup Dictionaries method 	(state translation tables for message number and log events)
	################################################################################	
	
	########################################
	# translate message number to message description
	########################################
	def messageAlarmDict(self, kmessageNumber):
		messageNumber = str(kmessageNumber)
		self.alarmDict= {"01":"Interface Configuration Message",
					"03":"Zone Name Message",
					"04":"Zone Status Message",
					"05":"Zones Snapshot Message",
					"06":"Partition Status Message",
					"07":"Partitions Snapshot Message",
					"08":"System Status Message",
					"09":"X-10 Message Received",
					"0a":"Log Event Message",
					"0b":"Keypad Message Received",
					"10":"Program Data Reply",
					"12":"User Information Reply",
					"1c":"Command / Request Failed",
					"1d":"ACK",
					"1e":"NAK",
					"1f":"CAN",
					"21":"Interface Configuration Request",
					"23":"Zone Name Request",
					"24":"Zone Status Request",
					"25":"Zones Snapshot Request",
					"26":"Partition Status Request",
					"27":"Partitions Snapshot Request",
					"28":"System Status Request",
					"29":"Send X-10 Message",
					"2a":"Log Event Request",
					"2b":"Send Keypad Text Message",
					"2c":"Keypad Terminal Mode Request",
					"30":"Program Data Request",
					"31":"Program Data Command",
					"32":"User Information Request with Pin",
					"33":"User Information Request without Pin",
					"34":"Set User Code Command with Pin",
					"35":"Set User Code Command without Pin",
					"36":"Set User Authorisation Command with Pin",
					"37":"Set User Authorisation Command without Pin",
					"3a":"Store Communication Event Command",
					"3b":"Set Date / Time Command",
					"3c":"Primary Keypad Function with Pin",
					"3d":"Primary Keypad Function without Pin",
					"3e":"Secondary Keypad Function",
					"3f":"Zone Bypass Toggle",
					"81":"Interface Configuration Message",
					"83":"Zone Name Message",
					"84":"Zone Status Message",
					"85":"Zones Snapshot Message",
					"86":"Partition Status Message",
					"87":"Partitions Snapshot Message",
					"88":"System Status Message",
					"89":"X-10 Message Received",
					"8a":"Log Event Message",
					"8b":"Keypad Message Received",
					"a9":"Send X-10 Message",
					"ab":"Send Keypad Text Message",
					"ac":"Keypad Terminal Mode Request",
					"b1":"Program Data Command",
					"b4":"Set User Code Command with Pin",
					"b5":"Set User Code Command without Pin",
					"b6":"Set User Authorisation Command with Pin",
					"b7":"Set User Authorisation Command without Pin",
					"ba":"Store Communication Event Command",
					"bb":"Set Clock / Calender Command",
					"bc":"Primary Keypad Function with Pin",
					"bd":"Primary Keypad Function without Pin",
					"be":"Secondary Keypad Function",
					"bf":"Zone Bypass Toggle",
					"ff":"end of file"
					}
		message = self.alarmDict[messageNumber]
		return message
		
	########################################
	# translate log event type number to an event desription
	########################################
	
	def messageLogEventDict(self, keventType):
		eventType = str(keventType)
		self.eventDict = {"0":"Alarm",
						"1":"Alarm Restore",
						"2":"Bypass",
						"3":"Bypass Restore",
						"4":"Tamper",
						"5":"Tamper Restore",
						"6":"Trouble",
						"7":"Trouble Restore",
						"8":"Tx Low Battery",
						"9":"Tx Low Battery Restore",
						"10":"Zone Lost",
						"11":"Zone Lost Restore",
						"12":"Not Used",
						"13":"Not Used",
						"14":"Not Used",
						"15":"Not Used",
						"16":"Not Used",
						"17":"Special Expansion Event",
						"18":"Duress",
						"19":"Fire Alert (Manual)",
						"20":"Medical Alert",
						"21":"Not Used",
						"22":"Police Panic",
						"23":"Keypad Tamper",
						"24":"Control Box Tamper",
						"25":"Control Box Tamper Restore",
						"26":"AC Failure",
						"27":"AC Failure Restore",
						"28":"Low Battery",
						"29":"Low Battery Restore",
						"30":"Overcurrent",
						"31":"Overcurrent Restore",
						"32":"Siren Tamper",
						"33":"Siren Tamper Restore",
						"34":"Telephone Fault",
						"35":"Telephone Fault Restore",
						"36":"Expander Trouble",
						"37":"Expander Trouble Restore",
						"38":"Fail To Communicate",
						"39":"Log Full",
						"40":"Opening",
						"41":"Closing",
						"42":"Exit Error",
						"43":"Recent Closing",
						"44":"Auto Test",
						"45":"Start Program",
						"46":"End Program",
						"47":"Start Download",
						"48":"End Download",
						"49":"Cancel",
						"50":"Ground Fault",
						"51":"Ground Fault Restore",
						"52":"Manual Test",
						"53":"Closed with Zones Bypassed",
						"54":"Start of Listen In",
						"55":"Technician On Site",
						"56":"Technician Left",
						"57":"Control Power Up",
						"119":"Not Used",
						"120":"First To Open",
						"121":"Last to Close",
						"122":"Pin Entered with Bit 7 Set",
						"123":"Begin Walk Test",
						"124":"End Walk Test",
						"125":"Re-Exit",
						"126":"Output Trip",
						"127":"Data Lost"
					}
		event = self.eventDict[eventType]
		self.plugin.debugLog(u"messageLogEventDict:        event number \"%s\" " % eventType)
		self.plugin.debugLog(u"messageLogEventDict:        event description \"%s\" " % event)
		return event
									
	########################################
	# translate log byte 5 to zone, user or device
	########################################
	
	def messageLogByte5Dict(self, keventType):
		eventType = str(keventType)
		self.byte5Dict = {"0":"zone",
						"1":"zone",
						"2":"zone",
						"3":"zone",
						"4":"zone",
						"5":"zone",
						"6":"zone",
						"7":"zone",
						"8":"zone",
						"9":"zone",
						"10":"zone",
						"11":"zone",
						"12":"zone",
						"13":"none",
						"14":"none",
						"15":"none",
						"16":"none",
						"17":"none",
						"18":"none",
						"19":"none",
						"20":"none",
						"21":"none",
						"22":"none",
						"23":"none",
						"24":"device",
						"25":"device",
						"26":"device",
						"27":"device",
						"28":"device",
						"29":"device",
						"30":"device",
						"31":"device",
						"32":"device",
						"33":"device",
						"34":"none",
						"35":"none",
						"36":"device",
						"37":"device",
						"38":"none",
						"39":"none",
						"40":"user",
						"41":"user",
						"42":"user",
						"43":"user",
						"44":"none",
						"45":"none",
						"46":"none",
						"47":"none",
						"48":"none",
						"49":"user",
						"50":"none",
						"51":"none",
						"52":"none",
						"53":"user",
						"54":"none",
						"55":"none",
						"56":"none",
						"57":"none",
						"119":"none",
						"120":"user",
						"121":"user",
						"122":"user",
						"123":"none",
						"124":"none",
						"125":"none",
						"126":"user",
						"127":"none"
					}
		byte5Value = self.byte5Dict[eventType]
		self.plugin.debugLog(u"messageLogByte5Dict:        event number: \"%s\" " % eventType)
		self.plugin.debugLog(u"messageLogByte5Dict:        zone,  device,  user: \"%s\" " % byte5Value)
		return byte5Value
		
	########################################
	# translate log byte 6 to reference partition or not	
	########################################
	
	def messageLogByte6Dict(self, keventType):
		eventType = str(keventType)
		self.byte6Dict = {"0":True,
						"1":True,
						"2":True,
						"3":True,
						"4":True,
						"5":True,
						"6":True,
						"7":True,
						"8":True,
						"9":True,
						"10":True,
						"11":True,
						"12":True,
						"13":False,
						"14":False,
						"15":False,
						"16":False,
						"17":False,
						"18":True,
						"19":True,
						"20":True,
						"21":False,
						"22":True,
						"23":True,
						"24":False,
						"25":False,
						"26":False,
						"27":False,
						"28":False,
						"29":False,
						"30":False,
						"31":False,
						"32":False,
						"33":False,
						"34":False,
						"35":False,
						"36":False,
						"37":False,
						"38":False,
						"39":False,
						"40":True,
						"41":True,
						"42":True,
						"43":True,
						"44":False,
						"45":False,
						"46":False,
						"47":False,
						"48":False,
						"49":True,
						"50":False,
						"51":False,
						"52":False,
						"53":True,
						"54":False,
						"55":False,
						"56":False,
						"57":False,
						"119":False,
						"120":True,
						"121":True,
						"122":True,
						"123":False,
						"124":False,
						"125":True,
						"126":False,
						"127":False
					}
		byte6Valid = self.byte6Dict[eventType]
		self.plugin.debugLog(u"messageLogByte6Dict:        event number: \"%s\" " % eventType)
		self.plugin.debugLog(u"messageLogByte6Dict:        partition valid: \"%s\" " % byte6Valid)		
		return byte6Valid
		
	########################################
	# translate log device address to a module description
	########################################
	
	def messageLogDeviceAddressDict(self, kdeviceAddress):
		deviceAddress = str(kdeviceAddress)
		self.deviceDict = {"0":"Security Panel",
						"16":"Hardwired Expander NX-216E (start zone 17)",
						"17":"Hardwired Expander NX-216E (start zone 25)",
						"18":"Hardwired Expander NX-216E (start zone 33)",
						"19":"Hardwired Expander NX-216E (start zone 41)",
						"20":"Hardwired Expander NX-216E (start zone 49)",
						"21":"Hardwired Expander NX-216E (start zone 57)",
						"23":"Hardwired Expander NX-216E (start zone 09)",
						"24":"Relay Expander NX-507E or Output Expander NX-508E (module 1)",
						"25":"Relay Expander NX-507E or Output Expander NX-508E (module 2)",
						"26":"Relay Expander NX-507E or Output Expander NX-508E (module 3)",
						"27":"Relay Expander NX-507E or Output Expander NX-508E (module 4)",
						"28":"Relay Expander NX-507E or Output Expander NX-508E (module 5)",
						"29":"Relay Expander NX-507E or Output Expander NX-508E (module 6)",
						"30":"Relay Expander NX-507E or Output Expander NX-508E (module 7)",
						"31":"Relay Expander NX-507E or Output Expander NX-508E (module 8)",
						"32":"Wireless Receiver NX-448E (module 6)",
						"33":"Wireless Receiver NX-448E (module 7)",
						"34":"Wireless Receiver NX-448E (module 8)",
						"35":"Wireless Receiver NX-448E (module 1)",
						"36":"Wireless Receiver NX-448E (module 2)",
						"37":"Wireless Receiver NX-448E (module 3)",
						"38":"Wireless Receiver NX-448E (module 4)",
						"39":"Wireless Receiver NX-448E (module 5)",
						"84":"Remote Power Supply NX-320E (module 1)",
						"85":"Remote Power Supply NX-320E (module 2)",
						"86":"Remote Power Supply NX-320E (module 3)",
						"87":"Remote Power Supply NX-320E (module 4)",
						"88":"Remote Power Supply NX-320E (module 5)",
						"89":"Remote Power Supply NX-320E (module 6)",
						"90":"Remote Power Supply NX-320E (module 7)",
						"91":"Remote Power Supply NX-320E (module 8)",
						"96":"Hardwired Expander NX-216E (start zone 65)",
						"97":"Hardwired Expander NX-216E (start zone 73)",
						"98":"Hardwired Expander NX-216E (start zone 81)",
						"99":"Hardwired Expander NX-216E (start zone 89)",
						"100":"Hardwired Expander NX-216E (start zone 97)",
						"101":"Hardwired Expander NX-216E (start zone 105)",
						"102":"Hardwired Expander NX-216E (start zone 113)",
						"103":"Hardwired Expander NX-216E (start zone 121)",
						"104":"Hardwired Expander NX-216E (start zone 129)",
						"105":"Hardwired Expander NX-216E (start zone 137)",
						"106":"Hardwired Expander NX-216E (start zone 145)",
						"107":"Hardwired Expander NX-216E (start zone 153)",
						"108":"Hardwired Expander NX-216E (start zone 161)",
						"109":"Hardwired Expander NX-216E (start zone 169)",
						"110":"Hardwired Expander NX-216E (start zone 177)",
						"111":"Hardwired Expander NX-216E (start zone 185)",
						"192":"Keypad (1)",
						"193":"Keypad (1)",
						"194":"Keypad (1)",
						"195":"Keypad (1)",
						"196":"Keypad (1)",
						"197":"Keypad (1)",
						"198":"Keypad (1)",
						"199":"Keypad (1)",
						"200":"Keypad (2)",
						"201":"Keypad (2)",
						"202":"Keypad (2)",
						"203":"Keypad (2)",
						"204":"Keypad (2)",
						"205":"Keypad (2)",
						"206":"Keypad (2)",
						"207":"Keypad (2)",
						"208":"Keypad (3)",
						"209":"Keypad (3)",
						"210":"Keypad (3)",
						"211":"Keypad (3)",
						"212":"Keypad (3)",
						"213":"Keypad (3)",
						"214":"Keypad (3)",
						"215":"Keypad (3)",
						"216":"Keypad (4)",
						"217":"Keypad (4)",
						"218":"Keypad (4)",
						"219":"Keypad (4)",
						"220":"Keypad (4)",
						"221":"Keypad (4)",
						"222":"Keypad (4)",
						"223":"Keypad (4)",
						"224":"Keypad (5)",
						"225":"Keypad (5)",
						"226":"Keypad (5)",
						"227":"Keypad (5)",
						"228":"Keypad (5)",
						"229":"Keypad (5)",
						"230":"Keypad (5)",
						"231":"Keypad (5)",
						"232":"Keypad (6)",
						"233":"Keypad (6)",
						"234":"Keypad (6)",
						"235":"Keypad (6)",
						"236":"Keypad (6)",
						"237":"Keypad (6)",
						"238":"Keypad (6)",
						"239":"Keypad (6)",
						"240":"Keypad (7)",
						"241":"Keypad (7)",
						"242":"Keypad (7)",
						"243":"Keypad (7)",
						"244":"Keypad (7)",
						"245":"Keypad (7)",
						"246":"Keypad (7)",
						"247":"Keypad (7)",
						"248":"Keypad (8)",
						"249":"Keypad (8)",
						"250":"Keypad (8)",
						"251":"Keypad (8)",
						"252":"Keypad (8)",
						"253":"Keypad (8)",
						"254":"Keypad (8)",
						"255":"Keypad (8)"
						}
		device = self.deviceDict[deviceAddress]
		self.plugin.debugLog(u"messageLogEventDict:        device: \"%s\" " % device)
		return device		
	
################################################################################
# end of Caddx.py file
################################################################################
