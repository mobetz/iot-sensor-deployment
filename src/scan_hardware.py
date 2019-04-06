
import usb.core
import usb.backend.libusb1

busses = usb.busses()
for bus in busses:
    devices = bus.devices
    for dev in devices:
        if dev is not None:
            try:
                xdev = usb.core.find(idVendor=dev.idVendor, idProduct=dev.idProduct)
                if xdev._manufacturer is None:
                    xdev._manufacturer = usb.util.get_string(xdev, xdev.iManufacturer)
                if xdev._product is None:
                    xdev._product = usb.util.get_string(xdev, xdev.iProduct)
                    print(str(xdev._manufacturer) + "," + str(xdev._product) + ": ")
            except:
                pass