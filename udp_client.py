import socket
import pickle
import cv2
import time

# Set up UDP socket
LISTEN_IP = ''  # Bind to all available interfaces
SERVER_PORT = 8485
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((LISTEN_IP, SERVER_PORT))
sock.settimeout(0.5)  # Optional timeout to allow graceful exit

# Create a full screen window for display
window_name = "UDP Stream"
cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
#cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

# Variables for FPS calculation
frame_count = 0
start_time = time.time()
fps = 0

try:
    while True:
        try:
            # Receive data (assuming each packet is a complete frame)
            data, addr = sock.recvfrom(65536)  # 64KB buffer size, adjust as needed
        except socket.timeout:
            continue  # If no data is received within the timeout, continue

        # Unpickle the received JPEG buffer
        try:
            buffer = pickle.loads(data)
        except Exception as e:
            print("Pickle error:", e)
            continue

        # Decode the JPEG buffer to an image (frame)
        frame = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        if frame is None:
            continue

        # Update and calculate FPS
        frame_count += 1
        elapsed_time = time.time() - start_time
        if elapsed_time > 1:
            fps = frame_count / elapsed_time
            frame_count = 0
            start_time = time.time()

        # Overlay FPS on the frame
        cv2.putText(frame, f"FPS: {fps:.2f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        # Display the frame in full screen
        cv2.imshow(window_name, frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

except KeyboardInterrupt:
    print("Exiting...")
finally:
    sock.close()
    cv2.destroyAllWindows()
