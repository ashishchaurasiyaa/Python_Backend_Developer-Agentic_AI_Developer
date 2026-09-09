"""
Encapsulation / Decapsulation -- verified practical: build and parse real
Ethernet + IP + TCP headers byte-by-byte with struct (no raw sockets needed).
"""

import socket
import struct
import zlib


def mac_to_bytes(mac):
    return bytes.fromhex(mac.replace(":", ""))


def build_ethernet_header(dst_mac, src_mac, ethertype=0x0800):
    return struct.pack("!6s6sH", mac_to_bytes(dst_mac), mac_to_bytes(src_mac), ethertype)


def ip_checksum(header_bytes):
    if len(header_bytes) % 2:
        header_bytes += b"\x00"
    total = sum(struct.unpack(f"!{len(header_bytes) // 2}H", header_bytes))
    total = (total >> 16) + (total & 0xFFFF)
    total += total >> 16
    return (~total) & 0xFFFF


def build_ip_header(src_ip, dst_ip, payload_len, ttl=64, proto=6):
    version_ihl = (4 << 4) | 5
    total_length = 20 + payload_len
    without_checksum = struct.pack(
        "!BBHHHBBH4s4s",
        version_ihl, 0, total_length, 0, 0, ttl, proto, 0,
        socket.inet_aton(src_ip), socket.inet_aton(dst_ip),
    )
    checksum = ip_checksum(without_checksum)
    return struct.pack(
        "!BBHHHBBH4s4s",
        version_ihl, 0, total_length, 0, 0, ttl, proto, checksum,
        socket.inet_aton(src_ip), socket.inet_aton(dst_ip),
    )


def build_tcp_header(src_port, dst_port, seq=0, ack=0, flags=0x02, window=65535):
    data_offset = 5 << 4
    return struct.pack("!HHLLBBHHH", src_port, dst_port, seq, ack, data_offset, flags, window, 0, 0)


def parse_ethernet_header(data):
    dst, src, ethertype = struct.unpack("!6s6sH", data[:14])
    return {
        "dst_mac": ":".join(f"{b:02x}" for b in dst),
        "src_mac": ":".join(f"{b:02x}" for b in src),
        "ethertype": hex(ethertype),
    }, data[14:]


def parse_ip_header(data):
    version_ihl, tos, total_len, ident, flags_frag, ttl, proto, checksum, src, dst = struct.unpack(
        "!BBHHHBBH4s4s", data[:20]
    )
    return {
        "version": version_ihl >> 4,
        "ihl_words": version_ihl & 0x0F,
        "total_length": total_len,
        "ttl": ttl,
        "protocol": proto,
        "checksum": hex(checksum),
        "src_ip": socket.inet_ntoa(src),
        "dst_ip": socket.inet_ntoa(dst),
    }, data[20:]


def parse_tcp_header(data):
    src_port, dst_port, seq, ack, offset_reserved, flags, window, checksum, urgent = struct.unpack(
        "!HHLLBBHHH", data[:20]
    )
    return {
        "src_port": src_port,
        "dst_port": dst_port,
        "seq": seq,
        "ack": ack,
        "flags": bin(flags),
        "window": window,
    }, data[20:]


if __name__ == "__main__":
    payload = b"GET /users HTTP/1.1\r\nHost: api.example.com\r\n\r\n"

    print("=== Step 1: Application data (Layer 7) ===")
    print(payload)
    print(f"Length: {len(payload)} bytes\n")

    tcp_header = build_tcp_header(52134, 443, seq=1000, ack=0)
    tcp_segment = tcp_header + payload
    print("=== Step 2: + TCP header (Layer 4) -> TCP segment ===")
    print(f"TCP header: {len(tcp_header)} bytes | Segment total: {len(tcp_segment)} bytes\n")

    ip_header = build_ip_header("10.0.0.5", "93.184.216.34", len(tcp_segment))
    ip_packet = ip_header + tcp_segment
    print("=== Step 3: + IP header (Layer 3) -> IP packet ===")
    print(f"IP header: {len(ip_header)} bytes | Packet total: {len(ip_packet)} bytes\n")

    eth_header = build_ethernet_header("aa:bb:cc:dd:ee:ff", "11:22:33:44:55:66")
    fcs = struct.pack("!I", zlib.crc32(ip_packet) & 0xFFFFFFFF)
    frame = eth_header + ip_packet + fcs
    print("=== Step 4: + Ethernet header + trailer (Layer 2) -> Frame ===")
    print(f"Eth header: {len(eth_header)} bytes | Trailer (FCS): {len(fcs)} bytes | Frame total: {len(frame)} bytes\n")

    print(f"Raw frame hex ({len(frame)} bytes):")
    print(frame.hex())
    print()

    print("=== Now DECAPSULATE the frame, layer by layer ===\n")
    eth_fields, rest = parse_ethernet_header(frame)
    print("Layer 2 (Ethernet) parsed:", eth_fields)

    ip_fields, rest = parse_ip_header(rest)
    print("Layer 3 (IP) parsed:", ip_fields)

    tcp_fields, rest = parse_tcp_header(rest)
    print("Layer 4 (TCP) parsed:", tcp_fields)

    app_data = rest[:-4]
    print("\nLayer 7 (Application) recovered data:")
    print(app_data)

    print(f"\nOverhead check: {len(frame) - len(payload)} bytes of headers/trailer wrapped around {len(payload)} bytes of real data.")
