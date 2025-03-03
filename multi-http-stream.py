from flask import Flask, Response
import cv2
from picamera2 import Picamera2
import threading
import time

app = Flask(__name__)

# Global variables to hold the latest frame and a lock for thread safety.
global_frame = None
frame_lock = threading.Lock()

def capture_frames():
    global global_frame
    picam2 = Picamera2()
    config = picam2.create_preview_configuration({"size": (1280, 720)})
    picam2.configure(config)
    picam2.start()  # Start capturing frames
    frame_index = 0

    while True:
        # Capture a frame from the camera
        frame = picam2.capture_array()
        if frame is None:
            continue

        frame_index += 1

        # Overlay frame index text
        text = f"Frame {frame_index}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1
        thickness = 2
        color = (0, 255, 0)  # Green
        (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
        h, w = frame.shape[:2]
        x = (w - text_width) // 2
        y = h - baseline
        cv2.putText(frame, text, (x, y), font, font_scale, color, thickness)

        # Encode the frame as JPEG
        ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ret:
            continue

        # Update the global frame in a thread-safe way
        with frame_lock:
            global_frame = buffer.tobytes()

        # Adjust delay as needed (e.g., for ~30 fps, use about 0.03 seconds)
        time.sleep(0.03)

# Start the background thread to capture frames continuously.
thread = threading.Thread(target=capture_frames)
thread.daemon = True
thread.start()

def gen_frames():
    """Generator function that yields the latest JPEG frame in MJPEG format."""
    global global_frame
    while True:
        with frame_lock:
            if global_frame is None:
                continue
            frame = global_frame
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video')
def video_feed():
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    # Run the Flask app on all interfaces.
    app.run(host='0.0.0.0', port=8485, threaded=True)
