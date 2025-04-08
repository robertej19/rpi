import cv2
import socket
import pickle
import struct
import time
import numpy as np

# Import the Picamera2 API.
from picamera2 import Picamera2

# -------------------------------
# Initialize the Picamera2 instance and start the camera.
# -------------------------------
picam2 = Picamera2()
# Create a preview configuration (adjust resolution as desired).
config = picam2.create_preview_configuration({"size": (1280, 720)})
picam2.configure(config)
# For processing using capture_array(), simply start the camera.
picam2.start()

FRAME_RATE = 30  # Target frame rate (Hz)

# -------------------------------
# Set up the server socket.
# -------------------------------
SERVER_IP = ''         # Listen on all available interfaces.
SERVER_PORT = 8485     # Port to listen on.
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((SERVER_IP, SERVER_PORT))
server_socket.listen(0)
print("Server listening on port", SERVER_PORT)

# Wait for a client connection.
conn, addr = server_socket.accept()
print("Connected by:", addr)

def process_frame(frame):
    """
    Process the frame to detect circles using Hough Circle Transform.
    Draws ALL detected circles on the frame for debugging and returns the
    modified frame and an array of detected circles.
    
    The function:
      1. Converts the frame to grayscale.
      2. Applies Gaussian blur to reduce noise.
      3. Uses cv2.HoughCircles to detect circles.
      4. Draws each detected circle and its center on the frame.
      5. Prints the detected circle parameters for debugging.
      
    Returns:
      - The processed frame (with drawn circles),
      - The list of detected circles (or None if none were found),
      - (For compatibility, we return None for radius as overall data.)
    """
    # Convert the frame to grayscale.
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    # Apply Gaussian blur to reduce noise.
    blurred = cv2.GaussianBlur(gray, (9, 9), 2)
    
    # Detect circles using Hough Circle Transform.
    circles = cv2.HoughCircles(blurred, cv2.HOUGH_GRADIENT,
                               dp=1.2,
                               minDist=50,
                               param1=100,
                               param2=30,
                               minRadius=10,
                               maxRadius=0)  # maxRadius=0 means no upper limit.
    
    if circles is not None:
        circles = np.round(circles[0, :]).astype("int")
        print("Detected circles:", circles)   # Debug print.
        # Loop over all detected circles.
        for (x, y, r) in circles:
            # Draw the outer circle in green.
            cv2.circle(frame, (x, y), r, (0, 255, 0), 2)
            # Draw the center of the circle in red.
            cv2.circle(frame, (x, y), 3, (0, 0, 255), -1)
    else:
        print("No circles detected.")
    return frame, circles, None

print("Starting video transmission (drawing all circles)...")

while True:
    # Capture a frame from the camera as a NumPy array.
    frame = picam2.capture_array()
    if frame is None:
        print("Failed to capture frame")
        time.sleep(1/FRAME_RATE)
        continue

    # Optionally resize the frame to a fixed height (e.g., 480 pixels) for consistency.
    desired_height = 480
    scale = desired_height / frame.shape[0]
    new_width = int(frame.shape[1] * scale)
    frame = cv2.resize(frame, (new_width, desired_height))
    
    # Process the frame: detect and draw ALL circles.
    processed_frame, circles, _ = process_frame(frame)
    
    # Encode the processed frame as JPEG.
    ret, buffer = cv2.imencode(".jpg", processed_frame)
    if not ret:
        time.sleep(1/FRAME_RATE)
        continue

    # Package the data into a payload dictionary.
    payload = {
        "timestamp": time.time(),
        "circles": circles.tolist() if circles is not None else None,  # List of [x, y, r] values.
        "frame": buffer.tobytes()
    }
    
    # Serialize the payload.
    data = pickle.dumps(payload)
    # Prepend the length of the serialized data as a 4-byte header.
    message = struct.pack(">L", len(data)) + data
    
    try:
        conn.sendall(message)
    except BrokenPipeError:
        print("Connection lost.")
        break
    
    time.sleep(1/FRAME_RATE)

# Clean up resources.
conn.close()
server_socket.close()
picam2.stop()
