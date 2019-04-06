import serial.tools.list_ports


def get_zigbee_ports():
    return [port.device for port in list(serial.tools.list_ports.comports()) \
                 if port.vid == 1027 and port.pid == 24577]

