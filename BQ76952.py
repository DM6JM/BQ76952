#!/usr/bin/python
# -*- coding:utf-8 -*-

import smbus
import time

#The CRC polynomial is x8 + x2 + x + 1, and the initial value is 0.

'''
When a read transaction is sent by the host, the device may clock stretch while it fetches the data and prepares
to send it. However, when subcommands are sent that require the device to fetch data and load it into the 0x40
– 0x5F transfer buffer, the device does not clock stretch during this time. The timing required for the device to
fetch the data depends on the specific subcommand and any other processing underway within the device, so
it will vary during operation. The approximate times required for the device to fetch the data for subcommands
are described in Table 9-2. When sending a subcommand, it is recommended to wait long enough for the device
to fetch the data, then read 0x3E/0x3F again. If the initial subcommand is echoed back from this read, then the
fetched data is available and can be read from the transfer buffer.
The simplest approach is to use a 2 ms wait time after writing to 0x3E/0x3F before reading the result from the
transfer buffer
'''

class BQ76952Command:
  def __init__(self, type, command, convertLambda, size):
    self.type = type
    self.command = command
    self.convertLambda = convertLambda
    self.size = size

class BQ76952DataFlash:
  def __init__(self, address, convertLambda, size):
    self.address = address
    self.convertLambda = convertLambda
    self.size = size

class BQ76952Cell:
  def __init__(self, number):
    self.number = number
    self.voltage = None


class BQ76952:
  
  mV2V = lambda v: float(v) / 1000
  stackV2V = lambda v: float(v) / 100 # TODO: Fix once clear how to calculate
  packV2V = lambda v: float(v) / 100 # TODO: Fix once clear how to calculate
  ldV2V = lambda v: float(v) / 100 # TODO: Fix once clear how to calculate

  byteList2Int = lambda v: int(v[0] + (v[1] * 256))

  maxCellsSupported = 16
  
  # Command-Type (Read, Write, RW, Command, Lambda for result or None, Transfersize: Size or None if command only or None for Subcommands)
  commandSet = {
    "subCommand": BQ76952Command('W', 0x3E, None, 2), #0x3E and 0x3F is the address, but auto-increment should fix it
    "subCommandResponse": BQ76952Command('R', 0x40, None, None),
    "dataArea": BQ76952Command('W', 0x3E, None, 2), #0x3E and 0x3F is the address, but auto-increment should fix it
    "dataAreaResponse": BQ76952Command('R', 0x40, None, None),
    "Cell1Voltage": BQ76952Command('R', 0x14, mV2V, 2),
    "Cell2Voltage": BQ76952Command('R', 0x16, mV2V, 2),
    "Cell3Voltage": BQ76952Command('R', 0x18, mV2V, 2),
    "Cell4Voltage": BQ76952Command('R', 0x1A, mV2V, 2),
    "Cell5Voltage": BQ76952Command('R', 0x1C, mV2V, 2),
    "Cell6Voltage": BQ76952Command('R', 0x1E, mV2V, 2),
    "Cell7Voltage": BQ76952Command('R', 0x20, mV2V, 2),
    "Cell8Voltage": BQ76952Command('R', 0x22, mV2V, 2),
    "Cell9Voltage": BQ76952Command('R', 0x24, mV2V, 2),
    "Cell10Voltage": BQ76952Command('R', 0x26, mV2V, 2),
    "Cell11Voltage": BQ76952Command('R', 0x28, mV2V, 2),
    "Cell12Voltage": BQ76952Command('R', 0x2A, mV2V, 2),
    "Cell13Voltage": BQ76952Command('R', 0x2C, mV2V, 2),
    "Cell14Voltage": BQ76952Command('R', 0x2E, mV2V, 2),
    "Cell15Voltage": BQ76952Command('R', 0x30, mV2V, 2),
    "Cell16Voltage": BQ76952Command('R', 0x32, mV2V, 2),
    "StackVoltage": BQ76952Command('R', 0x34, stackV2V, 2),
    "PackVoltage": BQ76952Command('R', 0x34, packV2V, 2),
    "LDVoltage": BQ76952Command('R', 0x34, ldV2V, 2)
    }
  subCommandSet = {

  }
  dataFlashSet = {
    "cellInfo": BQ76952DataFlash(0x9304, byteList2Int, 2),

  }
  
  def __init__(self, bus, address = 0x08):
    self._addr = address
    self._bus = bus
    self._i2c = None
    self.cells = []
    self.current = 0
    self.temperature = 0
  
  def __del__(self): 
    if self._i2c != None:
      self._i2c.close()
      del self._i2c
      self._i2c = None    

  def start(self):
    if self._i2c == None:
      try:
        self._i2c = smbus.SMBus(self._bus)
      except:
        print("Error initializing I2C/SMBus")
      else:
        # Get information about Number of Cells and config
        cellInfo = self.readDataFlash("cellInfo")
        if cellInfo == 0:
          cellInfo = ~cellInfo # Invert, since 0x0000 is treated like 0xFFFF
        for cell in range(self.maxCellsSupported):
          if cellInfo & 1:
            print("Adding cell number "+ str(cell + 1))
            self.cells.append(BQ76952Cell(cell + 1))
          cellInfo >>= 1
    else:
      raise Exception("Already initialized")
    
  def updateVoltages(self):
    if self._i2c == None:
      raise Exception("Interface not started") 
    try:
      for cell in self.cells:
        cell.voltage = self.executeCommand("Cell"+str(cell.number)+"Voltage")
    except:
      raise Exception("Error updating voltages")
    
  def readDataFlash(self, command):
    if self._i2c == None:
      raise Exception("Interface not started") 
    try:
      commandInfo_Prepare = self.dataFlashSet[command]
      self.executeCommand("dataArea", commandInfo_Prepare.address)
      time.sleep(0.005) # Let BQ prepare data (5ms)
      commandInfo_Read = self.commandSet["dataAreaResponse"]
      result = self._i2c.read_i2c_block_data(self._addr, commandInfo_Read.command, commandInfo_Prepare.size)
      print("DEBUG: readDataFlash with command: " + command + " at " + format(commandInfo_Prepare.address, '#04x') + " = " + str(result))

      if commandInfo_Prepare.convertLambda:
        result = commandInfo_Prepare.convertLambda(result)
      return result
    except:
      raise Exception("Error reading DataFlash")

  def executeCommand(self, command, data=None):
    if self._i2c == None:
      raise Exception("Interface not started") 
    try:
      commandinfo = self.commandSet[command]
      if commandinfo.type == "R":
        if commandinfo.size == 2:
          result = self._i2c.read_word_data(self._addr, commandinfo.command)
        elif commandinfo.size == 1:
          result = self._i2c.read_byte_data(self._addr, commandinfo.command)
        elif commandinfo.size > 0:
          result = self._i2c.write_quick(self._addr, commandinfo.command)
        else:
          raise Exception("Unsupported command size") 
        if commandinfo.convertLambda:
          result = commandinfo.convertLambda(result)
        return result        
      elif commandinfo.type == "W":
        if commandinfo.size == 2:
          self._i2c.write_word_data(self._addr, commandinfo.command, data)
        elif commandinfo.size == 1:
          self._i2c.write_byte_data(self._addr, commandinfo.command, data)
        elif commandinfo.size == 0:
          self._i2c.write_quick(self._addr, commandinfo.command)
        else:
          raise Exception("Unsupported command size") 
      else:
        raise Exception("Unsupported command type") 
    except:
      raise Exception("Error executing command")

if __name__ == "__main__":
  print("Creating instance of BQ76952 on default SMBUS(1)")
  bq = BQ76952(1)
  bq.start()
  print("Number of Cells active: " + str(len(bq.cells)))
  bq.updateVoltages()
  for cell in bq.cells:
    print("Cell" + str(cell.number) + ": " + str(cell.voltage) + "mV")
  del bq