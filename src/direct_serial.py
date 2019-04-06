from serial import Serial
from threading import Thread
from queue import Queue


START_BYTE = 0x7E
RECEIVE_BYTE = 0x90
AT_RESPONSE_BYTE = 0x88
UNKNOWN_BYTE = 0xFF
TRANSMISSION_BYTE = 0x10
TRANSMISSION_STATUS = 0x8B


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
        "command": b[4:6],
        "payload": b[6:-1],
        "lqi": b[-1]
    },  # AT Response
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
    msg = b'\x08\x01' + cmd.encode()
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


def parse_message(barray):
    packet_type = 0xFF
    if len(barray) >= 3:
        packet_type = barray[2]

    if packet_type in PacketTypes:
        return PacketTypes[packet_type](barray)
    else:
        print("Warning: unknown packet type: " + str(packet_type))
        return PacketTypes[UNKNOWN_BYTE](barray)


def polling_thread(dev, incoming, outgoing):
    in_progress = b''
    waiting_message = {}
    while True:
        d = dev.read()
        if d == START_BYTE.to_bytes(1, 'big'):
            parsed_message = parse_message(in_progress)
            if parsed_message["type"] == "receive":
                waiting_message = parsed_message
            elif parsed_message["type"] == "AT":
                waiting_message["rssi"] = int.from_bytes(parsed_message["payload"], byteorder='big')
                incoming.put(waiting_message)
                print("Received message: " + str(waiting_message))
            in_progress = b''
        else:
            in_progress = in_progress + d
            if len(in_progress) == 3 and in_progress[2] == RECEIVE_BYTE:
                send_at_command(dev, 'DB')


if __name__ == "__main__":
    port = Serial("COM5", 9600, timeout=0.5)
    inbound = Queue()
    outbound = Queue()
    t = Thread(target=polling_thread, args=(port, inbound, outbound,))
    t.start()

    OTHER_ZIGBEE = b'\xc4\x7f'
    go = True
    while go:
        text = input("Enter a message:")
        go = text != ".quit"
        if go:
            send_transmission(port, OTHER_ZIGBEE, text)

    port.close()
