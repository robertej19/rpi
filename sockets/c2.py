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
# Global variables to store the latest payload for each camera.
# -------------------------
latest_payload1 = None
latest_payload2 = None
payload_lock1 = threading.Lock()
payload_lock2 = threading.Lock()

# -------------------------
# Settings for the two Pi‑camera servers.
# -------------------------
PI1_SERVER_IP = "192.168.1.190"  # CHANGE THIS to the IP address for camera 1
PI2_SERVER_IP = "192.168.1.184"# CHANGE THIS to the IP address for camera 2
PI_SERVER_PORT = 8485

def socket_receiver(ip, port, lock, cam_id):
    global latest_payload1, latest_payload2
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((ip, port))
        print(f"Connected to Pi server for cam {cam_id} at {ip}:{port}")
    except Exception as e:
        print("Error connecting to Pi server at", ip, e)
        return
    data = b""
    payload_size = struct.calcsize(">L")
    while True:
        try:
            while len(data) < payload_size:
                packet = s.recv(4096)
                if not packet:
                    print("Connection closed by server at", ip)
                    return
                data += packet
            packed_msg_size = data[:payload_size]
            data = data[payload_size:]
            msg_size = struct.unpack(">L", packed_msg_size)[0]
            while len(data) < msg_size:
                packet = s.recv(4096)
                if not packet:
                    print("Connection closed by server at", ip)
                    return
                data += packet
            frame_data = data[:msg_size]
            data = data[msg_size:]
            payload = pickle.loads(frame_data)
            with lock:
                if cam_id == 1:
                    latest_payload1 = payload
                else:
                    latest_payload2 = payload
            num_objs = len(payload.get("large_objects", [])) if payload.get("large_objects") is not None else 0
            #print(f"Received payload from cam {cam_id} at {payload.get('timestamp')}, found {num_objs} objects")
        except Exception as e:
            print("Error receiving data from", ip, e)
            break

# Start receiver threads for both cameras.
t1 = threading.Thread(target=socket_receiver, args=(PI1_SERVER_IP, PI_SERVER_PORT, payload_lock1, 1), daemon=True)
t2 = threading.Thread(target=socket_receiver, args=(PI2_SERVER_IP, PI_SERVER_PORT, payload_lock2, 2), daemon=True)
t1.start()
t2.start()

app = Flask(__name__)

@app.route('/')
def index():
    # The HTML page displays two video streams side-by-side and a scene view with detection info.
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Live Video & 2D Scene from Two Cameras</title>
            <script>
                function fetchDetectionInfo() {
                    fetch("/detection_info")
                      .then(response => response.json())
                      .then(data => {
                          document.getElementById("detectionInfo").innerText =
                              "Cam1 - Centroid: " + (data.cam1.centroid ? "(" + data.cam1.centroid.join(", ") + ")" : "N/A") +
                              " | Width: " + (data.cam1.width ? data.cam1.width + " px" : "N/A") +
                              " | Dist: " + (data.cam1.distance ? data.cam1.distance + " cm" : "N/A") +
                              "\\nCam2 - Centroid: " + (data.cam2.centroid ? "(" + data.cam2.centroid.join(", ") + ")" : "N/A") +
                              " | Width: " + (data.cam2.width ? data.cam2.width + " px" : "N/A") +
                              " | Dist: " + (data.cam2.distance ? data.cam2.distance + " cm" : "N/A");
                      })
                      .catch(error => {
                          document.getElementById("detectionInfo").innerText = "Error: " + error;
                      });
                }
                setInterval(fetchDetectionInfo, 500);
            </script>
        </head>
        <body>
            <h1>Live Video Streams</h1>
            <div style="display:flex;">
                <div style="margin-right:10px;">
                    <h3>Camera 1</h3>
                    <img src="{{ url_for('video_feed_cam1') }}" style="width:100%; max-width:600px;" />
                </div>
                <div>
                    <h3>Camera 2</h3>
                    <img src="{{ url_for('video_feed_cam2') }}" style="width:100%; max-width:600px;" />
                </div>
            </div>
            <pre id="detectionInfo" style="white-space: pre-wrap; background: #f0f0f0; padding: 10px;">Loading detection info...</pre>
            <hr>
            <h1>Scene View</h1>
            <img src="{{ url_for('scene_feed') }}" style="width:100%; max-width:1200px;" />
        </body>
        </html>
    ''')

# MJPEG generator for Camera 1 video.
def gen_frames_cam1():
    global latest_payload1
    while True:
        with payload_lock1:
            payload = latest_payload1
        if payload is not None and "frame" in payload:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + payload["frame"] + b'\r\n')
        else:
            time.sleep(0.03)

@app.route('/video_feed_cam1')
def video_feed_cam1():
    return Response(gen_frames_cam1(), mimetype='multipart/x-mixed-replace; boundary=frame')

# MJPEG generator for Camera 2 video.
def gen_frames_cam2():
    global latest_payload2
    while True:
        with payload_lock2:
            payload = latest_payload2
        if payload is not None and "frame" in payload:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + payload["frame"] + b'\r\n')
        else:
            time.sleep(0.03)

@app.route('/video_feed_cam2')
def video_feed_cam2():
    return Response(gen_frames_cam2(), mimetype='multipart/x-mixed-replace; boundary=frame')

# Combined detection info from both cameras.
@app.route('/detection_info')
def detection_info():
    info = {"cam1": {"centroid": None, "width": None, "distance": None},
            "cam2": {"centroid": None, "width": None, "distance": None}}
    with payload_lock1:
        payload1 = latest_payload1
    if payload1 is not None:
        large_objects1 = payload1.get("large_objects")
        roi1 = payload1.get("ROI")  # (ROI_X1, ROI_Y1, ROI_X2, ROI_Y2)
        if large_objects1 and len(large_objects1) > 0:
            x, y, w, h = large_objects1[0]
            if roi1 is not None:
                ROI_X1, ROI_Y1, _, _ = roi1
                centroid = [x + w//2 + ROI_X1, y + h//2 + ROI_Y1]
            else:
                centroid = [x + w//2, y + h//2]
            info["cam1"]["centroid"] = centroid
            info["cam1"]["width"] = w
            try:
                distance_cm = int(3000 / float(w))
            except Exception as e:
                distance_cm = None
            info["cam1"]["distance"] = distance_cm

    with payload_lock2:
        payload2 = latest_payload2
    if payload2 is not None:
        large_objects2 = payload2.get("large_objects")
        roi2 = payload2.get("ROI")
        if large_objects2 and len(large_objects2) > 0:
            x, y, w, h = large_objects2[0]
            if roi2 is not None:
                ROI_X1, ROI_Y1, _, _ = roi2
                centroid = [x + w//2 + ROI_X1, y + h//2 + ROI_Y1]
            else:
                centroid = [x + w//2, y + h//2]
            info["cam2"]["centroid"] = centroid
            info["cam2"]["width"] = w
            try:
                distance_cm = int(3000 / float(w))
            except Exception as e:
                distance_cm = None
            info["cam2"]["distance"] = distance_cm
    return jsonify(info)

# Scene view MJPEG generator.
def gen_scene():
    """
    Create a live-updating 2D scene with:
      - Camera1 (red box) at (0,0)
      - Camera2 (blue box) at (100,0) facing -x
      - For Cam1, the detected object as a blue circle at x = distance_cm.
      - For Cam2, the detected object as a green circle at x = 100 - distance_cm.
      
    All distances (in centimeters) are rounded to the nearest integer, and
    all items are drawn on the same horizontal line.
    """
    global latest_payload1, latest_payload2
    scale = 5  # 5 pixels per cm (adjust as needed)
    # We'll assume the x-axis covers from 0 to 120 cm.
    scene_width_cm = 120  
    scene_width = int(scene_width_cm * scale)
    scene_height = 150
    baseline_y = scene_height // 2  # everything will be drawn at this y position

    while True:
        # Create a white background for the scene.
        scene = np.ones((scene_height, scene_width, 3), dtype=np.uint8) * 255
        
        # Draw the x-axis line (for reference)
        cv2.line(scene, (0, baseline_y), (scene_width, baseline_y), (0, 0, 0), 1)
        
        # --- Draw Camera 1 as a red box at x=0 ---
        # We'll draw a red rectangle representing Cam1 at the left.
        cam1_x_px = 10  # An arbitrary horizontal offset so the camera icon isn't flush against the left edge.
        cam_box_width = 30
        cam_box_height = 40
        cam1_top_left = (cam1_x_px, baseline_y - cam_box_height//2)
        cam1_bottom_right = (cam1_x_px + cam_box_width, baseline_y + cam_box_height//2)
        cv2.rectangle(scene, cam1_top_left, cam1_bottom_right, (0, 0, 255), -1)
        cv2.putText(scene, "Cam1", (cam1_x_px, baseline_y - cam_box_height//2 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        
        # --- Draw Camera 2 as a blue box at x=100 cm ---
        cam2_world_x = 100  # in cm
        cam2_x_px = int(cam2_world_x * scale)
        # For Cam2 facing -x, we align the box so its right edge is at x = cam2_x_px.
        cam2_top_left = (cam2_x_px - cam_box_width, baseline_y - cam_box_height//2)
        cam2_bottom_right = (cam2_x_px, baseline_y + cam_box_height//2)
        cv2.rectangle(scene, cam2_top_left, cam2_bottom_right, (255, 0, 0), -1)
        cv2.putText(scene, "Cam2", (cam2_top_left[0], baseline_y - cam_box_height//2 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        
        # --- Process Camera 1 detection ---
        with payload_lock1:
            p1 = latest_payload1
        if p1 is not None and p1.get("large_objects") is not None and len(p1["large_objects"]) > 0:
            x, y, w, h = p1["large_objects"][0]
            try:
                # Compute distance in cm and round to nearest integer.
                dist_cm = int(round(3000 / float(w)))
            except Exception as e:
                dist_cm = None
            if dist_cm is not None:
                # For Cam1, the object's world coordinate is x = dist_cm.
                obj1_x_px = int(dist_cm * scale)
                # Draw the object as a blue circle (object width is 3 cm so radius in scene = (3*scale)/2).
                obj_radius = int((3 * scale) / 2)
                cv2.circle(scene, (obj1_x_px, baseline_y), obj_radius, (255, 0, 0), -1)
                # Draw the distance text above the object.
                cv2.putText(scene, f"{dist_cm} cm", (obj1_x_px, baseline_y - obj_radius - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        
        # --- Process Camera 2 detection ---
        with payload_lock2:
            p2 = latest_payload2
        if p2 is not None and p2.get("large_objects") is not None and len(p2["large_objects"]) > 0:
            x, y, w, h = p2["large_objects"][0]
            try:
                dist_cm = int(round(3000 / float(w)))
            except Exception as e:
                dist_cm = None
            if dist_cm is not None:
                # For Cam2 (at 100 cm facing -x), the object's world x coordinate is 100 - distance.
                obj_world_x = 100 - dist_cm
                obj2_x_px = int(obj_world_x * scale)
                obj_radius = int((3 * scale) / 2)
                # Draw the object as a green circle.
                cv2.circle(scene, (obj2_x_px, baseline_y), obj_radius, (0, 255, 0), -1)
                cv2.putText(scene, f"{dist_cm} cm", (obj2_x_px, baseline_y - obj_radius - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        
        ret, buffer = cv2.imencode(".jpg", scene)
        if ret:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        time.sleep(0.1)  # update about 5 times per second


@app.route('/scene_feed')
def scene_feed():
    return Response(gen_scene(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
