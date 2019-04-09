from serial import Serial
from threading import Thread
from queue import Queue
from scan_hardware import get_zigbee_ports

START_BYTE = 0x7E
RECEIVE_BYTE = 0x90
AT_COMMAND_BYTE = 0x08
AT_RESPONSE_BYTE = 0x88
UNKNOWN_BYTE = 0xFF
TRANSMISSION_BYTE = 0x10
TRANSMISSION_STATUS = 0x8B
REMOTE_AT_REQ_BYTE = 0x17
REMOTE_AT_RESP_BYTE = 0x97

ESCAPE_BYTE = 0x7D
XON_BYTE = 0x11
XOFF_BYTE = 0x13
NEED_ESCAPE = (ESCAPE_BYTE, XON_BYTE, XOFF_BYTE, START_BYTE)

PacketTypes = {

    RECEIVE_BYTE: lambda b: {
        "type": "receive",
        "full_addr": ':'.join('%02x' % b for b in b[3:11]),
        "short_addr": ':'.join('%02x' % d for d in b[12:14]),
        "payload": b[15:-1].decode(),
        "lqi": b[-1]
    },  # Message
    TRANSMISSION_STATUS: lambda b: {
        "type": "response",
        "frame_id": b[4],
        "destination": ':'.join('%02x' % d for d in b[5:7]),
        "status_code": b[9],
        "lqi": b[-1]
    },  # AT Response
    AT_RESPONSE_BYTE: lambda b: {
        "type": "AT",
        "frame_id": b[4],
        "command": b[5:7].decode(),
        "payload": b[7:-1],
        "lqi": b[-1]
    },  # AT Response
    REMOTE_AT_RESP_BYTE: lambda b: {
        "type": "REMOTE_AT",
        "frame_id": b[4],
        "full_addr": ':'.join('%02x' % b for b in b[5:13]),
        "short_addr": ':'.join('%02x' % d for d in b[13:15]),
        "command": b[15:17].decode(),
        "status_code": b[17],
        "payload": b[18:-1],
        "lqi": b[-1]
    },
    UNKNOWN_BYTE: lambda b: {
        "type": "unknown"
    }
}


def compute_checksum(msg):
    total = sum(msg)
    truncation = total & 0xFF
    checksum = 0xFF - truncation
    return checksum.to_bytes(1, 'big')


def build_message(msg):
    length = len(msg)
    checksum = compute_checksum(msg)
    full_msg = START_BYTE.to_bytes(1, 'big') + length.to_bytes(2, 'big') + msg + checksum
    return full_msg


def send_at_command(device, cmd):
    PACKET_ID = b'\x01'
    msg = AT_COMMAND_BYTE.to_bytes(1, 'big') + PACKET_ID + cmd.encode()
    encoded_msg = build_message(msg)
    device.write(encoded_msg)


def send_transmission(device, address_16bit, message):
    FRAME_ID = 1
    address_64bit = b'\xff\xff\xff\xff\xff\xff\xff\xff'
    NUM_HOPS = b'\x00'
    OPTIONS = b'\x00'
    msg = TRANSMISSION_BYTE.to_bytes(1, 'big') + FRAME_ID.to_bytes(1, 'big') + address_64bit + address_16bit + \
          NUM_HOPS + OPTIONS + message.encode()
    encoded_msg = build_message(msg)
    device.write(encoded_msg)


def send_remote_at_command(device, address_16bit, message):
    FRAME_ID = 1
    address_64bit = b'\xff\xff\xff\xff\xff\xff\xff\xff'
    OPTIONS = b'\x00'
    msg = REMOTE_AT_REQ_BYTE.to_bytes(1, 'big') + FRAME_ID.to_bytes(1, 'big') + address_64bit + address_16bit + \
          OPTIONS + message.encode()
    encoded_msg = build_message(msg)
    device.write(encoded_msg)


def parse_message(barray):
    packet_type = 0xFF
    if len(barray) >= 3:
        packet_type = barray[3]

    if packet_type in PacketTypes:
        return PacketTypes[packet_type](barray)
    else:
        print("Warning: unknown packet type: " + str(packet_type))
        return PacketTypes[UNKNOWN_BYTE](barray)


def set_name_and_pan(device, name, pan):
    send_at_command(device, "ID " + pan)
    send_at_command(device, "NI " + name)


def polling_thread(dev, received, to_send):
    in_progress = b''
    waiting_message = {}
    bytes_left = 999

    while True:
        d = dev.read()
        if d == ESCAPE_BYTE.to_bytes(1, 'big'):
            d = dev.read()
        in_progress = in_progress + d

        bytes_left = bytes_left - 1
        if bytes_left == 0:
            bytes_left = 999
            parsed_message = parse_message(in_progress)
            print(parsed_message)
            if parsed_message["type"] == "receive":
                received.put(parsed_message)
            elif parsed_message["type"] == "AT" and parsed_message["command"] != "DB":
                pass
                # print("Received command message: " + parsed_message["command"] + ", " + parsed_message["payload"])
            elif parsed_message["type"] == "AT" and parsed_message["command"] == "DB":
                waiting_neighbor["rssi"] = int.from_bytes(parsed_message["payload"], byteorder='big')
                print("Found neighbor: " + str(waiting_neighbor))
            elif parsed_message["type"] == "REMOTE_AT":
                waiting_neighbor = parsed_message
            in_progress = b''
        else:
            if len(in_progress) == 3:
                bytes_left = int.from_bytes(in_progress[1:3], 'big') + 1
            elif len(in_progress) == 4 and in_progress[3] == REMOTE_AT_RESP_BYTE:
                send_at_command(dev, 'DB')


def choose_device():
    zigbee_devices = get_zigbee_ports()
    if len(zigbee_devices) == 0:
        raise Exception("No Zigbee sensors connected.")

    print("Available devices: ")
    for i, d in enumerate(zigbee_devices):
        print(str(i) + ")  " + d)
    print("")
    dnum = -1
    while dnum < 0 or dnum > len(zigbee_devices) - 1:
        resp = input("Select a device: ")
        dnum = int(resp) if resp.isnumeric() else -1

    return zigbee_devices[dnum]


dev_path_to_name = {
    "/dev/ttyUSB0": "Lefty",
    "/dev/ttyUSB1": "Topper",
    "/dev/ttyUSB2": "Slidey"
}

if __name__ == "__main__":
    dev_path = choose_device()
    port = Serial(dev_path, 9600)


    received = Queue()
    to_send = Queue()
    t = Thread(target=polling_thread, args=(port, received, to_send,))

    t.start()

    set_name_and_pan(port, dev_path_to_name[dev_path], "5555")
    send_at_command(port, "ID")


    OTHER_ZIGBEE = b'\xFF\xFF'
    go = True
    while go:
        text = input("Enter a message:")

        go = text != ".quit"
        if text == ".quit":
            go = False
        elif text == ".qual":
            print("Requesting NI from all devices.")
            send_remote_at_command(port, OTHER_ZIGBEE, 'NI')
        else:
            send_transmission(port, OTHER_ZIGBEE, text)

    port.close()

#TODO: broadcast remote AT command "NI", collect NI+16_addr+RSSI for neighbors
# --- TODO: this also means detecting a remote AT response, send this to a list of "neighbors"