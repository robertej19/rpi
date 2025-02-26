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
# You can change the resolution here if desired:
config = picam2.create_preview_configuration({"size": (1280,720)})
#config = picam2.create_preview_configuration({"size": (320, 180)})
picam2.configure(config)
encoder = H264Encoder()
picam2.start_recording(encoder, "testvideo.h264")
#picam2.start()  # Uncomment if you want to use capture_array() without recording

frame_index = 0

try:
    while True:
        # Capture a frame from the camera as a NumPy array (compatible with OpenCV)
        frame = picam2.capture_array()
        
        # Increment frame index
        frame_index += 1
        
        # Prepare the text to be written
        text = f"Frame {frame_index}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1
        thickness = 2
        color = (0, 255, 0)  # Green in BGR
        
        # Determine text size to center it horizontally
        (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
        h, w = frame.shape[:2]
        x = (w - text_width) // 2
        y = h - baseline  # slightly above the bottom
        
        # Write the text on the frame
        cv2.putText(frame, text, (x, y), font, font_scale, color, thickness)
        
        # Encode the frame as JPEG
        ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ret:
            continue
        
        # Serialize (pickle) the JPEG buffer
        data = pickle.dumps(buffer)
        
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
