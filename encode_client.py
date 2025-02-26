import socket
import pickle
import struct
import cv2
import time

SERVER_IP = '192.168.1.184'
SERVER_PORT = 8485

# Create and connect the socket
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect((SERVER_IP, SERVER_PORT))

data = b""
payload_size = struct.calcsize("L")

# Set up the full screen window
window_name = "Received Frame"
cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
#cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

# Variables to track FPS
frame_count = 0
start_time = time.time()
fps = 0

try:
    while True:
        # Retrieve message size (header)
        while len(data) < payload_size:
            packet = client_socket.recv(4096)
            if not packet:
                raise ConnectionError("Socket connection closed")
            data += packet

        packed_msg_size = data[:payload_size]
        data = data[payload_size:]
        msg_size = struct.unpack("L", packed_msg_size)[0]

        # Retrieve the full frame based on the message size
        while len(data) < msg_size:
            packet = client_socket.recv(4096)
            if not packet:
                raise ConnectionError("Socket connection closed during frame reception")
            data += packet

        frame_data = data[:msg_size]
        data = data[msg_size:]

        # Unpickle the JPEG buffer and decode the frame
        buffer = pickle.loads(frame_data)
        frame = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        #convert frame from BGR to RGB
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        monitor_width, monitor_height = 3000, 1800
        frame = cv2.resize(frame, (monitor_width, monitor_height))
        
        # FPS calculation
        frame_count += 1
        elapsed_time = time.time() - start_time
        if elapsed_time > 1:
            fps = frame_count / elapsed_time
            frame_count = 0
            start_time = time.time()

        # Overlay the FPS on the frame
        cv2.putText(frame, f"FPS: {fps:.2f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        cv2.imshow(window_name, frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
except Exception as e:
    print(f"Error: {e}")
finally:
    client_socket.close()
    cv2.destroyAllWindows()
