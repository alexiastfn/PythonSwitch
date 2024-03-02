#!/usr/bin/python3
import sys
import struct
import wrapper
import threading
import time
from wrapper import recv_from_any_link, send_to_link, get_switch_mac, get_interface_name

def parse_ethernet_header(data):
    # Unpack the header fields from the byte array
    #dest_mac, src_mac, ethertype = struct.unpack('!6s6sH', data[:14])
    dest_mac = data[0:6]
    src_mac = data[6:12]
    
    # Extract ethertype. Under 802.1Q, this may be the bytes from the VLAN TAG
    ether_type = (data[12] << 8) + data[13]

    vlan_id = -1
    # Check for VLAN tag (0x8100 in network byte order is b'\x81\x00')
    if ether_type == 0x8200:
        vlan_tci = int.from_bytes(data[14:16], byteorder='big')
        vlan_id = vlan_tci & 0x0FFF  # extract the 12-bit VLAN ID
        ether_type = (data[16] << 8) + data[17]

    return dest_mac, src_mac, ether_type, vlan_id

def create_vlan_tag(vlan_id):
    # 0x8100 for the Ethertype for 802.1Q
    # vlan_id & 0x0FFF ensures that only the last 12 bits are used
    return struct.pack('!H', 0x8200) + struct.pack('!H', vlan_id & 0x0FFF)

#def is_type_trunk(interface):


def send_bdpu_every_sec():
    while True:
        # TODO Send BDPU every second if necessary
        time.sleep(1)

def main():
    # init returns the max interface number. Our interfaces
    # are 0, 1, 2, ..., init_ret value + 1
    switch_id = sys.argv[1]
    MAC_Table = {}
    ports_Table = {}

    my_file = open("configs/switch" + str(switch_id) + ".cfg", "r")
    read_content = my_file.read()
    content = read_content.strip().split("\n")

    for line in content[1:]:
        aux = line
        my_str = aux.split(" ")
        port = my_str[0]
        port_type = my_str[1]
        ports_Table[port] = port_type


    num_interfaces = wrapper.init(sys.argv[2:])
    interfaces = range(0, num_interfaces)

    print("# Starting switch with id {}".format(switch_id), flush=True)
    print("[INFO] Switch MAC", ':'.join(f'{b:02x}' for b in get_switch_mac()))

    # Create and start a new thread that deals with sending BDPU
    t = threading.Thread(target=send_bdpu_every_sec)
    t.start()

    # Printing interface names
    for i in interfaces:
        print(get_interface_name(i))

    while True:
        # Note that data is of type bytes([...]).
        # b1 = bytes([72, 101, 108, 108, 111])  # "Hello"
        # b2 = bytes([32, 87, 111, 114, 108, 100])  # " World"
        # b3 = b1[0:2] + b[3:4].
        interface, data, length = recv_from_any_link()

        dest_mac, src_mac, ethertype, vlan_id = parse_ethernet_header(data)

        # Print the MAC src and MAC dst in human readable format
        dest_mac = ':'.join(f'{b:02x}' for b in dest_mac)
        src_mac = ':'.join(f'{b:02x}' for b in src_mac)

        # Note. Adding a VLAN tag can be as easy as
        # tagged_frame = data[0:12] + create_vlan_tag(10) + data[12:]

        print(f'Destination MAC: {dest_mac}')
        print(f'Source MAC: {src_mac}')
        print(f'EtherType: {ethertype}')

        print("Received frame of size {} on interface {}".format(length, interface), flush=True)

        # TODO: Implement forwarding with learning

        MAC_Table[src_mac] = interface
        MAC_broadcast = "ff:ff:ff:ff:ff:ff"
        sending_to_interfaces = []

        if dest_mac != MAC_broadcast:
            if dest_mac in MAC_Table:
                #send_to_link(MAC_Table[dest_mac], data, length)
                sending_to_interfaces.append(MAC_Table[dest_mac])
            else:
                for port in interfaces:
                    if port != interface:
                        #send_to_link(port, data, length)
                        sending_to_interfaces.append(port)
        else:
            for port in interfaces:  # broadcast:
                if port != interface:
                    #send_to_link(port, data, length)
                    sending_to_interfaces.append(port)


        # TODO: Implement VLAN support


        for my_interface in sending_to_interfaces:

            my_interface_str = get_interface_name(my_interface)
            type_interface = ports_Table[my_interface_str]
            src_interface = MAC_Table[src_mac]
            src_interface_str = get_interface_name(src_interface)
            src_type_interface = ports_Table[src_interface_str]

            if src_type_interface == "T":
                dest_type_interface = ports_Table[my_interface_str]
                if dest_type_interface == "T":
                    send_to_link(my_interface, data, len(data))
                elif str(vlan_id) == ports_Table[my_interface_str]:
                    first_part = data[0:12]
                    second_part = data[16:]
                    new_data = first_part + second_part
                    send_to_link(my_interface, new_data, len(new_data))
            else:
                if type_interface == "T":
                    first_part = data[0:12]
                    header = create_vlan_tag(int(ports_Table[src_interface_str]))
                    second_part = data[12:]
                    new_data = first_part + header + second_part
                    send_to_link(my_interface, new_data, len(new_data))
                elif ports_Table[src_interface_str] == ports_Table[my_interface_str]:
                    send_to_link(my_interface, data, len(data))




if __name__ == "__main__":
    main()
