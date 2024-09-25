import socket
import struct
import hashlib
import random
import threading
import time
import pyamf
from pyamf.remoting import encode

class SimpleRTMPClient:
    def __init__(self, server, port, app, stream_key):
        self.server = server
        self.port = port
        self.app = app
        self.stream_key = stream_key
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(5)
        self.socket_buffer = b''

    def generate_c1(self):
        timestamp = struct.pack('>I', int(time.time()))
        zero = struct.pack('>I', 0)  # 4 bytes set to zero
        if hasattr(random, 'randbytes'):
            random_bytes = random.randbytes(1528)
        else:
            random_bytes = bytes([random.randint(0, 255) for _ in range(1528)])
        return timestamp + zero + random_bytes

    def handshake(self):
        # Send C0 + C1
        C0 = b'\x03'  # RTMP version 3
        C1 = self.generate_c1()
        self.socket.sendall(C0 + C1)

        # Receive S0 + S1 + S2
        S0 = self.socket.recv(1)
        if S0 != b'\x03':
            raise Exception("Invalid RTMP version from server")
        S1 = self.socket.recv(1536)
        S2 = self.socket.recv(1536)

        # Send C2 (echoing S1)
        C2 = S1
        self.socket.sendall(C2)

    def send_rtmp_packet(self, data, packet_type=0x14, timestamp=0):
        # Basic RTMP packet structure
        fmt = 0  # Type 0 for basic header
        csid = 3  # Common chunk stream ID for commands
        basic_header = (fmt << 6) | csid
        header = struct.pack('>B', basic_header)
        size = len(data)
        timestamp_bytes = struct.pack('>I', timestamp)[1:]  # 3 bytes
        data_size = struct.pack('>I', size)[1:]  # 3 bytes
        stream_id = struct.pack('<I', 0)[:3]  # 3 bytes, little endian
        packet_header = struct.pack('>B', packet_type) + data_size + timestamp_bytes + struct.pack('B', 0) + stream_id
        self.socket.sendall(header + packet_header + data)

    def send_connect(self):
        connect_command = [
            'connect',
            1,
            {
                'app': self.app,
                'type': 'nonprivate',
                'flashVer': 'FMLE/3.0 (compatible; FMSc/1.0)',
                'tcUrl': f'rtmp://{self.server}:{self.port}/{self.app}',
                'fpad': False,
                'capabilities': 15,
                'audioCodecs': 3575,
                'videoCodecs': 252,
                'videoFunction': 1,
                'pageUrl': '',
                'objectEncoding': 0
            }
        ]
        amf_data = encode(connect_command, encoding=pyamf.AMF0)
        self.send_rtmp_packet(amf_data)

    def send_publish(self):
        publish_command = [
            'publish',
            1,
            self.stream_key,
            'live'
        ]
        amf_data = encode(publish_command, encoding=pyamf.AMF0)
        self.send_rtmp_packet(amf_data)

    def connect(self):
        self.socket.connect((self.server, self.port))
        self.handshake()
        self.send_connect()
        # Here you should receive and handle server responses to the connect command
        # This requires implementing an AMF decoder and handling RTMP messages
        # For simplicity, this is omitted
        time.sleep(1)  # Wait for server to process
        self.send_publish()

    def publish(self):
        # Placeholder for additional publish logic if needed
        pass

    def send_flv_data(self, flv_data):
        # Placeholder for sending FLV data over RTMP
        # Proper implementation requires chunking and handling RTMP packets
        self.socket.sendall(flv_data)

    def close(self):
        self.socket.close()
