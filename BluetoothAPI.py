import time
import objc
import sys
import ctypes
from CoreBluetooth import (
    CBCentralManager,
    CBPeripheral,
    CBCharacteristicPropertyBroadcast,
    CBCharacteristicPropertyRead,
    CBCharacteristicPropertyWriteWithoutResponse,
    CBCharacteristicPropertyWrite,
    CBCharacteristicPropertyNotify,
    CBCharacteristicPropertyIndicate,
    CBCharacteristicPropertyAuthenticatedSignedWrites,
    CBCharacteristicPropertyExtendedProperties,
    CBCharacteristicPropertyNotifyEncryptionRequired,
    CBCharacteristicPropertyIndicateEncryptionRequired,
)
from Foundation import NSObject, NSRunLoop, NSDate, NSUUID, NSTimer

from pynput.keyboard import Key, Controller  # Import pynput for keyboard simulation

class BluetoothScanner(NSObject):
    def init(self):
        self = objc.super(BluetoothScanner, self).init()
        if self is None:
            return None
        # Initialize CBCentralManager with self as delegate
        self.central_manager = CBCentralManager.alloc().initWithDelegate_queue_options_(self, None, None)
        self.discovered_peripherals = {}
        self.scanning = False
        self.target_name = "Controller_E18D"  # Replace with your device's BLE name
        self.target_peripheral = None
        self.connected = False
        self.control_characteristic = None  # Control characteristic UUID
        self.keyboard = Controller()        # Initialize keyboard controller
        self.current_keys = set()           # Track currently pressed keys
        self.timer = None                   # Timer for periodic reads (if needed)
        return self

    def start_scan(self):
        if not self.scanning:
            print("Scanning for BLE devices...")
            # Start scanning for peripherals with no specific services
            self.central_manager.scanForPeripheralsWithServices_options_(None, None)
            self.scanning = True

    def stop_scan(self):
        if self.scanning:
            self.central_manager.stopScan()
            print("Scanning stopped.")
            self.scanning = False
            # List all discovered peripherals
            for uuid_str, peripheral in self.discovered_peripherals.items():
                name = peripheral.name() or "Unknown"
                print(f"- {name} (UUID: {uuid_str})")

    def centralManagerDidUpdateState_(self, central):
        state = central.state()
        if state == 5:  # Powered On
            print("Bluetooth is powered on.")
            self.start_scan()
        elif state == 4:
            print("Bluetooth is powered off.")
        else:
            print(f"Central manager state: {state}")

    def centralManager_didDiscoverPeripheral_advertisementData_RSSI_(self, central, peripheral, advertisementData, RSSI):
        name = peripheral.name() or "Unknown"
        uuid_str = peripheral.identifier().UUIDString()
        if uuid_str not in self.discovered_peripherals:
            self.discovered_peripherals[uuid_str] = peripheral
            print(f"Discovered Peripheral: {name} (UUID: {uuid_str})")
            if self.target_name and name == self.target_name:
                print(f"Found target peripheral with name: {name}")
                self.target_peripheral = peripheral
                self.stop_scan()
                self.connect_to_peripheral()

    def connect_to_peripheral(self):
        if self.target_peripheral:
            print(f"Attempting to connect to peripheral: {self.target_peripheral.name() or 'Unknown'} (UUID: {self.target_peripheral.identifier().UUIDString()})")
            self.central_manager.connectPeripheral_options_(self.target_peripheral, None)
        else:
            print("Target peripheral not found.")

    def centralManager_didConnectPeripheral_(self, central, peripheral):
        print(f"Connected to peripheral: {peripheral.name() or 'Unknown'} (UUID: {peripheral.identifier().UUIDString()})")
        self.connected = True
        peripheral.setDelegate_(self)
        peripheral.discoverServices_(None)

    def centralManager_didFailToConnectPeripheral_error_(self, central, peripheral, error):
        print(f"Failed to connect to peripheral: {peripheral.name() or 'Unknown'}, error: {error}")
        self.connected = False

    def centralManager_didDisconnectPeripheral_error_(self, central, peripheral, error):
        print(f"Disconnected from peripheral: {peripheral.name() or 'Unknown'}, error: {error}")
        self.connected = False
        # Release any pressed keys upon disconnection
        self.release_all_keys()

    def peripheral_didDiscoverServices_(self, peripheral, error):
        if error:
            print(f"Error discovering services: {error}")
            return
        for service in peripheral.services():
            service_uuid = service.UUID().UUIDString().lower()
            print(f"Discovered service: {service_uuid}")
            # Replace '180f' with your actual service UUID if different
            if service_uuid == '180f':  # Example: Battery Service
                print("Found Battery Service")
                peripheral.discoverCharacteristics_forService_(None, service)
            # If you have a custom service for control data, discover its characteristics here
            # Example:
            # elif service_uuid == 'YOUR_CUSTOM_SERVICE_UUID':
            #     peripheral.discoverCharacteristics_forService_(None, service)

    def peripheral_didDiscoverCharacteristicsForService_error_(self, peripheral, service, error):
        if error:
            print(f"Error discovering characteristics for service {service.UUID()}: {error}")
            return
        for characteristic in service.characteristics():
            char_uuid = characteristic.UUID().UUIDString().lower()
            print(f"Discovered characteristic: {char_uuid} for service: {service.UUID()}")
            # Assuming '2a19' is repurposed for control data
            if char_uuid == '2a19':
                print("Found Control Characteristic")
                self.PrintCharacteristicProperties(characteristic)
                self.control_characteristic = characteristic
                # Subscribe to notifications if supported
                if characteristic.properties() & CBCharacteristicPropertyNotify:
                    peripheral.setNotifyValue_forCharacteristic_(True, characteristic)
                    print("Subscribed to control characteristic notifications.")
                else:
                    # If notifications are not supported, use periodic reads
                    self.schedule_control_read(interval=0.1)  # Adjust interval as needed

    def schedule_control_read(self, interval=0.1):
        if self.timer is None:
            self.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                interval, self, 'readControlCharacteristic:', None, True)
            print(f"Started periodic control characteristic reads every {interval} seconds.")

    def readControlCharacteristic_(self, timer):
        if self.control_characteristic and self.connected:
            self.target_peripheral.readValueForCharacteristic_(self.control_characteristic)
        else:
            print("Cannot read control characteristic: Not connected or characteristic not found.")

    @objc.python_method
    def PrintCharacteristicProperties(self, characteristic):
        properties = characteristic.properties()
        property_list = []
        if properties & CBCharacteristicPropertyBroadcast:
            property_list.append('Broadcast')
        if properties & CBCharacteristicPropertyRead:
            property_list.append('Read')
        if properties & CBCharacteristicPropertyWriteWithoutResponse:
            property_list.append('Write Without Response')
        if properties & CBCharacteristicPropertyWrite:
            property_list.append('Write')
        if properties & CBCharacteristicPropertyNotify:
            property_list.append('Notify')
        if properties & CBCharacteristicPropertyIndicate:
            property_list.append('Indicate')
        if properties & CBCharacteristicPropertyAuthenticatedSignedWrites:
            property_list.append('Authenticated Signed Writes')
        if properties & CBCharacteristicPropertyExtendedProperties:
            property_list.append('Extended Properties')
        if properties & CBCharacteristicPropertyNotifyEncryptionRequired:
            property_list.append('Notify Encryption Required')
        if properties & CBCharacteristicPropertyIndicateEncryptionRequired:
            property_list.append('Indicate Encryption Required')
        print(f"Characteristic {characteristic.UUID()} properties: {', '.join(property_list)}")

    def peripheral_didUpdateValueForCharacteristic_error_(self, peripheral, characteristic, error):
        if error:
            print(f"Error reading characteristic {characteristic.UUID()}: {error}")
            return
        char_uuid = characteristic.UUID().UUIDString().lower()
        if char_uuid == '2a19':
            control_data = characteristic.value()
            if control_data is None:
                print("Received None data from characteristic.")
                return
            control_bytes = self.nsdata_to_bytes(control_data)
            print(f"Received control data: {control_bytes}")
            print(f"Length of control data: {len(control_bytes)}")
            self.handle_control_input(control_bytes)
        else:
            pass

    @objc.python_method
    def nsdata_to_bytes(self, nsdata):
        # Convert NSData to bytes
        length = nsdata.length()
        if length == 0:
            return b''
        buf = (ctypes.c_ubyte * length)()
        nsdata.getBytes_length_(buf, length)
        return bytes(buf)

    @objc.python_method
    def handle_control_input(self, data):
        send_state = self.parse_control_data(data)
        if send_state is not None:
            self.update_key_press(send_state)
        else:
            self.release_all_keys()

    @objc.python_method
    def parse_control_data(self, data):
        if not data:
            print("parse_control_data: Received empty data.")
            return None
        send_state = data[0]
        print(f"Received send_state value: {send_state:#04x}")

        # Map each bit to button names
        send_state_mapping = {
            0x01: 'button_a',
            0x02: 'button_b',
            0x04: 'button_square',
            0x08: 'button_triangle',
            0x10: 'button_up',
            0x20: 'button_down',
            0x40: 'button_left',
            0x80: 'button_right',
        }

        buttons_pressed = set()
        for bitmask, button in send_state_mapping.items():
            if send_state & bitmask:
                buttons_pressed.add(button)

        if buttons_pressed:
            print(f"Mapped send_state {send_state:#04x} to buttons: {', '.join(buttons_pressed)}")
            return buttons_pressed
        elif send_state == 0x00:
            # No buttons pressed
            return set()
        else:
            print(f"Unknown send_state: {send_state:#04x}")
            return set()

    @objc.python_method
    def update_key_press(self, buttons_pressed):
        key_mapping = {
            'button_a': Key.space,          # A Button -> Space
            'button_b': Key.backspace,      # B Button -> Backspace
            'button_square': Key.shift,      # Square -> Shift
            'button_triangle': Key.enter,    # Triangle -> Enter
            'button_up': Key.up,             # Up -> Arrow Up
            'button_down': Key.down,         # Down -> Arrow Down
            'button_left': Key.left,         # Left -> Arrow Left
            'button_right': Key.right,       # Right -> Arrow Right
        }

        # Determine buttons to press and release
        buttons_to_press = buttons_pressed - self.current_keys
        buttons_to_release = self.current_keys - buttons_pressed

        # Press new keys
        for button in buttons_to_press:
            key = key_mapping.get(button)
            if key:
                self.keyboard.press(key)
                print(f"Pressed {key}")
                self.current_keys.add(button)

        # Release keys that are no longer pressed
        for button in buttons_to_release:
            key = key_mapping.get(button)
            if key:
                self.keyboard.release(key)
                print(f"Released {key}")
                self.current_keys.remove(button)

    @objc.python_method
    def release_all_keys(self):
        key_mapping = {
            'button_a': Key.space,
            'button_b': Key.backspace,
            'button_square': Key.shift,
            'button_triangle': Key.enter,
            'button_up': Key.up,
            'button_down': Key.down,
            'button_left': Key.left,
            'button_right': Key.right,
        }
        for button in list(self.current_keys):
            key = key_mapping.get(button)
            if key:
                self.keyboard.release(key)
                print(f"Released {key}")
            self.current_keys.remove(button)

# Create a Bluetooth scanner instance
scanner = BluetoothScanner.alloc().init()
print(f"Looking for peripheral with name: {scanner.target_name}")

run_loop = NSRunLoop.currentRunLoop()

try:
    while True:
        run_loop.runMode_beforeDate_("NSDefaultRunLoopMode", NSDate.dateWithTimeIntervalSinceNow_(0.1))
except KeyboardInterrupt:
    print("Script terminated by user.")
    if scanner.timer:
        scanner.timer.invalidate()
    if scanner.connected:
        # Release any pressed keys before disconnecting
        scanner.release_all_keys()
        scanner.central_manager.cancelPeripheralConnection_(scanner.target_peripheral)
    sys.exit(0)
