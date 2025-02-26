import socket
import pickle
import struct
import cv2

SERVER_IP = '192.168.1.184'
SERVER_PORT = 8485

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect((SERVER_IP, SERVER_PORT))

data = b""
payload_size = struct.calcsize("L")

# Create a named window and set it to full screen
window_name = "Received Frame"
cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
#cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

try:
    while True:
        while len(data) < payload_size:
            packet = client_socket.recv(4096)
            if not packet:
                raise ConnectionError("Socket connection closed")
            data += packet

        packed_msg_size = data[:payload_size]
        data = data[payload_size:]
        msg_size = struct.unpack("L", packed_msg_size)[0]

        while len(data) < msg_size:
            packet = client_socket.recv(4096)
            if not packet:
                raise ConnectionError("Socket connection closed during frame reception")
            data += packet

        frame_data = data[:msg_size]
        data = data[msg_size:]
        frame = pickle.loads(frame_data)

        # Optionally, resize frame to match your monitor resolution (if needed)
        monitor_width, monitor_height = 1920, 1080
        frame = cv2.resize(frame, (monitor_width, monitor_height))

        cv2.imshow(window_name, frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
except Exception as e:
    print(f"Error: {e}")
finally:
    client_socket.close()
    cv2.destroyAllWindows()
