#! /usr/bin/env python
# -*- coding: utf-8 -*-
################################################################################
# This is an Indigo 5.0 plugin to support the "Caddx NetworX Series Alarm System"
# Written 2011 by Ian Sibley
################################################################################

################################################################################
# Python Imports
################################################################################
import os
import sys
import time

################################################################################
# Local Imports
################################################################################
from caddx	import Caddx
from string	import atoi, atof

################################################################################
# Globals
################################################################################


################################################################################
class Plugin(indigo.PluginBase):
	
	########################################
		
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
		
		self.caddx = Caddx(self)
		self.debug = pluginPrefs.get("showDebugInfo", False)
		if self.debug:
			indigo.server.log (u"Debug logging is enabled")
		else:	
			indigo.server.log (u"Debug logging is disabled")
		self.devicePort = self.getSerialPortUrl(pluginPrefs, u'devicePort')
		self.watchdogTimerPeriod = atof(pluginPrefs.get("watchdogTimerPeriod", 0))
		self.sleepBetweenIdlePoll = atof(pluginPrefs.get("sleepBetweenIdlePoll", 0.01))
		self.sleepBetweenComm = atof(pluginPrefs.get("sleepBetweenComm", 0.3))
		self.sleepBetweenCreateZone = atof(pluginPrefs.get("sleepBetweenCreateZone", 1.0))
		self.enableSpeakPrompts = pluginPrefs.get("enableSpeak", False)
		self.alarmEventInfo = pluginPrefs.get("showAlarmEventInfo", False)
		self.commandActInfo = pluginPrefs.get("showCommandActInfo", False)
		self.partitionActInfo = pluginPrefs.get("showPartitionActInfo", False)
		self.zoneActInfo = pluginPrefs.get("showZoneActInfo", False)
		self.messageActInfo = pluginPrefs.get("showMessageActInfo", False)
		self.messageProcessInfo = pluginPrefs.get("showMessageProcessInfo", False)
		
	########################################
	def __del__(self):
		indigo.PluginBase.__del__(self)
		
	########################################
	# Plugin Start and Stop methods	
	########################################
		
	def startup(self):
		self.debugLog(u"startup:        process called for caddx plugin ")

	def shutdown(self):
		self.debugLog(u"shutdown:        process called for caddx plugin ")
		
	########################################
	# Device Start and Stop methods	
	########################################
	
	def deviceStartComm(self, dev):
	#	self.debugLog(u"deviceStartComm:        entering process %s (%d - %s)" % (dev.name, dev.id, dev.deviceTypeId))
		self.caddx.deviceStart(dev)
		
	def deviceStopComm(self, dev):
	#	self.debugLog(u"deviceStopComm:        entering process %s (%d - %s)" % (dev.name, dev.id, dev.deviceTypeId))
		self.caddx.deviceStop(dev)

	########################################
	# Trigger Start and Stop methods	
	########################################
	
	def triggerStartProcessing(self, trigger):
		self.debugLog(u"triggerStartProcessing:        entering process %s (%d)" % (trigger.name, trigger.id))
		self.caddx.triggerStart(trigger)
		
	def triggerStopProcessing(self, trigger):
		self.debugLog(u"triggerStopProcessing:        entering process %s (%d)" % (trigger.name, trigger.id))
		self.caddx.triggerStop(trigger)
	
	########################################
	# Run Concurrent Thread Start and Stop methods	
	########################################
			
	def runConcurrentThread(self):
		self.debugLog(u"runConcurrentThread:        entering process")
		if self.devicePort == None:
			indigo.server.log (u"The Caddx communication parameters are not yet configured. Please configure in the plugin configuration.")
			pass
		else:	
			self.caddx.startComm()
		self.debugLog(u"runConcurrentThread:        exiting process")	
		
	def stopConcurrentThread(self):
		self.debugLog(u"stopConcurrentThread:        entering process")
		self.caddx.stopComm()
		self.debugLog(u"stopConcurrentThread:        exiting process")	
		
	########################################
	# Preference Validation methods 
    ########################################

	def validatePrefsConfigUi(self, valuesDict):
		self.debugLog(u"validatePrefsConfigUi:        entering process")
		errorsDict = indigo.Dict()
		self.validateSerialPortUi(valuesDict, errorsDict, u"devicePort")
		if valuesDict.get(u"masterCode", u"") == "1234":					# User has not changed default Master Code -- show an error.
			errorsDict = indigo.Dict()
			errorsDict[u'masterCode'] = u"Select a new Master Code"
			self.debugLog(u"validateDeviceConfigUi:        Select a new Master Code")
			return (False, valuesDict, errorsDict)
		elif atoi(valuesDict.get(u"codeLength", u"")) != len(valuesDict.get(u"masterCode", u"")):	# User Master Code number of digits does not match the Code Length set-- show an error.	
			errorsDict = indigo.Dict()
			errorsDict[u'masterCode'] = u"Master Code number of digits must equal the Code Length set"
			self.debugLog(u"validateDeviceConfigUi:        Master Code number of digits must equal the Code Length set")
			return (False, valuesDict, errorsDict)
			
		if len(errorsDict) > 0:			# Some UI fields are not valid, return corrected fields and error messages (client will not let the dialog window close).
			return (False, valuesDict, errorsDict)

		self.debugLog(u"validatePrefsConfigUi:        exiting process")
		return (True, valuesDict)

	########################################
	# Preference close dialog methods 
    ########################################
	
	def closedPrefsConfigUi(self, valuesDict, userCancelled):
		self.debugLog(u"closedPrefsConfigUi:        entering process")

		if not userCancelled:
			indigo.server.log (u"Plugin configuration preferences were updated, reloading preferences .....")
			self.devicePort = self.getSerialPortUrl(valuesDict, u'devicePort')
			self.watchdogTimerPeriod = atof(valuesDict.get("watchdogTimerPeriod", 0))
			self.sleepBetweenIdlePoll = atof(valuesDict.get("sleepBetweenIdlePoll", 0.01))
			self.sleepBetweenComm = atof(valuesDict.get("sleepBetweenComm", 0.3))
			self.sleepBetweenCreateZone = atof(valuesDict.get("sleepBetweenCreateZone", 1.0))
			self.enableSpeakPrompts = valuesDict.get("enableSpeak", False)
			self.alarmEventInfo = valuesDict.get("showAlarmEventInfo", False)
			self.commandActInfo = valuesDict.get("showCommandActInfo", False)
			self.partitionActInfo = valuesDict.get("showPartitionActInfo", False)
			self.zoneActInfo = valuesDict.get("showZoneActInfo", False)
			self.messageActInfo = valuesDict.get("showMessageActInfo", False)
			self.messageProcessInfo = valuesDict.get("showMessageProcessInfo", False)
			self.debug = valuesDict.get("showDebugInfo", False)
			
			indigo.server.log(u". . Loading new plugin preferences ...")
			indigo.server.log(u"")
			indigo.server.log(u". .       Communication:             interface: %s," % (self.devicePort))
			indigo.server.log(u". .                                  baud rate: %s," % (valuesDict.get("serialBaudRate", None)))
			indigo.server.log(u". .                                    timeout: %s seconds," % (valuesDict.get("serialTimeout", None)))
			indigo.server.log(u"")
			indigo.server.log(u". .    	  Plugin Timers:   sleep between polls: %s seconds," % (valuesDict.get("sleepBetweenIdlePoll", None)))
			indigo.server.log(u". .                     sleep between commands: %s seconds," % (valuesDict.get("sleepBetweenComm", None)))
			indigo.server.log(u". .                  sleep between create zone: %s seconds," % (valuesDict.get("sleepBetweenCreateZone", None)))
			indigo.server.log(u"")
			indigo.server.log(u". .      Base Transport:           port status: %s," % (valuesDict.get("portStatus", None)))
			indigo.server.log(u". .                               comm failure: %s," % (valuesDict.get("communicationFailure", None)))
			indigo.server.log(u". .                          last failure time: %s," % (valuesDict.get("lastFailureTime", None)))
			indigo.server.log(u". .                            watch dog timer: %s seconds," % (valuesDict.get("watchdogTimerPeriod", None)))
			indigo.server.log(u". .                       active communication: %s," % (valuesDict.get("activeCommunication", None)))
			indigo.server.log(u"")
			indigo.server.log(u". .        Caddx Object:            panel name: %s," % (valuesDict.get("panelName", None)))
			indigo.server.log(u". .                                 panel type: %s," % (valuesDict.get("panelType", None)))
			indigo.server.log(u". .                                   location: %s," % (valuesDict.get("panelLocation", None)))
			indigo.server.log(u". .                             speach enabled: %s," % (valuesDict.get("enableSpeak", None)))
			indigo.server.log(u"")
			indigo.server.log(u". .       Configuration:              firmware: %s," % (valuesDict.get("firmware", None)))
			indigo.server.log(u". .                                master code: %s," % (valuesDict.get("masterCode", None)))
			indigo.server.log(u". .                                code length: %s," % (valuesDict.get("codeLength", None)))
			indigo.server.log(u". .                                 partitions: %s," % (valuesDict.get("partitionsSystem", None)))
			indigo.server.log(u". .                                      users: %s," % (valuesDict.get("usersSystem", None)))
			indigo.server.log(u". .                                      zones: %s," % (valuesDict.get("zonesSystem", None)))
			indigo.server.log(u". .                        syncing in progress: %s," % (valuesDict.get("isSynchronising", None)))
			indigo.server.log(u". .                               synchronised: %s," % (valuesDict.get("synchronised", None)))
			indigo.server.log(u". .                    keypad being programmed: %s," % (valuesDict.get("isKeypadProgramming", None)))
			indigo.server.log(u". .                               panel status: %s," % (valuesDict.get("panelStatus", None)))
			indigo.server.log(u"")
			indigo.server.log(u". .       Event Logging:          alarm events: %s," % (valuesDict.get("showAlarmEventInfo", None))) 
			indigo.server.log(u". .                            command actions: %s," % (valuesDict.get("showAlarmEventInfo", None)))
			indigo.server.log(u". .                         partition activity: %s," % (valuesDict.get("showPartitionActInfo", None)))
			indigo.server.log(u". .                              zone activity: %s," % (valuesDict.get("showZoneActInfo", None)))
			indigo.server.log(u". .                     communication activity: %s," % (valuesDict.get("showMessageActInfo", None)))
			indigo.server.log(u". .                         message processing: %s," % (valuesDict.get("showMessageProcessInfo", None)))
			indigo.server.log(u"")
			indigo.server.log(u". .     Show Debug Info:  %s " % (valuesDict.get("showDebugInfo", None)))
			indigo.server.log(u"")
			
		self.debugLog(u"closedPrefsConfigUi:        exiting process")
					
	########################################
	# Device Validation methods 
    ########################################
	
	def validateDeviceConfigUi(self, valuesDict, typeId, devId):
		self.debugLog(u"validateDeviceConfigUi:        entering process")
		# ##User choices look good, so return True (client will then close the dialog window)
		self.debugLog(u"validateDeviceConfigUi:        exiting process")
		return True	
	
	def getPartitionList(self, filter="", valuesDict=None, typeId="", targetId=0):
		### read plugin config perference limit parameter settings
		partitionsSystem = int(self.pluginPrefs[u'partitionsSystem'])
		partitionsSystem =  partitionsSystem+ 1			### loop offset to display full partition range	
		myArray = []
		for i in range(1, partitionsSystem):
			myArray.append( ( str(i), str(i) ) )
		return myArray
		
	def getUserList(self, filter="", valuesDict=None, typeId="", targetId=0):
		### read plugin config perference limit parameter settings
		usersSystem = int(self.pluginPrefs[u'usersSystem'])
		usersSystem = usersSystem + 1					### loop offset to display full user range
		myArray = []
		for i in range(1, usersSystem):
			myArray.append( ( str(i), str(i) ) )
		return myArray	
			
	def getZoneList(self, filter="", valuesDict=None, typeId="", targetId=0):
		### read plugin config perference limit parameter settings
		zonesSystem = int(self.pluginPrefs[u'zonesSystem'])
		zonesSystem = zonesSystem + 1					### loop offset to display full zone range
		myArray = []
		for i in range(1, zonesSystem):
			myArray.append( ( str(i), str(i) ) )
		return myArray	
		
	def getZoneOffsetList(self, filter="", valuesDict=None, typeId="", targetId=0):
		### read plugin config perference limit parameter settings
		zoneOffset = 12											### loop offset to display full zone offset
		myArray = []
		for i in range(0, zoneOffset):
			myArray.append( ( str(i), str(i) ) )
		return myArray				
			
	########################################
	# Device close dialog methods
	########################################
			
	def closedDeviceConfigUi(self, valuesDict, userCancelled, typeId, devId):
		self.debugLog(u"closedDeviceConfigUi:        entering process")
		if userCancelled is False:			
			indigo.server.log("closedDeviceConfigUi:        Device preferences were updated, reloading preferences...")
	
		self.debugLog(u"closedDeviceConfigUi:        exiting process")
		pass	
		
	########################################
	# Actions command method routines <action.xml>
	########################################
	
	########################################
	# Indigo Relay / Dimmer Action callback
	########################################
		
	def actionControlDimmerRelay(self, action, dev):
		deviceAction = action.deviceAction
		indigo.server.log(u"ignored \"%s\" %s request (sensor is read-only)" % (dev.name, deviceAction))
	
	########################################	
	# Indigo Sensor Action callback
	########################################
		
	def actionControlSensor(self, action, dev):
		### TURN ON ###
		if action.sensorAction == indigo.kSensorAction.TurnOn:
			indigo.server.log(u"actionControlSensor:        ignored \"%s\" %s request (sensor is read-only)" % (dev.name, "on"))
		### TURN OFF ###
		elif action.sensorAction == indigo.kSensorAction.TurnOff:
			indigo.server.log(u"actionControlSensor:        ignored \"%s\" %s request (sensor is read-only)" % (dev.name, "off"))
		### TOGGLE ###	
		elif action.sensorAction == indigo.kSensorAction.Toggle:
			indigo.server.log(u"actionControlSensor:        ignored \"%s\" %s request (sensor is read-only)" % (dev.name, "toggle"))
		### STATUS REQUEST ###	
		elif action.sensorAction == indigo.kSensorAction.RequestStatus:
			# Query hardware module (dev) for its current states here:
			# ** IMPLEMENT ME **
			indigo.server.log(u"actionControlSensor:        sent \"%s\" %s" % (dev.name, "status request"))
	
	########################################	
	# Plugin Custom Action callback
	########################################

	# Primary Keypad Functions
	
	def methodArmStay(self, pluginAction):													# command action: --> Arm Alarm in Stay Mode <--
		self.caddx._actionGeneric(pluginAction, "Arm in Stay Mode")
	def methodArmAway(self, pluginAction):													# command action: --> Arm Alarm in Away Mode <--
		self.caddx._actionGeneric(pluginAction, "Arm in Away Mode")	
	def methodDisarm(self, pluginAction):													# command action: --> Disarm System <--
		self.caddx._actionGeneric(pluginAction, "Disarm System")
	def methodFirePanic(self, pluginAction):												# command action: --> Activate Fire Panic <--
		self.caddx._actionGeneric(pluginAction, "Activate Fire Panic")
	def methodMedicalPanic(self, pluginAction):												# command action: --> Activate Medical Panic <--
		self.caddx.actionGeneric(pluginAction, "Activate Medical Panic")
	def methodPoliceDuress(self, pluginAction):												# command action: --> Activate Police Duress <--
		self.caddx._actionGeneric(pluginAction, "Activate Police Duress")	
	def methodTurnOffSounderOrAlarm(self, pluginAction):									# command action: --> Turn Off Any Sounder or Alarm<--
		self.caddx._actionGeneric(pluginAction, "Turn Off Any Sounder or Alarm")
	def methodCancel(self, pluginAction):													# command action: --> Cancel <--
		self.caddx._actionGeneric(pluginAction, "Cancel")
	def methodInitiateAutoArm(self, pluginAction):											# command action: --> Initiate Auto Arm <--
		self.caddx._actionGeneric(pluginAction, "Initiate Auto Arm")
	def methodStartWalkTestMode(self, pluginAction):										# command action: --> Start Walk Test Mode <--
		self.caddx.actionGeneric(pluginAction, "Start Walk Test Mode")
	def methodStopWalkTestMode(self, pluginAction):  										# command action: --> Stop Walk Test Mode <--
		self.caddx.actionGeneric(pluginAction, "Stop Walk Test Mode")
	
	# Secondary Keypad Functions
	
	def methodStay1ButtonArmToggleInteriors(self, pluginAction):							# command action: --> Stay (1 button arm / toggle Interiors) <--
		self.caddx._actionGeneric(pluginAction, "Stay 1 Button Arm Toggle Interiors")
	def methodChimeToggleChimeMode(self, pluginAction):										# command action: --> Chime (toggle Chime Mode) <--
		self.caddx._actionGeneric(pluginAction, "Toggle Chime Mode")
	def methodExitButtonArmToggleInstant(self, pluginAction):								# command action: --> Exit (1 button arm / toggle Instant) <--
		self.caddx._actionGeneric(pluginAction, "Exit 1 Button Arm Toggle Instant")
	def methodBypassInteriors(self, pluginAction):											# command action: --> Bypass Interiors <--
		self.caddx._actionGeneric(pluginAction, "Bypass Interiors")
	def methodSmokeDetectorReset(self, pluginAction):										#  command action: --> Reset Smoke Detectors <--
		self.caddx._actionGeneric(pluginAction, "Reset Smoke Detectors")
	def methodAutoCallbackDownload(self, pluginAction):										# command action: --> Auto Callback Download <--
		self.caddx._actionGeneric(pluginAction, "Auto Callback Download")
	def methodManualPickupDownload(self, pluginAction):										# command action: --> Manual Pickup Download <--
		self.caddx._actionGeneric(pluginAction, "Manual Pickup Download")
	def methodEnableSilentExitForThisArmCycle(self, pluginAction):							# command action: --> Enable Silent Exit for this Arm Cycle <--
		self.caddx._actionGeneric(pluginAction, "Enable Silent Exit for this Arm Cycle")
	def methodPerformTest(self, pluginAction):												# command action: --> Perform Test <--
		self.caddx._actionGeneric(pluginAction, "Perform Test")
	def methodGroupBypass(self, pluginAction):												# command action: --> Group Bypass <--
		self.caddx._actionGeneric(pluginAction, "Group Bypass")
	def methodAuxiliaryFunction1(self, pluginAction):										# command action: --> Auxiliary Function 1 <--
		self.caddx._actionGeneric(pluginAction, "Auxiliary Function 1")
	def methodAuxiliaryFunction2(self, pluginAction):										# command action: --> Auxiliary Function 2 <--
		self.caddx._actionGeneric(pluginAction, "Auxiliary Function 2")
	def methodStartKeypadSounder(self, pluginAction):										# command action: --> Start Keypad Sounder <--
		self.caddx.actionGeneric(pluginAction, "Start Keypad Sounder")
	
	# Requested Alarm Panel Messages and Commands
	
	def methodInterfaceConfigurationRequest(self, pluginAction):							# command action: --> Interface Configuration Request <--					
		self.caddx._actionCmdMessage(pluginAction, "Interface Configuration Request")
	def methodZoneNameRequest(self, pluginAction):											#  command action: --> Zone Name Request <--
		self.caddx._actionCmdMessage(pluginAction, "Zone Name Request")
	def methodZoneStatusRequest(self, pluginAction):										# command action: --> Zone Status Request <--
		self.caddx_.actionCmdMessage(pluginAction, "Zone Status Request")			
	def methodZonesSnapshotRequest(self, pluginAction):										# command action: --> Zones Snapshot Request <--
		self.caddx._actionCmdMessage(pluginAction, "Zones Snapshot Request")
	def methodPartitionStatusRequest(self, pluginAction):									# command action: --> Partition Status Request <--
		self.caddx._actionCmdMessage(pluginAction, "Partition Status Request")		
	def methodPartitionSnapshotRequest(self, pluginAction):									# command action: --> Partition Snapshot Request <--
		self.caddx._actionCmdMessage(pluginAction, "Partition Snapshot Request")	
	def methodSystemStatusRequest(self, pluginAction):										# command action: --> System Status Request <--
		self.caddx._actionCmdMessage(pluginAction, "System Status Request")					
	def methodLogEventRequest(self, pluginAction):											# command action: --> Log Event Request <--
		self.caddx._actionCmdMessage(pluginAction, "Log Event Request")					
	def methodSendKeypadTextMessage(self, pluginAction):									# command action: --> Send Keypad Text Message <--
		self.caddx._actionCmdMessage(pluginAction, "Send Keypad Text Message")					
	def methodKeypadTerminalModeRequest(self, pluginAction):								# command action: --> Keypad Terminal Mode Request <--
		self.caddx._actionCmdMessage(pluginAction, "Keypad Terminal Mode Request")	
	def methodUserInformationRequestWithoutPin(self, pluginAction):							# command action: --> User Information Request without Pin <--
		self.caddx._actionCmdMessage(pluginAction, "User Information Request without Pin")	
	def methodSetClockCalenderCommand(self, pluginAction):									# command action: --> Set Clock/ Calender <--
		self.caddx._actionCmdMessage(pluginAction, "Set Clock and Calender")	
	def methodZoneBypassToggle(self, pluginAction):											# command action: --> Zone Bypass Toggle <--
		self.caddx._actionCmdMessage(pluginAction, "Zone Bypass toggle")		
	
	########################################	
	# Plugin Config Action callback
	########################################

	#  synchronise the Indigo device databases with the Caddx NetworX alarm panel database
	def configSyncDatabase(self, pluginAction):	
		indigo.server.log("configSyncDatabase:        start database sync process") 
		self.syncDatabase()
		
	########################################
	# Menu - Create Basic Alarm System Devices method
	########################################
	# create all indigo basic system indigo devices for the Caddx NetworX alarm system
	
	def createAlarmSystemDevices(self):	
	#	self._createInterfaceOptions()
		self._createStatusInfo()
		self._createAlarmPartitions()
		self._createAlarmKeypads()
   		self._createAlarmUsers()
   		self._createAlarmZones()
   	
   	def _createInterfaceOptions(self):						# create interface message options device	
		panel = 1
		if panel in self.caddx.panelList.keys():
			indigo.server.log("createInterfaceOptions:        Alarm device interface message options already exists")
		else:						
			indigo.server.log("createInterfaceOptions:        Creating alarm device interface message options")
			deviceName = "interface options"
			indigo.device.create(protocol = indigo.kProtocol.Plugin,
  			address = "",
   			name = deviceName, 
   			description = "interface options", 
   			pluginId = "com.ians.caddx",
   			deviceTypeId = "panel",
   		 	props = {"address" : panel}
   		 	)
   	
   	def _createStatusInfo(self):							# create system status information device	
		systemId = 1
		if systemId in self.caddx.systemStatusList.keys():
			indigo.server.log("createSystemStatusInfo:        Alarm device system status info already exists")
		else:						
			indigo.server.log("createSystemStatusInfo:        Creating alarm device system status info")
			deviceName = "status info"
			indigo.device.create(protocol = indigo.kProtocol.Plugin,
  			address = "",
   			name = deviceName, 
   			description = "system status info", 
   			pluginId = "com.ians.caddx",
   			deviceTypeId = "statusInfo",
   		 	props = {"address" : systemId}
   		 	)
   	 	
   	def _createAlarmPartitions(self):						# read plugin config perference limit parameter settings
		partitionsSystem = int(self.pluginPrefs[u'partitionsSystem'])		# create alarm partitions from 1 to partitionsSystem value	
		for key in range(0,partitionsSystem):	
			key = (key + 1)
			partition = str(key)
			keypad = partition
			partitionName = "Alarm Partition %s" % partition
			if key in self.caddx.partitionList.keys():
				indigo.server.log("createAlarmPartitions:        Alarm device partition: %s already exists" % key)
			else:						
				indigo.server.log("createAlarmPartitions:        Creating alarm device partition: %s" % key)
				deviceName = "alarm partition"
				indigo.device.create(protocol = indigo.kProtocol.Plugin,
  				address = "",
   				name = deviceName, 
   				description = "alarm partition %s" % partition, 
   				pluginId = "com.ians.caddx",
   				deviceTypeId = "partition",
   			 	props = {"address" : partition, "associatedKeypad" : keypad, "partitionName" : partitionName}
   			 	)
   			 	
   	def _createAlarmKeypads(self):							# create alarm keypad for partition 1 	
		keypad = 1
		keypadName = "Keypad"
		if keypad in self.caddx.keypadList.keys():
			indigo.server.log("createAlarmKeypads:        Alarm device keypad: %s already exists" % keypad)
		else:						
			indigo.server.log("createAlarmKeypads:        Creating alarm device keypad: %s" % keypad)
			deviceName = "alarm keypad"
			indigo.device.create(protocol = indigo.kProtocol.Plugin,
  			address = "",
   			name = deviceName, 
   			description = "alarm keypad %s" % keypad, 
   			pluginId = "com.ians.caddx",
   			deviceTypeId = "keypad",
   		 	props = {"address" : keypad, "keypadName" : keypadName}
   		 	)		 	
   	
   	def _createAlarmUsers(self):							# read plugin config perference limit parameter settings
		usersSystem = int(self.pluginPrefs[u'usersSystem'])			# create alarm users from 1 to usersSystem value	
		for key in range(0,usersSystem):	
			key = (key + 1)
			user = str(key)
			if key in self.caddx.userList.keys():
				indigo.server.log("createAlarmUsers:        Alarm device user: %r already exists" % key)
			else:
				if key <= 9:
					userNumber = "0" + user
				else:
					userNumber =  user			
				indigo.server.log("createAlarmUsers:        Creating alarm device user: %r" % key)
				deviceName = "user %s" % userNumber
				userName = "Fred %s" % userNumber
				indigo.device.create(protocol = indigo.kProtocol.Plugin,
  				address = "",
   				name = deviceName, 
   				description = "alarm user %s" % userNumber, 
   				pluginId = "com.ians.caddx",
   				deviceTypeId = "user",
   			 	props = {"address" : user, "userName" : userName}
   			 	) 		 	 	
							
	def _createAlarmZones(self):							# create indigo zone devices from 1 to the set value of "zonesSystem" 
		zonesSystem = int(self.pluginPrefs[u'zonesSystem'])			# read plugin config perference limit parameter settings
		for key in range(0,zonesSystem):							# create alarm zones from 1 to zonesSystem value
			key = (key + 1)
			zone = str(key)
			if key in self.caddx.zoneList.keys():
				indigo.server.log("createAlarmZones:        Alarm device zone %r already exists" % key)
			else:	
				if key <= 9:
					zoneName = "zone 00" + zone
				elif key <= 99:
					zoneName = "zone 0" + zone
				else:
					zoneName = "zone " + zone
				self.caddx._singleZoneNameRequest(key -1)			# read alarm zone Keypad Display Name
				displayName = self.caddx.keypadDisplayName
				self.debugLog("createAlarmZones:        key: %r,  displayName: %s" % (key, displayName))	
				indigo.server.log("createAlarmZones:        Creating alarm device zone: %r" % key)		# create specific alarm zone device
				deviceName = "%s - %s " % (zoneName, displayName)
				indigo.device.create(protocol=indigo.kProtocol.Plugin,
   				address="",
   				name=deviceName, 
   				description="security %s" % zoneName, 
   				pluginId="com.ians.caddx",
   				deviceTypeId="zone",
   			 	props={"address" : zone, "zoneName" : deviceName, "zoneDisplayName" : displayName}
   			 	)
    	   	
   	########################################
	# Menu - Synchronise  Database method
	########################################
	
	
	def syncDatabase(self):				#  synchronise the Indigo device databases with the Caddx NetworX alarm panel database
		indigo.server.log("syncDatabase:        start Indigo database synchronisation process with Caddx NetworX Security System database.")
		
		# update sync database states in plugin config perferences
		self.pluginPrefs[u"isSynchronising"] = True
		self.pluginPrefs[u"panelStatus"] = "synchronising Database  ** %s" % self.caddx.timestamp()
		variableID = "panelStatus"
		panelStatusVariable = (u"synchronising Database  ** %s" % self.caddx.timestamp())
		self.caddx.updateVariable(variableID, panelStatusVariable)
		
		# set limit parameters for request commands( determine the range of update requests)
		action = ""
		zonesSnapshotQuery = 12														# 12 blocks of 16 zones = 192 zones
		
		# read plugin config perference limit parameter settings
		partitionsSystem = int(self.pluginPrefs[u'partitionsSystem'])
		usersSystem = int(self.pluginPrefs[u'usersSystem'])
		zonesSystem = int(self.pluginPrefs[u'zonesSystem'])
		
		# execute alarm panel request commands to sync configuration database
		self.caddx._actionInterfaceConfigurationRequest(action)						# command action: --> Interface Configuration Request <--
		self.caddx._actionZoneNameRequest(zonesSystem)								# command action: --> Zone Name Request <--
		self.caddx._actionZoneStatusRequest(zonesSystem)							# command action: --> Zone Status Request <--
		self.caddx._actionZonesSnapshotRequest(zonesSnapshotQuery)					# command action: --> Zones Snapshot Request <--
		self.caddx._actionPartitionStatusRequest(partitionsSystem)					# command action: --> Partition Status Request <--
		self.caddx._actionPartitionSnapshotRequest(action)							# command action: --> Partition Snapshot Request <--
		self.caddx._actionSystemStatusRequest(action)								# command action: --> System Status Request <--
		self.caddx._actionUserInformationRequestWithoutPin(usersSystem)				# command action: --> User Information Request without PIN <--"
		time.sleep(int(0.75*zonesSystem))
		indigo.server.log("syncDatabase:        Indigo database now successfully synchronised with the Caddx NetworX Security System database." )
		
		# update sync database states in plugin perferences
		self.pluginPrefs[u"isSynchronising"] = False
		self.pluginPrefs[u"synchronised"] = True
		self.pluginPrefs[u"panelStatus"] = "synchronise completed  ** %s " % self.caddx.timestamp()
		variableID = "panelStatus"
		panelStatusVariable = (u"synchronise completed  ** %s " % self.caddx.timestamp())
		self.caddx.updateVariable(variableID, panelStatusVariable)

	########################################
	# Menu - Interface Config values to Log method
	########################################
	
	def interfaceMessageConfigToLog(self):		# copy the current alarm panel Interface Configuration Setting to Indigo Event Log
		localPrefsCopy = self.pluginPrefs
		
		indigo.server.log(u"Interface Message Configuration:  . . .")			 
		indigo.server.log(u". . interface option:       interface configuration message: %s," % (self._handleEnabledDisabledState(localPrefsCopy.get("interfaceConfigurationMessage", None))))
		indigo.server.log(u". . interface option:                   zone status message: %s," % (self._handleEnabledDisabledState(localPrefsCopy.get("zoneStatusMessage", None))))
		indigo.server.log(u". . interface option:                 zone snapshot message: %s," % (self._handleEnabledDisabledState(localPrefsCopy.get("zoneSnapshotMessage", None))))
		indigo.server.log(u". . interface option:              partition status message: %s," % (self._handleEnabledDisabledState(localPrefsCopy.get("partitionStatusMessage", None))))
		indigo.server.log(u". . interface option:            partition snapshot message: %s," % (self._handleEnabledDisabledState(localPrefsCopy.get("partitionSnapshotMessage", None))))
		indigo.server.log(u". . interface option:                 system status message: %s," % (self._handleEnabledDisabledState(localPrefsCopy.get("systemStatusMessage", None))))
		indigo.server.log(u". . interface option:                  received X10 message: %s," % (self._handleEnabledDisabledState(localPrefsCopy.get("receivedX10Message", None))))
		indigo.server.log(u". . interface option:                     log event message: %s," % (self._handleEnabledDisabledState(localPrefsCopy.get("logEventReceived", None))))
		indigo.server.log(u". . interface option:               keypad message received: %s," % (self._handleEnabledDisabledState(localPrefsCopy.get("keypadMessageReceived", None))))
		indigo.server.log(u". . interface option:                     zone name request: %s," % (self._handleEnabledDisabledState(localPrefsCopy.get("zoneNameRequest", None))))
		indigo.server.log(u". . interface option:                   zone status request: %s," % (self._handleEnabledDisabledState(localPrefsCopy.get("zoneStatusRequest", None))))
		indigo.server.log(u". . interface option:                 zone snapshot request: %s," % (self._handleEnabledDisabledState(localPrefsCopy.get("zoneSnapshotRequest", None))))
		indigo.server.log(u". . interface option:              partition status request: %s," % (self._handleEnabledDisabledState(localPrefsCopy.get("partitionStatusRequest", None))))
		indigo.server.log(u". . interface option:            partition snapshot request: %s," % (self._handleEnabledDisabledState(localPrefsCopy.get("partitionSnapshotRequest", None))))
		indigo.server.log(u". . interface option:                 system status request: %s," % (self._handleEnabledDisabledState(localPrefsCopy.get("systemStatusRequest", None))))
		indigo.server.log(u". . interface option:                      send X10 message: %s," % (self._handleEnabledDisabledState(localPrefsCopy.get("sendX10Message", None))))
		indigo.server.log(u". . interface option:                     log event request: %s," % (self._handleEnabledDisabledState(localPrefsCopy.get("logEventRequest", None))))
		indigo.server.log(u". . interface option:              send keypad text message: %s," % (self._handleEnabledDisabledState(localPrefsCopy.get("sendKeypadTextMessage", None))))
		indigo.server.log(u". . interface option:          keypad terminal mode request: %s," % (self._handleEnabledDisabledState(localPrefsCopy.get("keypadTerminalModeRequest", None))))
		indigo.server.log(u". . interface option:                  program data request: %s," % (self._handleEnabledDisabledState(localPrefsCopy.get("programDataRequest", None))))
		indigo.server.log(u". . interface option:                  program data command: %s," % (self._handleEnabledDisabledState(localPrefsCopy.get("programDataCommand", None))))
		indigo.server.log(u". . interface option:     set user Auth command without pin: %s," % (self._handleEnabledDisabledState(localPrefsCopy.get("setUserAuthorisationCommandWithoutPin", None))))
		indigo.server.log(u". . interface option:     store communication event command: %s," % (self._handleEnabledDisabledState(localPrefsCopy.get("storeCommunicationEventCommand", None))))
		indigo.server.log(u". . interface option:            set clock calender command: %s," % (self._handleEnabledDisabledState(localPrefsCopy.get("setClockCalenderCommand", None))))
		indigo.server.log(u". . interface option:      primary keypad function with pin: %s," % (self._handleEnabledDisabledState(localPrefsCopy.get("primaryKeypadFunctionWithPin", None))))
		indigo.server.log(u". . interface option:   primary keypad function without pin: %s," % (self._handleEnabledDisabledState(localPrefsCopy.get("primaryKeypadFunctionWithoutPin", None))))
		indigo.server.log(u". . interface option:             secondary keypad function: %s," % (self._handleEnabledDisabledState(localPrefsCopy.get("secondaryKeypadFunction", None))))
		indigo.server.log(u". . interface option:                    zone bypass toggle: %s," % (self._handleEnabledDisabledState(localPrefsCopy.get("zoneBypassToggle", None))))
		indigo.server.log(u"")
		
	def _handleEnabledDisabledState(self, value):
		if value == "1":
			state = "Enabled"
		elif value == "0":
			state = "-------"
		else:
			state = "None"
		return state		
		
	########################################
	# Menu - System Status values to Log method
	########################################
	
	def systemStatusToLog(self):				# copy the current alarm panel System Status Information  to Indigo Event Log
		localPrefsCopy = self.pluginPrefs
		
		indigo.server.log(u"System Status Information: . . .")	
		indigo.server.log(u". . system status:                         line seizure: %s," % (self._handleOnOffState(localPrefsCopy.get("lineSeizure", None))))
		indigo.server.log(u". . system status:                             off hook: %s," % (self._handleOnOffState(localPrefsCopy.get("offHook", None))))
		indigo.server.log(u". . system status:           initial Handshake received: %s," % (self._handleOnOffState(localPrefsCopy.get("initialHandshakeReceived", None))))
		indigo.server.log(u". . system status:                 download in progress: %s," % (self._handleOnOffState(localPrefsCopy.get("downloadInProgress", None))))
		indigo.server.log(u". . system status:             dialer delay in progress: %s," % (self._handleOnOffState(localPrefsCopy.get("dialerDelayInProgress", None))))
		indigo.server.log(u". . system status:                   using backup phone: %s," % (self._handleOnOffState(localPrefsCopy.get("usingBackupPhone", None))))
		indigo.server.log(u". . system status:                     listen in active: %s," % (self._handleOnOffState(localPrefsCopy.get("listenInActive", None))))
		indigo.server.log(u". . system status:                      two way lockout: %s," % (self._handleOnOffState(localPrefsCopy.get("twoWayLockout", None))))
		indigo.server.log(u"")
		indigo.server.log(u". . system status:                         ground fault: %s," % (self._handleOnOffState(localPrefsCopy.get("groundFault", None))))
		indigo.server.log(u". . system status:                          phone fault: %s," % (self._handleOnOffState(localPrefsCopy.get("phoneFault", None))))
		indigo.server.log(u". . system status:                  fail to communicate: %s," % (self._handleOnOffState(localPrefsCopy.get("failToCommunicate", None))))
		indigo.server.log(u". . system status:                           fuse fault: %s," % (self._handleOnOffState(localPrefsCopy.get("fuseFault", None))))
		indigo.server.log(u". . system status:                           box tamper: %s," % (self._handleOnOffState(localPrefsCopy.get("boxTamper", None))))
		indigo.server.log(u". . system status:                         siren tamper: %s," % (self._handleOnOffState(localPrefsCopy.get("sirenTamper", None))))
		indigo.server.log(u". . system status:                          low battery: %s," % (self._handleOnOffState(localPrefsCopy.get("lowBattery", None))))
		indigo.server.log(u". . system status:                           AC failure: %s," % (self._handleOnOffState(localPrefsCopy.get("acFail", None))))
		indigo.server.log(u"")
		indigo.server.log(u". . system status:                  expander box tamper: %s," % (self._handleOnOffState(localPrefsCopy.get("expanderBoxTamper", None))))
		indigo.server.log(u". . system status:                  expander AC failure: %s," % (self._handleOnOffState(localPrefsCopy.get("expanderACFailure", None))))
		indigo.server.log(u". . system status:                 expander low battery: %s," % (self._handleOnOffState(localPrefsCopy.get("expanderLowBattery", None))))
		indigo.server.log(u". . system status:         expander loss of supervision: %s," % (self._handleOnOffState(localPrefsCopy.get("expanderLossOffSupervision", None))))
		indigo.server.log(u". . system status:            expander aux over current: %s," % (self._handleOnOffState(localPrefsCopy.get("expanderAuxOverCurrent", None))))
		indigo.server.log(u". . system status:        expander comm channel failure: %s," % (self._handleOnOffState(localPrefsCopy.get("auxiliaryCommChannelFailure", None))))
		indigo.server.log(u". . system status:                  expander bell fault: %s," % (self._handleOnOffState(localPrefsCopy.get("expanderBellFault", None))))
		indigo.server.log(u"")
		indigo.server.log(u". . system status:                   enable 6 digit pin: %s," % (self._handleOnOffState(localPrefsCopy.get("enable6DigitPin", None))))
		indigo.server.log(u". . system status:             programming token in use: %s," % (self._handleOnOffState(localPrefsCopy.get("programmingTokenInUse", None))))
		indigo.server.log(u". . system status:     pin required for locate download: %s," % (self._handleOnOffState(localPrefsCopy.get("pinRequiredForLocalDownload", None))))
		indigo.server.log(u". . system status:                global pulsing buzzer: %s," % (self._handleOnOffState(localPrefsCopy.get("globalPulsingBuzzer", None))))
		indigo.server.log(u". . system status:                      golbal siren on: %s," % (self._handleOnOffState(localPrefsCopy.get("globalSirenOn", None))))
		indigo.server.log(u". . system status:                  global steady siren: %s," % (self._handleOnOffState(localPrefsCopy.get("globalSteadySiren", None))))
		indigo.server.log(u". . system status:         bus device has line seizured: %s," % (self._handleOnOffState(localPrefsCopy.get("busDeviceHasLineSeized", None))))
		indigo.server.log(u". . system status:      bus device requested sniff mode: %s," % (self._handleOnOffState(localPrefsCopy.get("busDeviceRequestedSniffMode", None))))
		indigo.server.log(u"")
		indigo.server.log(u". . system status:                 dynamic battery test: %s," % (self._handleOnOffState(localPrefsCopy.get("dynamicBatteryTest", None))))
		indigo.server.log(u". . system status:                          AC power on: %s," % (self._handleOnOffState(localPrefsCopy.get("acPowerOn", None))))
		indigo.server.log(u". . system status:                   low battery memory: %s," % (self._handleOnOffState(localPrefsCopy.get("lowBatteryMemory", None))))
		indigo.server.log(u". . system status:                  ground fault memory: %s," % (self._handleOnOffState(localPrefsCopy.get("groundFaultMemory", None))))
		indigo.server.log(u". . system status   fire alarm verification being timed: %s," % (self._handleOnOffState(localPrefsCopy.get("fireAlarmVerificationBeingTimed", None))))
		indigo.server.log(u". . system status:                    smoke power reset: %s," % (self._handleOnOffState(localPrefsCopy.get("smokePowerReset", None))))
		indigo.server.log(u". . system status:              line power deteced 50Hz: %s," % (self._handleOnOffState(localPrefsCopy.get("linePowerDetected50Hz", None))))
		indigo.server.log(u". . system status:   timimg high voltage battery charge: %s," % (self._handleOnOffState(localPrefsCopy.get("timingHighVoltageBatteryCharge", None))))
		indigo.server.log(u"")
		indigo.server.log(u". . system status:   communication since last auto test: %s," % (self._handleOnOffState(localPrefsCopy.get("communicationSinceLastAutoTest", None))))
		indigo.server.log(u". . system status:           power up delay in progress: %s," % (self._handleOnOffState(localPrefsCopy.get("powerUpDelayInProgress", None))))
		indigo.server.log(u". . system status:                       walk test mode: %s," % (self._handleOnOffState(localPrefsCopy.get("walkTestMode", None))))
		indigo.server.log(u". . system status:                  loss of system time: %s," % (self._handleOnOffState(localPrefsCopy.get("lossOfSystemTime", None))))
		indigo.server.log(u". . system status:                     enroll requested: %s," % (self._handleOnOffState(localPrefsCopy.get("enrollRequested", None))))
		indigo.server.log(u". . system status:                    test fixture mode: %s," % (self._handleOnOffState(localPrefsCopy.get("testFixtureMode", None))))
		indigo.server.log(u". . system status:                control shutdown mode: %s," % (self._handleOnOffState(localPrefsCopy.get("controlShutdownMode", None))))
		indigo.server.log(u". . system status:               timimg a cancel window: %s," % (self._handleOnOffState(localPrefsCopy.get("timingACancelWindow", None))))
		indigo.server.log(u"")
		indigo.server.log(u". . system status:                 callback in progress: %s," % (self._handleOnOffState(localPrefsCopy.get("callBackInProgress", None))))
		indigo.server.log(u"")
		indigo.server.log(u". . system status:                   phone line faulted: %s," % (self._handleOnOffState(localPrefsCopy.get("phoneLineFaulted", None))))
		indigo.server.log(u". . system status:      volage present interrupt active: %s," % (self._handleOnOffState(localPrefsCopy.get("voltagePresentInterruptActive", None))))
		indigo.server.log(u". . system status:                 house phone off hook: %s," % (self._handleOnOffState(localPrefsCopy.get("housePhoneOffHook", None))))
		indigo.server.log(u". . system status:           phone line monitor enabled: %s," % (self._handleOnOffState(localPrefsCopy.get("phoneLineMonitorEnabled", None))))
		indigo.server.log(u". . system status:                             sniffing: %s," % (self._handleOnOffState(localPrefsCopy.get("sniffing", None))))
		indigo.server.log(u". . system status:               last read was off hook: %s," % (self._handleOnOffState(localPrefsCopy.get("lastReadWasOffHook", None))))
		indigo.server.log(u". . system status:                  listen in requested: %s," % (self._handleOnOffState(localPrefsCopy.get("listenInRequested", None))))
		indigo.server.log(u". . system status:                    listen in trigger: %s," % (self._handleOnOffState(localPrefsCopy.get("listenInTrigger", None))))
		indigo.server.log(u"")
		indigo.server.log(u". . system status:                    valid partition 1: %s," % (self._handleOnOffState(localPrefsCopy.get("validPartition1", None))))
		indigo.server.log(u". . system status:                    valid partition 2: %s," % (self._handleOnOffState(localPrefsCopy.get("validPartition2", None))))
		indigo.server.log(u". . system status:                    valid partition 3: %s," % (self._handleOnOffState(localPrefsCopy.get("validPartition3", None))))
		indigo.server.log(u". . system status:                    valid partition 4: %s," % (self._handleOnOffState(localPrefsCopy.get("validPartition4", None))))
		indigo.server.log(u". . system status:                    valid partition 5: %s," % (self._handleOnOffState(localPrefsCopy.get("validPartition5", None))))
		indigo.server.log(u". . system status:                    valid partition 6: %s," % (self._handleOnOffState(localPrefsCopy.get("validPartition6", None))))
		indigo.server.log(u". . system status:                    valid partition 7: %s," % (self._handleOnOffState(localPrefsCopy.get("validPartition7", None))))
		indigo.server.log(u". . system status:                    valid partition 8: %s," % (self._handleOnOffState(localPrefsCopy.get("validPartition8", None))))
		indigo.server.log(u". . system status:          communication stack pointer: %s," % (localPrefsCopy.get("communicatorStackPointer", None)))
		indigo.server.log(u"")
		
	def _handleOnOffState(self, value):
		if value == "1":
			state = "On"
		elif value == "0":
			state = "--"
		else:
			state = value
		return state
			
	########################################
	# Menu - Partition Status values to Log method
	########################################
	
	def partitionStatusToLog(self):				# copy the current alarm panel Partition Status  to Indigo Event Log
		partition = 1
		
		indigo.server.log(u"Primary Partition Status: . . . ")
		
		if partition in self.caddx.partitionList.keys():
			dev = self.caddx.partitionList[partition]
			
	#		indigo.server.log(u". . partition status:                              address: %s," % (dev.states["address"]))
	#		indigo.server.log(u". . partition status:                       keypad address: %s," % (dev.states["keypadAddress"]))
	#		indigo.server.log(u". . partition status:                       partition name: %s," % (dev.states["partitionName"]))
	
			indigo.server.log(u". . partition status:                     partition number: %s," % (dev.states["partitionNumber"]))
			indigo.server.log(u". . partition status:                     last user number: %s," % (dev.states["lastUserNumber"]))
			indigo.server.log(u". . partition status:                       partition user: %s," % (dev.states["partitionUser"]))
			indigo.server.log(u". . partition status:                      partition state: %s," % (dev.states["partitionState"]))
			indigo.server.log(u". . partition status:                       security state: %s," % (dev.states["securityState"]))
			indigo.server.log(u". . partition status:                      security  ready: %s," % (self._handleOnOffState(dev.states["securityReady"])))
			indigo.server.log(u"")
			indigo.server.log(u". . partition status:                    last state change: %s," % (dev.states["lastStateChange"]))
			indigo.server.log(u". . partition status:                    last zone trigger: %s," % (dev.states["lastZoneTrigger"]))
			indigo.server.log(u". . partition status:                 last function status: %s," % (dev.states["statusLastFunction"]))
			indigo.server.log(u"")
			indigo.server.log(u". . partition status:                      vaild partition: %s," % (self._handleOnOffState(dev.states["validPartition"])))
			indigo.server.log(u". . partition status:                           chime mode: %s," % (self._handleOnOffState(dev.states["chimeMode"])))
			indigo.server.log(u". . partition status:                      any entry delay: %s," % (self._handleOnOffState(dev.states["anyEntryDelay"])))
			indigo.server.log(u". . partition status:                       any exit delay: %s," % (self._handleOnOffState(dev.states["anyExitDelay"])))
			indigo.server.log(u". . partition status:             partition previous alarm: %s," % (self._handleOnOffState(dev.states["partitionPreviousAlarm"])))
			indigo.server.log(u"")
			indigo.server.log(u". . partition status:                 bypass code required: %s," % (self._handleOnOffState(dev.states["bypassCodeRequired"])))
			indigo.server.log(u". . partition status:                         fire trouble: %s," % (self._handleOnOffState(dev.states["fireTrouble"])))
			indigo.server.log(u". . partition status:                                 fire: %s," % (self._handleOnOffState(dev.states["fire"])))
			indigo.server.log(u". . partition status:                  fire pulsing buzzer: %s," % (self._handleOnOffState(dev.states["firePulsingBuzzer"])))
			indigo.server.log(u". . partition status:                     TLM fault memory: %s," % (self._handleOnOffState(dev.states["tLMFaultMemory"])))
			indigo.server.log(u". . partition status:                         armed system: %s," % (self._handleOnOffState(dev.states["armedSystem"])))
			indigo.server.log(u". . partition status:                              instant: %s," % (self._handleOnOffState(dev.states["instant"])))
			indigo.server.log(u"")
			indigo.server.log(u". . partition status:                       previous alarm: %s," % (self._handleOnOffState(dev.states["previousAlarm"])))
			indigo.server.log(u". . partition status:                             siren on: %s," % (self._handleOnOffState(dev.states["sirenOn"])))
			indigo.server.log(u". . partition status:                      steady siren on: %s," % (self._handleOnOffState(dev.states["steadySirenOn"])))
			indigo.server.log(u". . partition status:               alarm memory condition: %s," % (self._handleOnOffState(dev.states["alarmMemoryCondition"])))
			indigo.server.log(u". . partition status:                               tamper: %s," % (self._handleOnOffState(dev.states["tamper"])))
			indigo.server.log(u". . partition status:               cancel command entered: %s," % (self._handleOnOffState(dev.states["cancelCommandEntered"])))
			indigo.server.log(u". . partition status:                         code entered: %s," % (self._handleOnOffState(dev.states["codeEntered"])))
			indigo.server.log(u". . partition status:                       cancel pending: %s," % (self._handleOnOffState(dev.states["cancelPending"])))
			indigo.server.log(u"")
			indigo.server.log(u". . partition status:                  silent exit enabled: %s," % (self._handleOnOffState(dev.states["silentExitEnabled"])))
			indigo.server.log(u". . partition status:                entry guard stay mode: %s," % (self._handleOnOffState(dev.states["entryGuardStayMode"])))
			indigo.server.log(u". . partition status:                                entry: %s," % (self._handleOnOffState(dev.states["entry"])))
			indigo.server.log(u". . partition status:              dely expiration warning: %s," % (self._handleOnOffState(dev.states["delayExpirationWarning"])))
			indigo.server.log(u". . partition status:                               exit 1: %s," % (self._handleOnOffState(dev.states["exit1"])))
			indigo.server.log(u". . partition status:                               exit 2: %s," % (self._handleOnOffState(dev.states["exit2"])))
			indigo.server.log(u"")
			indigo.server.log(u". . partition status:                       LED extinguish: %s," % (self._handleOnOffState(dev.states["ledExtinguish"])))
			indigo.server.log(u". . partition status:                         cross timing: %s," % (self._handleOnOffState(dev.states["crossTiming"])))
			indigo.server.log(u". . partition status:           recent closing being timed: %s," % (self._handleOnOffState(dev.states["recentClosingBeingTimed"])))
			indigo.server.log(u". . partition status:                      error triggered: %s," % (self._handleOnOffState(dev.states["exitErrorTriggered"])))
			indigo.server.log(u". . partition status:                  auto home inhibited: %s," % (self._handleOnOffState(dev.states["autoHomeInhibited"])))
			indigo.server.log(u". . partition status:                   sensor low battery: %s," % (self._handleOnOffState(dev.states["sensorLowBattery"])))
			indigo.server.log(u". . partition status:           sensor loss of supervision: %s," % (self._handleOnOffState(dev.states["sensorLostSupervision"])))
			indigo.server.log(u"")
			indigo.server.log(u". . partition status:                          zone bypass: %s," % (self._handleOnOffState(dev.states["zoneBypass"])))
			indigo.server.log(u". . partition status:      force arm triggered by auto arm: %s," % (self._handleOnOffState(dev.states["forceArmTriggeredByAutoArm"])))
			indigo.server.log(u". . partition status:                         ready to arm: %s," % (self._handleOnOffState(dev.states["readyToArm"])))
			indigo.server.log(u". . partition status:                   ready to force arm: %s," % (self._handleOnOffState(dev.states["readyToForceArm"])))
			indigo.server.log(u". . partition status:                   valid pin accepted: %s," % (self._handleOnOffState(dev.states["validPinAccepted"])))
			indigo.server.log(u". . partition status:                    chime on sounding: %s," % (self._handleOnOffState(dev.states["chimeOnSounding"])))
			indigo.server.log(u". . partition status:               error beep triple beep: %s," % (self._handleOnOffState(dev.states["errorBeepTripleBeep"])))
			indigo.server.log(u". . partition status:              tone on activation tone: %s," % (self._handleOnOffState(dev.states["toneOnActivationTone"])))
			indigo.server.log(u"")
			indigo.server.log(u". . partition status:                              entry 1: %s," % (self._handleOnOffState(dev.states["entry1"])))
			indigo.server.log(u". . partition status:                          open period: %s," % (self._handleOnOffState(dev.states["openPeriod"])))
			indigo.server.log(u". . partition status:      alarm send using phone number 1: %s," % (self._handleOnOffState(dev.states["alarmSendUsingPhoneNumber1"])))
			indigo.server.log(u". . partition status:      alarm send using phone number 2: %s," % (self._handleOnOffState(dev.states["alarmSendUsingPhoneNumber2"])))
			indigo.server.log(u". . partition status:      alarm send using phone number 3: %s," % (self._handleOnOffState(dev.states["alarmSendUsingPhoneNumber3"])))
			indigo.server.log(u". . partition status:            cancel report is in stack: %s," % (self._handleOnOffState(dev.states["cancelReportIsInTheStack"])))
			indigo.server.log(u". . partition status:                     key switch armed: %s," % (self._handleOnOffState(dev.states["keySwitchArmed"])))
			indigo.server.log(u". . partition status:   delay trip in progress comman zone: %s," % (self._handleOnOffState(dev.states["delayTripInProgressCommonZone"])))
			indigo.server.log(u"")
			
				
	########################################
	# Menu - Zones Summary values to Log method
	########################################
		
		
	def zonesSummaryToLog(self):				# copy the zone summary Information  to Indigo Event Log			
		# read plugin config perference limit parameter settings
		zonesSystem = int(self.pluginPrefs[u'zonesSystem'])	
		indigo.server.log(u"Zones Summary Status: . . .")
		
		# read alarm zones from 1 to zonesSystem value	
		for key in range(0,zonesSystem):	
			key = (key + 1)
			zone = key
			if key in self.caddx.zoneList.keys():
				dev = self.caddx.zoneList[zone]
				localPropsCopy = dev.pluginProps
				zoneName = localPropsCopy["zoneName"]
				zoneNumber = localPropsCopy["address"]
				zoneDisplayName = localPropsCopy["zoneDisplayName"]
				zoneGroupType = localPropsCopy["zoneGroupType"]
				zoneGroupDescription = localPropsCopy["zoneGroupDescription"]
				zoneState = dev.states["zoneState"]
				indigo.server.log(u". . %s   display name: {%s},   state: %s,   type: %s,   description: %s  " % (zoneName, zoneDisplayName, zoneState, zoneGroupType, zoneGroupDescription))
		indigo.server.log(u"")
	
	########################################
	# Menu - Log Event History entries to Log method
	########################################

	def logEventHistoryToLog(self):				# copy the current alarm panel log event history to Indigo Event Log
		
		indigo.server.log(u"")
		indigo.server.log(u"Log Event History: (last 25 entries) . . .")
		logEventHistoryList = ["zlogEventHistory01", "zlogEventHistory02", "zlogEventHistory03", "zlogEventHistory04", "zlogEventHistory05", "zlogEventHistory06", "zlogEventHistory07",
									"zlogEventHistory08", "zlogEventHistory09", "zlogEventHistory10", "zlogEventHistory11", "zlogEventHistory12", "zlogEventHistory13", "zlogEventHistory14",
									"zlogEventHistory15", "zlogEventHistory16", "zlogEventHistory17", "zlogEventHistory18", "zlogEventHistory19", "zlogEventHistory20", "zlogEventHistory21",
									"zlogEventHistory22", "zlogEventHistory23", "zlogEventHistory24", "zlogEventHistory25" ]							 		 							 
		item = 0
		for i in logEventHistoryList:
			variable = logEventHistoryList[item]
			var = self.pluginPrefs[variable]
			indigo.server.log(u". . %s" % var)
			item += 1
		indigo.server.log(u"")	
						
	########################################
	# Menu - Set Date / Time method
	########################################
	
	def setClockCalender(self):					# command action: --> Set Clock/ Calender <--	
		self.caddx._actionSetClockCalenderCommand(action = "")	
		
	########################################
	# Menu - Log Events to Indigo Log method
	########################################
	
	def logEventRequest(self):					# command action: --> Log Event Request <--
		self.caddx.actionLogEventRequest(action = "")																			
							
################################################################################				
		#	plugin.py end						
################################################################################	
	

			
		


		
	