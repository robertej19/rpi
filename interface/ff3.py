from flask import Flask, Response, request, jsonify, send_from_directory
import cv2
from picamera2 import Picamera2
import threading
import time
import sys

app = Flask(__name__)

# Global variables for the latest frame, click coordinates, and box color.
global_frame = None
click_coords = None  # (x, y) for the center of the box
box_color = (0, 0, 255)  # Default to red (BGR)
frame_lock = threading.Lock()

def capture_frames(arg):
    global global_frame, click_coords, box_color
    picam2 = Picamera2()
    config = picam2.create_preview_configuration({"size": (1280, 720)})
    picam2.configure(config)
    picam2.start()  # Start capturing frames
    frame_index = 0

    while True:
        frame = picam2.capture_array()
        if frame is None:
            continue

        frame_index += 1

        # Overlay frame counter text.
        text = f"Frame {frame_index}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1
        thickness = 2
        text_color = (0, 255, 0)  # Green text
        (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
        h, w = frame.shape[:2]
        x_text = (w - text_width) // 2
        y_text = h - baseline
        cv2.putText(frame, text, (x_text, y_text), font, font_scale, text_color, thickness)

        # Draw a persistent box if a click has been made.
        with frame_lock:
            if click_coords is not None:
                x_click, y_click = click_coords
                half_width = 100  # Half of 200px width
                half_height = 100  # Half of 200px height
                x1 = max(0, x_click - half_width)
                y1 = max(0, y_click - half_height)
                x2 = min(w, x_click + half_width)
                y2 = min(h, y_click + half_height)
                cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 3)

        # Convert the frame from BGR to RGB.
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Encode the frame as JPEG.
        ret, buffer = cv2.imencode('.jpg', frame_rgb, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ret:
            continue

        with frame_lock:
            global_frame = buffer.tobytes()

        time.sleep(0.03)  # Adjust delay for desired frame rate

# Start the background thread for capturing frames, passing an example argument.
capture_arg = "example"  # Replace with your actual argument if needed.
thread = threading.Thread(target=capture_frames, args=(capture_arg,))
thread.daemon = True
thread.start()

def gen_frames():
    """Generator function that yields MJPEG frames."""
    global global_frame
    while True:
        with frame_lock:
            if global_frame is None:
                continue
            frame = global_frame
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/')
def index():
    # Serve the client-side HTML.
    return send_from_directory('.', 'index.html')

@app.route('/video')
def video_feed():
    # Stream the MJPEG frames.
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/click', methods=['POST'])
def click_handler():
    """
    Receives click coordinates from the client.
    Expected JSON format: { "x": <int>, "y": <int> }
    """
    global click_coords
    data = request.get_json()
    x = data.get('x')
    y = data.get('y')
    with frame_lock:
        click_coords = (x, y)
    print(f"Received click at: {click_coords}")
    return jsonify({'status': 'received', 'x': x, 'y': y})

@app.route('/setcolor', methods=['POST'])
def set_color():
    """
    Receives a color command from the client.
    Expected JSON format: { "color": "red" } or { "color": "green" }
    """
    global box_color
    data = request.get_json()
    color_str = data.get("color")
    with frame_lock:
        if color_str == "red":
            box_color = (0, 0, 255)  # Red in BGR
        elif color_str == "green":
            box_color = (0, 255, 0)  # Green in BGR
    print(f"Box color set to: {color_str}")
    return jsonify({"status": "received", "color": color_str})

@app.route('/exit', methods=['POST'])
def exit_handler():
    """
    Shuts down the Flask server when the client clicks the exit button.
    """
    shutdown = request.environ.get('werkzeug.server.shutdown')
    if shutdown is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    shutdown()
    return jsonify({"status": "server shutting down"})

if __name__ == '__main__':
    # Run the Flask server.
    app.run(host='0.0.0.0', port=8485, threaded=True)
