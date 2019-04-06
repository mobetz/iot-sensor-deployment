import time

from digi.xbee.devices import ZigBeeDevice
from digi.xbee.packets.base import DictKeys


def set_node_and_pan(device, node_name, pan_id):
    device.set_node_id(node_name)
    device.set_pan_id(bytearray.fromhex(pan_id))
    device.apply_changes()
    device.write_changes()
    return device


def generate_callback(device):
    def data_received_callback(message):
        signal_strength = device.execute_command("DB")  # causes a timeout error
        print(signal_strength)

    return data_received_callback


def generate_packet_callback(device):
    def packet_received_callback(packet):
        packet_dict = packet.to_dict()
        api_data = packet_dict[DictKeys.FRAME_SPEC_DATA][DictKeys.API_DATA]
        data = api_data[DictKeys.RF_DATA]

        rssi = "NONE"
        if DictKeys.RSSI in api_data:
            rssi = api_data[DictKeys.RSSI]
        else:
            pass
            # rssi = device.get_parameter("DB")  # this causes a timeout error

        addr = "NONE"
        if DictKeys.X64BIT_ADDR in api_data:
            addr = api_data[DictKeys.X64BIT_ADDR]
        elif DictKeys.X16BIT_ADDR in api_data:
            addr = api_data[DictKeys.X16BIT_ADDR]

        print("from: {}, RSSI: {}, Data: {}".format(addr, rssi, bytes(data).decode()))
    return packet_received_callback


#
# def do_discovery(device):
#     network = device.get_network()
#     network.start_discovery_process()
#
#     while network.is_discovery_running():
#         time.sleep(0.5)
#
#     print("Discovery complete!")
#     devices = network.get_devices()
#     for d in devices:
#         name = d.get_parameter("NI").decode("utf-8")
#         print("Name is: " + name)
#         if name == "jeremy":
#             d.set_parameter("NI", "NEWNAME".encode())
#             d.execute_command("WR")
#             print("renamed!")


if __name__ == "__main__":
    my_device = ZigBeeDevice("COM5", 9600)
    my_device.open()
    set_node_and_pan(my_device, "test_device", "1234")
    my_device.add_packet_received_callback(generate_packet_callback(my_device))

    print("At startup, last received packet strength: -" + str(ord(my_device.get_parameter("DB"))) + "dB")
