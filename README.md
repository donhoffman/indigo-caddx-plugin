# Caddx NetworX Security Panel  (Indigo Plugin)

**NOTE:**

As I am no longer using Indigo and have no test environment, this repo is no longer maintained 
and will be archived shortly.  Feel free to fork if you have a need to make changes.


## Overview

It is a comprehensive protocol implementation of Caddx NX-584 RS-232 Gateway Interface Protocol (April 2000) spec.

This should work with the Caddx NX-584 RS-232 Gateway Interface for the Caddx NX-4, NX-6 and NX-8 but I do not have the hardware to test this. It has only been tested with NX-8e.

This release is based off of the orginal plugin done by @IanS on the Indigo Forums, with bug fixes and enhancements provided by @kw123.  Many thanks for the orginal contribution.

## Installation

1. Download "Caddx Security System.indigoPlugin.zip" from the release link to the machine running your Indigo instance..
2. Double-click on it.   This should trigger Indigo to install and run the plugin.

You will need to make sure your panel is set up as follows:

1. Enable serial port.
2. Bit rates up to 38400 are known to work.
3. Home Automation Protocol should be Binary Mode.
4. Additional config to be provided later.  Above is minimal set.

Suggest you do this using the DL900 software.  This can be downloaded from the Interlogix site [here](https://www.interlogix.com/library?type=&segment=&brand=&category=&status=&query=dl900)

## Usage

If you previously were using version 1.3.0 as orginally done by @IanS, you will probably need to recreate your zone devices as the enhancements done by @kw123 changed the type of those devices from "sensor" to "custom."  If you are using the version 7.4.3 as provided by @kw123, no changes should be needed.

For new installations, go to the config menu item for this plugin and fill in the "General", "Panel Object" and "Device Communicaitons" sections, then invoke "Create Caddx Alarm System Devices" menu item, then the "Synchronize Database" Menu item.
