from client.modules.rtmp import stream_screen_to_rtmp


if __name__ == "__main__":
    RTMP_SERVER = "localhost"
    RTMP_PORT = 1935
    RTMP_APP = "live"        # The application name on your RTMP server
    RTMP_STREAM_KEY = "stream_key.flv"  # Your stream key

    stream_screen_to_rtmp(RTMP_SERVER, RTMP_PORT, RTMP_APP, RTMP_STREAM_KEY, fps=5)
