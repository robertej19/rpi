import socket
import pickle
import struct
import threading
import time
import cv2
import numpy as np
import os
from flask import Flask, Response, render_template_string, jsonify

# -------------------------
# Global variables to store the latest payload.
# -------------------------
latest_payload = None
payload_lock = threading.Lock()

# -------------------------
# Settings for the connection to the Pi server.
# -------------------------
PI_SERVER_IP = "192.168.1.190"  # Replace with your Raspberry Pi's IP address.
PI_SERVER_PORT = 8485

# -------------------------
# Socket receiver thread to update latest_payload.
# -------------------------
def socket_receiver():
    global latest_payload
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((PI_SERVER_IP, PI_SERVER_PORT))
        print(f"Connected to Pi server at {PI_SERVER_IP}:{PI_SERVER_PORT}")
    except Exception as e:
        print("Error connecting to Pi server:", e)
        return

    data = b""
    payload_size = struct.calcsize(">L")
    while True:
        try:
            while len(data) < payload_size:
                packet = s.recv(4096)
                if not packet:
                    print("Connection closed by server.")
                    return
                data += packet
            packed_msg_size = data[:payload_size]
            data = data[payload_size:]
            msg_size = struct.unpack(">L", packed_msg_size)[0]
            while len(data) < msg_size:
                packet = s.recv(4096)
                if not packet:
                    print("Connection closed by server.")
                    return
                data += packet
            frame_data = data[:msg_size]
            data = data[msg_size:]
            payload = pickle.loads(frame_data)
            with payload_lock:
                latest_payload = payload
            # Debug: print a received timestamp and number of large objects (if any)
            num_objs = len(payload.get("large_objects", [])) if payload.get("large_objects") is not None else 0
            print(f"Received new payload at {payload.get('timestamp')}, found {num_objs} large objects")
        except Exception as e:
            print("Error receiving data:", e)
            break

# Start the receiver thread.
receiver_thread = threading.Thread(target=socket_receiver, daemon=True)
receiver_thread.start()

# -------------------------
# Flask app setup.
# -------------------------
app = Flask(__name__)

# HTML page: displays video feed and scene.
@app.route('/')
def index():
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Live Video & Scene</title>
            <script>
                // Poll the detection info endpoint every 500ms.
                function fetchDetectionInfo() {
                    fetch("/detection_info")
                      .then(response => response.json())
                      .then(data => {
                          document.getElementById("detectionInfo").innerText =
                              "Centroid: " + (data.centroid ? "(" + data.centroid.join(", ") + ")" : "N/A") +
                              " | Object width: " + (data.width ? data.width + " px" : "N/A") +
                              " | Estimated distance: " + (data.distance ? data.distance + " cm" : "N/A");
                      })
                      .catch(error => {
                          document.getElementById("detectionInfo").innerText = "Error: " + error;
                      });
                }
                setInterval(fetchDetectionInfo, 500);
            </script>
        </head>
        <body>
            <h1>Live Video Feed</h1>
            <img src="{{ url_for('video_feed') }}" style="width:100%; max-width:1200px;" />
            <h3 id="detectionInfo">Loading detection info...</h3>
            <hr>
            <h1>Scene View</h1>
            <img src="{{ url_for('scene_feed') }}" style="width:100%; max-width:1200px;" />
        </body>
        </html>
    ''')

# -------------------------
# MJPEG generator for video feed.
# -------------------------
def gen_frames():
    global latest_payload
    while True:
        with payload_lock:
            payload = latest_payload
        if payload is not None and "frame" in payload:
            # Debug print to see frame yielding.
            print("Yielding video frame at", payload.get("timestamp"))
            frame = payload["frame"]
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        else:
            time.sleep(0.03)

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# -------------------------
# Endpoint that returns detection info as JSON.
# -------------------------
@app.route('/detection_info')
def detection_info():
    info = {"centroid": None, "width": None, "distance": None}
    with payload_lock:
        payload = latest_payload
    if payload is not None:
        large_objects = payload.get("large_objects")
        roi = payload.get("ROI")  # ROI is a tuple: (ROI_X1, ROI_Y1, ROI_X2, ROI_Y2)
        if large_objects and len(large_objects) > 0:
            # Use the first large object's bounding box.
            x, y, w, h = large_objects[0]
            # Compute centroid relative to the full frame:
            if roi is not None:
                ROI_X1, ROI_Y1, _, _ = roi
                centroid = [x + w//2 + ROI_X1, y + h//2 + ROI_Y1]
            else:
                centroid = [x + w//2, y + h//2]
            info["centroid"] = centroid
            info["width"] = w
            # Calculate estimated distance (in cm):
            # Using: distance_cm = 3000 / width (if pixel pitch = 1 milliradian and object width = 3 cm)
            try:
                distance_cm = int(3000 / float(w))
            except Exception as e:
                distance_cm = None
            info["distance"] = distance_cm
    return jsonify(info)

# -------------------------
# MJPEG generator for the scene.
# -------------------------
def gen_scene():
    global latest_payload
    # Define scale: 5 pixels per centimeter.
    scale = 5  
    # Define scene image size (e.g., 800px wide by 150px tall).
    scene_width = 800
    scene_height = 150
    while True:
        # Create a white background image.
        scene = np.ones((scene_height, scene_width, 3), dtype=np.uint8) * 255
        
        # Draw the camera as a red box at (0,0). For visualization, we place it at a fixed location.
        # Let’s draw a red rectangle at coordinates (10, 50) to (60, 100).
        cv2.rectangle(scene, (10, 50), (60, 100), (0, 0, 255), -1)
        cv2.putText(scene, "Camera", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255), 1)
        
        # Read the latest payload.
        with payload_lock:
            payload = latest_payload
        if payload is not None:
            large_objects = payload.get("large_objects")
            if large_objects and len(large_objects) > 0:
                # Use the first object's bounding box width (w) to compute distance.
                _, _, w, _ = large_objects[0]
                try:
                    distance_cm = 3000 / float(w)
                except Exception as e:
                    distance_cm = None
                if distance_cm is not None:
                    # Convert distance in cm to scene x-coordinate using our scale.
                    # For example, x_pos = distance_cm * scale. (We add an offset so the camera is at 0.)
                    x_pos = int(distance_cm * scale)
                    # Prevent drawing off the scene.
                    x_pos = min(x_pos, scene_width - 30)
                    # Draw the object as a blue circle.
                    # We know object width is 3 cm, so radius in scene = (3 cm * scale)/2.
                    object_radius = int((3 * scale) / 2)
                    cv2.circle(scene, (x_pos, scene_height//2), object_radius, (255, 0, 0), -1)
                    # Write the distance text above the object.
                    cv2.putText(scene, f"{distance_cm} cm", (x_pos, scene_height//2 - object_radius - 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        ret, buffer = cv2.imencode(".jpg", scene)
        if ret:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        time.sleep(0.2)  # update the scene ~5 fps

@app.route('/scene_feed')
def scene_feed():
    return Response(gen_scene(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    # Ensure we run in a single process (disable reloader).
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
