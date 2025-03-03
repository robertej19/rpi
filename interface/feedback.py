from flask import Flask, Response, request, jsonify, send_from_directory
import cv2
from picamera2 import Picamera2
import threading
import time

app = Flask(__name__)

# Global variables to hold the latest frame and the current click coordinates.
global_frame = None
click_coords = None  # (x, y) for center of the red box
frame_lock = threading.Lock()

def capture_frames():
    global global_frame, click_coords
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
        color = (0, 255, 0)  # Green
        (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
        h, w = frame.shape[:2]
        x_text = (w - text_width) // 2
        y_text = h - baseline
        cv2.putText(frame, text, (x_text, y_text), font, font_scale, color, thickness)

        # Draw a persistent red box if a click has been made.
        with frame_lock:
            if click_coords is not None:
                x_click, y_click = click_coords
                half_width = 100  # Half of 200px width
                half_height = 100  # Half of 200px height

                # Calculate rectangle boundaries (ensuring they remain within frame dimensions)
                x1 = max(0, x_click - half_width)
                y1 = max(0, y_click - half_height)
                x2 = min(w, x_click + half_width)
                y2 = min(h, y_click + half_height)
                
                # Draw a red rectangle (red in BGR is (0, 0, 255))
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)

        # Convert the frame from BGR to RGB.
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Encode the frame as JPEG with quality 80.
        ret, buffer = cv2.imencode('.jpg', frame_rgb, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ret:
            continue

        with frame_lock:
            global_frame = buffer.tobytes()

        time.sleep(0.03)  # Adjust delay for desired frame rate

# Start a background thread to capture frames.
thread = threading.Thread(target=capture_frames)
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

if __name__ == '__main__':
    # Run the Flask server on all interfaces (adjust port if necessary).
    app.run(host='0.0.0.0', port=8485, threaded=True)
