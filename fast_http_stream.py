from flask import Flask, Response
import cv2
from picamera2 import Picamera2

app = Flask(__name__)

def gen_frames():
    # Initialize the camera and configure the preview resolution.
    picam2 = Picamera2()
    config = picam2.create_preview_configuration({"size": (1280, 720)})
    picam2.configure(config)
    picam2.start()  # Start camera capture for preview
    frame_index = 0

    while True:
        # Capture a frame as a NumPy array
        frame = picam2.capture_array()
        if frame is None:
            continue

        frame_index += 1

        # Overlay frame index text
        text = f"Frame {frame_index}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1
        thickness = 2
        color = (0, 255, 0)  # Green in BGR

        (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
        h, w = frame.shape[:2]
        x = (w - text_width) // 2
        y = h - baseline  # slightly above the bottom

        cv2.putText(frame, text, (x, y), font, font_scale, color, thickness)

        # Encode the frame as JPEG with quality 80
        ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ret:
            continue

        frame_bytes = buffer.tobytes()

        # Yield the frame in MJPEG format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video')
def video_feed():
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    # The server listens on all interfaces. Replace '8485' with any port you prefer.
    app.run(host='0.0.0.0', port=8485, threaded=True)

















