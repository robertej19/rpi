from flask import Flask, Response, request, jsonify, send_from_directory
import cv2
from picamera2 import Picamera2
import threading
import time

app = Flask(__name__)

# Global variables for the latest frame, click coordinates, box color, video mode, ROI, and Gaussian blur.
global_frame = None
click_coords = None  # (x, y) for the center of the box
box_color = (0, 0, 255)  # Default to red (BGR format)
video_mode = "color"  # "color" for full-color, "bw" for black & white

# ROI boundaries (default: full frame with nominal width=1280, height=720)
roi_x1 = 0
roi_x2 = 1280
roi_y1 = 0
roi_y2 = 720

# Gaussian blur parameters (kernel size and sigma).
gaussian_kernel_size = 1  # Use 1 to mean "no blur" (kernel size of 1x1)
gaussian_sigma = 0.0

frame_lock = threading.Lock()

def capture_frames():
    global global_frame, click_coords, box_color, video_mode, roi_x1, roi_x2, roi_y1, roi_y2, gaussian_kernel_size, gaussian_sigma
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
        text_color = (0, 255, 0)  # Green for text
        (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
        h, w = frame.shape[:2]
        x_text = (w - text_width) // 2
        y_text = h - baseline
        cv2.putText(frame, text, (x_text, y_text), font, font_scale, text_color, thickness)

        # Draw a persistent box if a click has been made.
        with frame_lock:
            if click_coords is not None:
                x_click, y_click = click_coords
                half_width = 100  # Half of 200px
                half_height = 100
                x1_rect = max(0, x_click - half_width)
                y1_rect = max(0, y_click - half_height)
                x2_rect = min(w, x_click + half_width)
                y2_rect = min(h, y_click + half_height)
                cv2.rectangle(frame, (x1_rect, y1_rect), (x2_rect, y2_rect), box_color, 3)

        # Apply ROI cropping (zoom into the specified region).
        with frame_lock:
            local_roi_x1 = roi_x1
            local_roi_x2 = roi_x2
            local_roi_y1 = roi_y1
            local_roi_y2 = roi_y2
        if 0 <= local_roi_x1 < local_roi_x2 <= w and 0 <= local_roi_y1 < local_roi_y2 <= h:
            roi_frame = frame[local_roi_y1:local_roi_y2, local_roi_x1:local_roi_x2]
            frame = cv2.resize(roi_frame, (w, h))

        # Apply Gaussian blur with the specified parameters.
        with frame_lock:
            local_kernel = gaussian_kernel_size
            local_sigma = gaussian_sigma
        if local_kernel > 1:
            # Ensure kernel size is odd.
            if local_kernel % 2 == 0:
                local_kernel += 1
            frame = cv2.GaussianBlur(frame, (local_kernel, local_kernel), local_sigma)

        # Convert frame to black & white if selected.
        if video_mode == "bw":
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            frame = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

        # Convert the frame from BGR to RGB.
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Encode the frame as JPEG with quality 80.
        ret, buffer = cv2.imencode('.jpg', frame_rgb, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ret:
            continue

        with frame_lock:
            global_frame = buffer.tobytes()

        time.sleep(0.03)  # Adjust delay for desired frame rate

# Start the background thread for capturing frames.
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
    return send_from_directory('.', 'index.html')

@app.route('/video')
def video_feed():
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/click', methods=['POST'])
def click_handler():
    """
    Receives a click coordinate and uses it to update the ROI.
    A fixed half-width and half-height are used to determine the box edges.
    """
    global roi_x1, roi_x2, roi_y1, roi_y2
    data = request.get_json()
    try:
        x = int(data.get('x'))
        y = int(data.get('y'))
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "Invalid coordinates"}), 400

    half_width = 100
    half_height = 100

    # Compute new ROI values with clamping to the nominal frame dimensions.
    with frame_lock:
        roi_x1 = max(0, x - half_width)
        roi_x2 = min(1280, x + half_width)
        roi_y1 = max(0, y - half_height)
        roi_y2 = min(720, y + half_height)
    print(f"ROI updated via click: x1={roi_x1}, x2={roi_x2}, y1={roi_y1}, y2={roi_y2}")
    return jsonify({'status': 'ROI updated', 'x1': roi_x1, 'x2': roi_x2, 'y1': roi_y1, 'y2': roi_y2})

"""def click_handler():
    global click_coords
    data = request.get_json()
    x = data.get('x')
    y = data.get('y')
    with frame_lock:
        click_coords = (x, y)
    print(f"Received click at: {click_coords}")
    return jsonify({'status': 'received', 'x': x, 'y': y})
"""
@app.route('/setcolor', methods=['POST'])
def set_color():
    global box_color, video_mode
    data = request.get_json()
    color_str = data.get("color")
    with frame_lock:
        if color_str == "red":
            box_color = (0, 0, 255)
            video_mode = "color"
        elif color_str == "green":
            box_color = (0, 255, 0)
            video_mode = "color"
        elif color_str == "black&white":
            video_mode = "bw"
        elif color_str == "color":
            video_mode = "color"
    print(f"Command received: {color_str}")
    return jsonify({"status": "received", "color": color_str})

@app.route('/setroi', methods=['POST'])
def set_roi():
    global roi_x1, roi_x2, roi_y1, roi_y2
    data = request.get_json()
    try:
        x1 = int(data.get("x1", 0))
        x2 = int(data.get("x2", 1280))
        y1 = int(data.get("y1", 0))
        y2 = int(data.get("y2", 720))
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "Invalid input types"}), 400

    if 0 <= x1 < x2 <= 1280 and 0 <= y1 < y2 <= 720:
        with frame_lock:
            roi_x1, roi_x2, roi_y1, roi_y2 = x1, x2, y1, y2
        print(f"ROI set to: x1={roi_x1}, x2={roi_x2}, y1={roi_y1}, y2={roi_y2}")
        return jsonify({"status": "ROI updated", "x1": roi_x1, "x2": roi_x2, "y1": roi_y1, "y2": roi_y2})
    else:
        return jsonify({"status": "error", "message": "Invalid ROI values"}), 400

@app.route('/setgaussian', methods=['POST'])
def set_gaussian():
    global gaussian_kernel_size, gaussian_sigma
    data = request.get_json()
    try:
        kernel = int(data.get("kernel", 1))
        sigma = float(data.get("sigma", 0))
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "Invalid input types"}), 400

    if kernel < 1:
        kernel = 1
    with frame_lock:
        gaussian_kernel_size = kernel
        gaussian_sigma = sigma
    print(f"Gaussian settings updated: kernel={gaussian_kernel_size}, sigma={gaussian_sigma}")
    return jsonify({"status": "Gaussian parameters updated", "kernel": gaussian_kernel_size, "sigma": gaussian_sigma})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8485, threaded=True)
