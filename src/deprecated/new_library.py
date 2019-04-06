from serial import Serial
from xbee import ZigBee

if __name__ == "__main__":
    port = Serial("COM5", 9600, timeout=3)
    print("Port set up")
    my_device = ZigBee(port)
    print("Device created")
    while True:
        print("In loop")
        dat = my_device.wait_read_frame()
        dat = my_device.at(command=b'DB')
        print("After wait")
        print(dat)


