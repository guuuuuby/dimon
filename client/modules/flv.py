import struct
import time

def create_flv_header():
    header = b'FLV'
    header += struct.pack('B', 1)
    header += struct.pack('B', 1)
    header += struct.pack('>I', 9)
    return header

def create_flv_tag(frame_data, timestamp=0):
    tag_type = b'\x09'
    data_size = struct.pack('>I', len(frame_data))[1:]
    timestamp_bytes = struct.pack('>I', timestamp)[1:]
    timestamp_extended = struct.pack('B', 0)
    stream_id = b'\x00\x00\x00'

    tag_header = tag_type + data_size + timestamp_bytes + timestamp_extended + stream_id

    frame_type = 1
    codec_id = 2
    video_header = struct.pack('B', (frame_type << 4) | codec_id)
    
    jpeg_type = b'\x00'
    video_data = jpeg_type + frame_data

    flv_tag = tag_header + video_header + video_data

    previous_tag_size = struct.pack('>I', len(flv_tag))

    return flv_tag + previous_tag_size
