import cv2
import socket
import pickle
import struct
import time
import numpy as np

from picamera2 import Picamera2

# -------------------------------
# Initialize the Picamera2 instance and start the camera.
# -------------------------------
picam2 = Picamera2()
# Configure the camera with a preview resolution (adjust as needed)
config = picam2.create_preview_configuration({"size": (1280, 720)})
picam2.configure(config)
picam2.start()

FRAME_RATE = 30  # Target frame rate (Hz)

# -------------------------------
# Set up the server socket.
# -------------------------------
SERVER_IP = ''         # Listen on all available interfaces.
SERVER_PORT = 8485     # Port to listen on.
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((SERVER_IP, SERVER_PORT))

#server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#server_socket.bind((SERVER_IP, SERVER_PORT))
server_socket.listen(0)
print("Server listening on port", SERVER_PORT)

# Wait for a client to connect.
conn, addr = server_socket.accept()
print("Connected by:", addr)

# -------------------------------
# Define the ROI coordinates.
# -------------------------------
# Set the ROI (region-of-interest) by defining its top-left and bottom-right coordinates.
# For example, here we choose an ROI from (x=200, y=150) to (x=1000, y=600)
ROI_X1, ROI_Y1 = 200, 150
ROI_X2, ROI_Y2 = 1000, 600

while True:
    # Capture a frame as a NumPy array.
    frame = picam2.capture_array()
    if frame is None:
        print("Failed to capture frame")
        time.sleep(1/FRAME_RATE)
        continue

    # Optionally, resize the frame for consistent processing (fix height to 480 pixels).
    desired_height = 480
    scale = desired_height / frame.shape[0]
    new_width = int(frame.shape[1] * scale)
    frame = cv2.resize(frame, (new_width, desired_height))

    # Draw the ROI rectangle on the frame for visualization (blue rectangle).
    cv2.rectangle(frame, (ROI_X1, ROI_Y1), (ROI_X2, ROI_Y2), (255, 0, 0), 2)

    # Extract the ROI from the frame.
    roi = frame[ROI_Y1:ROI_Y2, ROI_X1:ROI_X2]

    # Convert the ROI to grayscale.
    gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    # Apply Gaussian blur to the grayscale ROI to reduce noise.
    gray_roi = cv2.GaussianBlur(gray_roi, (5, 5), 0)
    # Apply adaptive threshold (using MEAN method) with inversion.
    # THRESH_BINARY_INV will make a dark object become white (foreground)
    # on a black background if the original object is dark on a light background.
    thresh_roi = cv2.adaptiveThreshold(
        gray_roi,
        maxValue=255,
        adaptiveMethod=cv2.ADAPTIVE_THRESH_MEAN_C,
        thresholdType=cv2.THRESH_BINARY_INV,
        blockSize=11,
        C=7
    )

    # Use morphological opening to remove noise.
    kernel = np.ones((3, 3), np.uint8)
    thresh_clean = cv2.morphologyEx(thresh_roi, cv2.MORPH_OPEN, kernel, iterations=1)

    # Find contours in the thresholded ROI.
    contours, _ = cv2.findContours(thresh_clean.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # For debugging: create a copy of the ROI to draw contours.
    roi_debug = roi.copy()
    cv2.drawContours(roi_debug, contours, -1, (0, 255, 0), 2)

    # List to hold bounding box information (x, y, w, h) for large contours.
    large_objects = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > 1000:  # Adjust this area threshold as needed.
            x, y, w, h = cv2.boundingRect(cnt)
            cv2.rectangle(roi_debug, (x, y), (x+w, y+h), (0, 0, 255), 2)
            large_objects.append((x, y, w, h))

    # Replace the ROI in the full frame with the debug ROI (so the drawn contours are visible).
    frame[ROI_Y1:ROI_Y2, ROI_X1:ROI_X2] = roi_debug

    # Encode the processed frame as JPEG.
    ret, buffer = cv2.imencode(".jpg", frame)
    if not ret:
        time.sleep(1/FRAME_RATE)
        continue

    # Package the data in a dictionary.
    payload = {
        "timestamp": time.time(),
        "large_objects": large_objects,   # List of bounding boxes relative to the ROI.
        "ROI": (ROI_X1, ROI_Y1, ROI_X2, ROI_Y2),
        "frame": buffer.tobytes()
    }

    # Serialize the payload using pickle.
    data = pickle.dumps(payload)
    # Prepend the length of the serialized data as a 4-byte header.
    message = struct.pack(">L", len(data)) + data

    try:
        conn.sendall(message)
    except BrokenPipeError:
        print("Connection lost.")
        break













