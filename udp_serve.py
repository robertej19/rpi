import threading
import socket
import cv2
import pickle
import struct
from picamera2 import Picamera2

# Initialize camera and configure for lower resolution / high performance if needed
picam2 = Picamera2()
config = picam2.create_video_configuration({"size": (640, 480)})
picam2.configure(config)
picam2.start()

SERVER_IP = '192.168.1.184'
SERVER_PORT = 8485

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP for lower latency

def send_frames():
    while True:
        frame = picam2.capture_array()  # capture frame as numpy array

        # Encode frame with JPEG
        ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ret:
            continue

        # Pack frame size (if needed, or send as discrete UDP datagrams)
        data = pickle.dumps(buffer)

        # For UDP, you may need to chunk data if it exceeds the MTU; here we assume small enough frames
        sock.sendto(data, (SERVER_IP, SERVER_PORT))

# Run the frame sending in a separate thread
sender_thread = threading.Thread(target=send_frames, daemon=True)
sender_thread.start()

try:
    while True:
        pass  # main thread could handle monitoring or other tasks
except KeyboardInterrupt:
    print("Exiting...")
finally:
    picam2.close()
    sock.close()
