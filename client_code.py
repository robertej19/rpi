import socket
import pickle
import struct
import cv2

# Define the server address and port
SERVER_IP = '192.168.1.184'
SERVER_PORT = 8485

# Create a TCP/IP socket
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect((SERVER_IP, SERVER_PORT))

data = b""
# The header size is based on an unsigned long (8 bytes on many systems)
# Adjust the format ("L") if your server sends a different type
payload_size = struct.calcsize("L")

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

        # Unpickle the received frame
        # On the client side:
        buffer = pickle.loads(frame_data)
        frame = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        #frame = pickle.loads(frame_data)

        # Display the frame using OpenCV
        cv2.imshow("Received Frame", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
except Exception as e:
    print(f"Error: {e}")
finally:
    client_socket.close()
    cv2.destroyAllWindows()
