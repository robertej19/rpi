import socket
import pickle
import struct
import cv2
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder

# Set up the server socket
SERVER_IP = ''  # Listen on all available interfaces
SERVER_PORT = 8485

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((SERVER_IP, SERVER_PORT))
server_socket.listen(0)
print("Server listening on port", SERVER_PORT)

# Wait for a client to connect
conn, addr = server_socket.accept()
print("Connected by:", addr)

# Initialize the Picamera2 instance and start the camera
picam2 = Picamera2()
#config = picam2.create_preview_configuration({"size": (1280, 720)})
config = picam2.create_preview_configuration({"size": (320, 180)})
picam2.configure(config)
encoder = H264Encoder()
picam2.start_recording(encoder,"testvideo.h264")
#picam2.start()

try:
    while True:
        # Capture a frame from the camera as a NumPy array (compatible with OpenCV)
        frame = picam2.capture_array()

        # Optionally, you can add overlay text (uncomment the next lines if desired)
        # text = "Live Stream"
        # position = (10, 30)
        # cv2.putText(frame, text, position, cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        # Serialize (pickle) the frame
        # On the server side:
        ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        data = pickle.dumps(buffer)
        #data = pickle.dumps(frame)
        
        # Pack the size of the pickled data (header) using an unsigned long
        message_size = struct.pack("L", len(data))
        
        # Send header and data over the socket
        conn.sendall(message_size + data)
except Exception as e:
    print("Error:", e)
finally:
    conn.close()
    server_socket.close()
    picam2.close()
