#!/usr/bin/python3
# Advertises, accepts a connection, creates the microbit temperature service and characteristic
import bluetooth_constants
import bluetooth_gatt
import bluetooth_exceptions
import dbus
import dbus.exceptions
import dbus.service
import dbus.mainloop.glib
import sys
import random
import json
import pickle
import os
import time
from gi.repository import GObject
from gi.repository import GLib
import subprocess

#sys.path.insert(0, '.')
DEVICE_CONFIG_PATH = "/usr/local/artlite-opaq-app/config/device_config.json"
DEVICE_MAPPING_PATH = "/usr/local/artlite-opaq-app/config/device_mapping.json"
DEVICE_SECRETS_PATH = "/usr/local/artlite-opaq-app/config/secrets.json"

command = """
cd /usr/local/bin/ 
./artlite_bt.sh off
./artlite_bt.sh on
"""
process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
stdout, stderr = process.communicate()
print("Output:")
print(stdout)
if stderr:
    print("Errors:")
    print(stderr)

# Read the JSON file
with open('/tmp/meta_files/UNIQUE_ID/id-displayboard.json', 'r') as file:
    json_data = json.load(file)
    
UNIQUE_ID = json_data["val"]

bus = None
adapter_path = None
adv_mgr_interface = None
connected = 0

SERVICE_UUID = UNIQUE_ID + '-2873-4ee1-bc21-f7dd0c72de04'
CHARAC_UUID_0 = '3d736f3c-9108-42d1-ab03-c6523eb7fcb5'
CHARAC_UUID_1 = '376eb4c9-a16d-4a50-aaf2-8052884a3f99'
CHARAC_UUID_2 = '5f5f4b18-fe65-4916-b6c7-b1574ee591cb'
CHARAC_UUID_3 = '4482c5c3-9932-4aa3-b74a-67e1720abd91'
CHARAC_UUID_4 = 'be02f706-70b5-4520-9ab4-424ae3c97532'
CHARAC_UUID_5 = '3204a6f1-2232-4dba-a948-7ad4688c168a'
CHARAC_UUID_6 = '8c9b1355-b316-4efe-a105-2f753bab7649'
CHARAC_UUID_7 = 'b8bfcc85-a6be-4857-abfb-8cd65d9f5b9d'

# much of this code was copied or inspired by test\example-advertisement in the BlueZ source
class Advertisement(dbus.service.Object):
    PATH_BASE = '/org/bluez/ldsg/advertisement'

    def __init__(self, bus, index, advertising_type):
        self.path = self.PATH_BASE + str(index)
        self.bus = bus
        self.ad_type = advertising_type
        self.service_uuids = [SERVICE_UUID]
        self.manufacturer_data = None
        self.solicit_uuids = None
        self.service_data = None
        self.local_name = UNIQUE_ID
        self.include_tx_power = False
        self.data = None
        self.discoverable = True
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        properties = dict()
        properties['Type'] = self.ad_type
        if self.service_uuids is not None:
            properties['ServiceUUIDs'] = dbus.Array(self.service_uuids,
                                                    signature='s')
        if self.solicit_uuids is not None:
            properties['SolicitUUIDs'] = dbus.Array(self.solicit_uuids,
                                                    signature='s')
        if self.manufacturer_data is not None:
            properties['ManufacturerData'] = dbus.Dictionary(
                self.manufacturer_data, signature='qv')
        if self.service_data is not None:
            properties['ServiceData'] = dbus.Dictionary(self.service_data,
                                                        signature='sv')
        if self.local_name is not None:
            properties['LocalName'] = dbus.String(self.local_name)
        if self.discoverable is not None and self.discoverable == True:
            properties['Discoverable'] = dbus.Boolean(self.discoverable)
        if self.include_tx_power:
            properties['Includes'] = dbus.Array(["tx-power"], signature='s')

        if self.data is not None:
            properties['Data'] = dbus.Dictionary(
                self.data, signature='yv')
        print(properties)
        return {bluetooth_constants.ADVERTISING_MANAGER_INTERFACE: properties}

    def get_path(self):
        return dbus.ObjectPath(self.path)

    @dbus.service.method(bluetooth_constants.DBUS_PROPERTIES,
                         in_signature='s',
                         out_signature='a{sv}')
    def GetAll(self, interface):
        if interface != bluetooth_constants.ADVERTISEMENT_INTERFACE:
            raise bluetooth_exceptions.InvalidArgsException()
        return self.get_properties()[bluetooth_constants.ADVERTISING_MANAGER_INTERFACE]

    @dbus.service.method(bluetooth_constants.ADVERTISING_MANAGER_INTERFACE,
                         in_signature='',
                         out_signature='')
    def Release(self):
        print('%s: Released' % self.path)
        

class Application(dbus.service.Object):
    """
    org.bluez.GattApplication1 interface implementation
    """
    def __init__(self, bus):
        self.path = '/'
        self.services = []
        dbus.service.Object.__init__(self, bus, self.path)
        print("Adding SensorService to the Application")
        self.add_service(SensorService(bus, '/org/bluez/ldsg', 0))

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_service(self, service):
        self.services.append(service)

    @dbus.service.method(bluetooth_constants.DBUS_OM_IFACE, out_signature='a{oa{sa{sv}}}')
    def GetManagedObjects(self):
        response = {}
        print('GetManagedObjects')

        for service in self.services:
            print("GetManagedObjects: service="+service.get_path())
            response[service.get_path()] = service.get_properties()
            chrcs = service.get_characteristics()
            for chrc in chrcs:
                response[chrc.get_path()] = chrc.get_properties()
                descs = chrc.get_descriptors()
                for desc in descs:
                    response[desc.get_path()] = desc.get_properties()

        return response
        
        
class SensorService(bluetooth_gatt.Service):
    def __init__(self, bus, path_base, index):
        print("Initialising SensorService object")
        bluetooth_gatt.Service.__init__(self, bus, path_base, index, SERVICE_UUID, True)
        print("Adding ChangeConfigurationCharacteristic to the service")
        self.add_characteristic(SensorCharacteristic(bus, 0, self, CHARAC_UUID_0, functions = ["read","write"], charac_name = "ChangeConfigurationCharacteristic", service_name = None))

        print("Adding ChangeDeviceMappingCharacteristic to the service")
        self.add_characteristic(SensorCharacteristic(bus, 1, self, CHARAC_UUID_1, functions = ["read","write"], charac_name = "ChangeDeviceMappingCharacteristic", service_name = None))
        
        print("Adding RestartOpaqAppCharacteristic to the service")
        self.add_characteristic(SensorCharacteristic(bus, 2, self, CHARAC_UUID_2, functions = ["read","write"], charac_name = "RestartOpaqAppCharacteristic", service_name = "artlite-opaq-app"))
        
        print("Adding RestartBleOpsCharacteristic to the service")
        self.add_characteristic(SensorCharacteristic(bus, 3, self, CHARAC_UUID_3, functions = ["read","write"], charac_name = "RestartBleOpsCharacteristic", service_name = "artlite-opaq-ble-configurator-app"))
        
        print("Adding RestartCairAppCharacteristic to the service")
        self.add_characteristic(SensorCharacteristic(bus, 4, self, CHARAC_UUID_4, functions = ["read","write"], charac_name = "RestartCairAppCharacteristic", service_name = "cair-app"))
        
        print("Adding RestartDeviceCharacteristic to the service")
        self.add_characteristic(SensorCharacteristic(bus, 5, self, CHARAC_UUID_5, functions = ["read","write"], charac_name = "RestartDeviceCharacteristic", service_name = None))
        
        print("Adding GetIPAddressCharacteristic to the service")
        self.add_characteristic(SensorCharacteristic(bus, 6, self, CHARAC_UUID_6, functions = ["read"], charac_name = "GetIPAddressCharacteristic", service_name = None))
        
        print("Adding ChangeSecretsCharacteristic to the service")
        self.add_characteristic(SensorCharacteristic(bus, 7, self, CHARAC_UUID_7, functions = ["write"], charac_name = "ChangeSecretsCharacteristic", service_name = None))
        
class SensorCharacteristic(bluetooth_gatt.Characteristic):
    def __init__(self, bus, index, service, CHARAC_UUID, functions, charac_name, service_name):
        bluetooth_gatt.Characteristic.__init__(
                self, bus, index,
                CHARAC_UUID,
                functions,
                service)
        self.sensor_value = 50
        self.buffer = ''
        self.charac_name = charac_name
        self.service_name = service_name
        
    def ReadValue(self, options):
        print('ReadValue in '+ self.charac_name + ' called')
        
        if self.charac_name == "ChangeConfigurationCharacteristic":
            with open(DEVICE_CONFIG_PATH, 'r') as file:
                device_config = json.load(file)

            print('Returning '+ str(device_config))
            value_bytes = str(device_config).encode('utf-8')

            value = []
            for byteval in value_bytes:
                value.append(dbus.Byte(byteval))
         
            return value
            
        elif self.charac_name == "ChangeDeviceMappingCharacteristic":
            with open(DEVICE_MAPPING_PATH, 'r') as file:
                device_config = json.load(file)

            print('Returning '+ str(device_config))
            value_bytes = str(device_config).encode('utf-8')

            value = []
            for byteval in value_bytes:
                value.append(dbus.Byte(byteval))
         
            return value
            
        elif  self.charac_name == 'RestartDeviceCharacteristic':
            return "  " + self.charac_name 
            
        elif self.charac_name == 'RestartOpaqAppCharacteristic' or self.charac_name == 'RestartBleOpsCharacteristic' or self.charac_name == 'RestartCairAppCharacteristic':
            try:
                service_status = get_service_status(self.service_name).encode('utf-8')
                print("Status of the service " + self.service_name + " is: " + service_status)
                return "  " + self.service_name + " service - " + service_status
            except Exception as e:
                print(e)
                
        elif self.charac_name == 'GetIPAddressCharacteristic':
            interface = 'wlan0'  # Replace with your interface name
            ip_address = get_ip_address(interface)
            
            if ip_address:
                print("IP Address of " + interface + ": " + ip_address)
                return ip_address.encode('utf-8')
            else:
                print("Could not find IP address for interface " + interface)
                return "Not Determined!"
       
    
            
    def WriteValue(self, value, options):
        print('WriteValue in '+ self.charac_name + ' called')
        if self.charac_name == "ChangeConfigurationCharacteristic":
            #print(value)
            byte_list = [int(byte) for byte in value]
            
            decoded_string = ''.join([chr(byte) for byte in byte_list]) # Convert the list of bytes to a string
            self.buffer += decoded_string
            # Check if the buffer contains a complete JSON message
            # Assuming the JSON messages are enclosed in curly braces
            while '}}' in self.buffer:
                end_index = self.buffer.index('}}') + 2 # Find the end of the first complete JSON message
                complete_message = self.buffer[:end_index] # Extract the complete message
                try:
                    json_msg = json.loads(complete_message)  # Attempt to parse the JSON message
                    print("Received complete message:", complete_message)  # Process the complete message
                    my_write_callback(complete_message, DEVICE_CONFIG_PATH)
                    # Remove the processed or problematic message from the buffer
                    self.buffer = self.buffer[end_index:]
                except ValueError as e:
                    # Handle malformed JSON
                    print("Warning: Incomplete or malformed JSON message received. Error: ",e)
                    # Or attempt to skip to the next possible message
                    self.buffer = self.buffer[end_index:]
            
        elif self.charac_name == "ChangeDeviceMappingCharacteristic":
            #print(value)
            byte_list = [int(byte) for byte in value]
            
            decoded_string = ''.join([chr(byte) for byte in byte_list]) # Convert the list of bytes to a string
            self.buffer += decoded_string
            # Check if the buffer contains a complete JSON message
            # Assuming the JSON messages are enclosed in curly braces
            while '}' in self.buffer:
                end_index = self.buffer.index('}') + 1  # Find the end of the first complete JSON message
                complete_message = self.buffer[:end_index]  # Extract the complete message
                
                try:
                    json_msg = json.loads(complete_message)  # Attempt to parse the JSON message
                    print("Received complete message:", complete_message)  # Process the complete message
                    my_write_callback(complete_message, DEVICE_MAPPING_PATH)
                    # Remove the processed or problematic message from the buffer
                    self.buffer = self.buffer[end_index:]
                except ValueError as e:
                    # Handle malformed JSON
                    print("Warning: Incomplete or malformed JSON message received. Error: ",e)
                    # Or attempt to skip to the next possible message
                    self.buffer = self.buffer[end_index:]
            
        elif  self.charac_name == 'RestartDeviceCharacteristic':
            byte_list = [int(byte) for byte in value]
            result = int(chr(byte_list[0]))
            print(result)
            if result == 1:
                reboot_device()
            else:
                print('command Fail')
            
        elif self.charac_name == 'RestartOpaqAppCharacteristic' or self.charac_name == 'RestartBleOpsCharacteristic' or self.charac_name == 'RestartCairAppCharacteristic':
            byte_list = [int(byte) for byte in value]
            result = int(chr(byte_list[0]))
            print(result)
            if result == 1:
                restart_service(self.service_name)
                print('restart Successfull')
            else:
                print('command Fail')
        
        elif self.charac_name == 'ChangeSecretsCharacteristic':
            byte_list = [int(byte) for byte in value]
            
            decoded_string = ''.join([chr(byte) for byte in byte_list]) # Convert the list of bytes to a string
            self.buffer += decoded_string
            # Check if the buffer contains a complete JSON message
            # Assuming the JSON messages are enclosed in curly braces
            while '}' in self.buffer:
                end_index = self.buffer.index('}') + 1  # Find the end of the first complete JSON message
                complete_message = self.buffer[:end_index]  # Extract the complete message
                
                try:
                    json_msg = json.loads(complete_message)  # Attempt to parse the JSON message
                    
                    # Check if the required keys are present
                    if all(key in json_msg for key in ["DEVICE_ID", "SECRET_KEY"]):
                        print("Received complete message:", complete_message)  # Process the complete message
                        my_write_callback(complete_message, DEVICE_SECRETS_PATH)
                    else:
                        print("Warning: JSON message is missing required keys.")
                    
                    # Remove the processed or problematic message from the buffer
                    self.buffer = self.buffer[end_index:]
                
                except ValueError as e:
                    # Handle malformed JSON
                    print("Warning: Incomplete or malformed JSON message received. Error: ",e)
                    # Or attempt to skip to the next possible message
                    self.buffer = self.buffer[end_index:]
        
                
def get_ip_address(interface_name):
    try:
        # Execute the shell command and capture the output
        ip_address = subprocess.check_output(
            "ifconfig " + interface_name + " | grep 'inet addr:' | awk '{{print $2}}' | cut -d':' -f2", 
            shell=True
        ).decode().strip()
        
        return ip_address
    except subprocess.CalledProcessError:
        return None
    
def reboot_device():
    try:
        print("Rebooting device..")
        subprocess.Popen(['reboot'])
    except Exception as e:
        print("Failed to reboot the device: ",e)
        
def restart_service(service_name):
    try:
        # Restart the service
        subprocess.Popen(['systemctl', 'restart', service_name])
        print("Service " + service_name + " has been restarted.")
    except subprocess.CalledProcessError as e:
        print("Failed to restart service " + service_name + ": ", e)

def get_service_status(service_name):
    try:
        result = subprocess.Popen(['systemctl', 'is-active', service_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE) # Check the status of the service
        output, error = result.communicate() # Read the output and error (if any)
        status = output.strip()  # Remove any trailing newline or spaces
        print("Service " + service_name + " is currently "+ status)
        return status
    except Exception as e:
        print("Failed to get status for service " + service_name)
        print(e)
        return "unknown"

def my_write_callback(msg,path):
    print("Updating " + path + " file..")
    try:
        with open(path, 'w') as file:
            json.dump(json.loads(msg), file, indent=4)
        print(path + " file has been updated.")
    except Exception as e:    
        print(e)
    
def register_ad_cb():
    print('Advertisement registered OK')

def register_ad_error_cb(error):
    print('Error: Failed to register advertisement: ' + str(error))
    mainloop.quit()

def register_app_cb():
    print('GATT application registered')

def register_app_error_cb(error):
    print('Failed to register application: ' + str(error))
    mainloop.quit()

def set_connected_status(status):
    if (status == 1):
        print("connected")
        connected = 1
        stop_advertising()
    else:
        print("disconnected")
        connected = 0
        start_advertising()

def properties_changed(interface, changed, invalidated, path):
    if (interface == bluetooth_constants.DEVICE_INTERFACE):
        if ("Connected" in changed):
            set_connected_status(changed["Connected"])

def interfaces_added(path, interfaces):
    if bluetooth_constants.DEVICE_INTERFACE in interfaces:
        properties = interfaces[bluetooth_constants.DEVICE_INTERFACE]
        if ("Connected" in properties):
            set_connected_status(properties["Connected"])

def stop_advertising():
    global adv
    global adv_mgr_interface
    print("Unregistering advertisement",adv.get_path())
    adv_mgr_interface.UnregisterAdvertisement(adv.get_path())

def start_advertising():
    global adv
    global adv_mgr_interface
    # we're only registering one advertisement object so index (arg2) is hard coded as 0
    print("Registering advertisement",adv.get_path())
    adv_mgr_interface.RegisterAdvertisement(adv.get_path(), {},
                                        reply_handler=register_ad_cb,
                                        error_handler=register_ad_error_cb)
          
# Define a function to stop the main loop
def stop_mainloop():
    print("Stopping the main loop.")
    mainloop.quit()  

def global_exception_handler(exc_type, exc_value, exc_traceback):
    print("Unhandled exception:", exc_value)
    mainloop.quit()
    
sys.excepthook = global_exception_handler

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus()
# we're assuming the adapter supports advertising
adapter_path = bluetooth_constants.BLUEZ_NAMESPACE + bluetooth_constants.ADAPTER_NAME
adv_mgr_interface = dbus.Interface(bus.get_object(bluetooth_constants.BLUEZ_SERVICE_NAME,adapter_path), bluetooth_constants.ADVERTISING_MANAGER_INTERFACE)
bus.add_signal_receiver(properties_changed,
        dbus_interface = bluetooth_constants.DBUS_PROPERTIES,
        signal_name = "PropertiesChanged",
        path_keyword = "path")
bus.add_signal_receiver(interfaces_added,
        dbus_interface = bluetooth_constants.DBUS_OM_IFACE,
        signal_name = "InterfacesAdded")

# we're only registering one advertisement object so index (arg2) is hard coded as 0
adv_mgr_interface = dbus.Interface(bus.get_object(bluetooth_constants.BLUEZ_SERVICE_NAME,adapter_path), bluetooth_constants.ADVERTISING_MANAGER_INTERFACE)
adv = Advertisement(bus, 0, 'peripheral')
start_advertising()

mainloop = GLib.MainLoop()
# Schedule the stop function to be called after 5 seconds
#GLib.timeout_add_seconds(5, stop_mainloop)
app = Application(bus)
print('Registering GATT application...')

service_manager = dbus.Interface(
        bus.get_object(bluetooth_constants.BLUEZ_SERVICE_NAME, adapter_path),
        bluetooth_constants.GATT_MANAGER_INTERFACE)

service_manager.RegisterApplication(app.get_path(), {},
                                reply_handler=register_app_cb,
                                error_handler=register_app_error_cb)
                           
try:
    print("Running the main loop.")
    mainloop.run()
    print("Main loop has exited.")
     
except:
    print("MAINLOOP ERROR!")
    
if __name__ == "__main__":
    print("Hello Main")