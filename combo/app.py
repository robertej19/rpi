import cv2
import numpy as np
import time
from flask import Response, Flask
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go

# Create a Flask server; Dash will use this under the hood.
server = Flask(__name__)
app = dash.Dash(__name__, server=server)

# Define the two camera URLs.
# (For testing purposes, both feeds are using the same URL. Replace with actual URLs as needed.)
camera_url1 = "http://192.168.1.184:8485/video"
camera_url2 = "http://192.168.1.190:8485/video"

# Open the video capture streams.
cap1 = cv2.VideoCapture(camera_url1)
cap2 = cv2.VideoCapture(camera_url2)
if not cap1.isOpened():
    print(f"Error: Could not open video stream from {camera_url1}")
if not cap2.isOpened():
    print(f"Error: Could not open video stream from {camera_url2}")

# Known ping pong ball diameter (meters) and pixel pitch.
BALL_DIAMETER = 0.04  # 40 mm
PIXEL_PITCH = 0.001   # 1 mrad per pixel

# Global variables to hold the most recent distance estimates (in meters).
global_distance1 = None
global_distance2 = None

def process_frame(frame):
    """
    Process a video frame to detect the ping pong ball (orange object) and
    estimate its distance from the camera. The full frame is used as ROI.
    Returns:
      - Processed frame (with contour and centroid drawn)
      - Centroid coordinates of the largest valid contour
      - Computed distance (in meters) using:
          distance = BALL_DIAMETER / (2 * radius * PIXEL_PITCH)
    """
    h, w = frame.shape[:2]
    roi = frame[0:h, 0:w]  # use the full frame

    # Convert ROI to HSV and create a mask for the orange color.
    roi_hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    lower_orange = np.array([80, 125, 125])
    upper_orange = np.array([180, 250, 250])
    mask = cv2.inRange(roi_hsv, lower_orange, upper_orange)

    # Clean up the mask.
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, kernel, iterations=1)

    # Find contours in the mask.
    contours, _ = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    largest_centroid = None
    distance = None
    largest_area = 0
    chosen_contour = None

    for contour in contours:
        area = cv2.contourArea(contour)
        if area > 1000 and area > largest_area:
            largest_area = area
            chosen_contour = contour

    if chosen_contour is not None:
        (x_center, y_center), radius = cv2.minEnclosingCircle(chosen_contour)
        centroid = (int(x_center), int(y_center))
        largest_centroid = centroid
        cv2.drawContours(frame, [chosen_contour], -1, (0, 255, 0), 2)
        cv2.circle(frame, centroid, 5, (0, 0, 255), -1)
        if radius > 0:
            distance = BALL_DIAMETER / (2 * radius * PIXEL_PITCH)
    return frame, largest_centroid, distance

def generate_frames():
    """
    Generator function to read from both camera streams, process the frames,
    overlay text info (centroid and distance) on each feed, and combine them
    side-by-side into a single frame. It also updates global distance variables.
    """
    global global_distance1, global_distance2
    while True:
        ret1, frame1 = cap1.read()
        ret2, frame2 = cap2.read()
        if not ret1 or not ret2:
            # If a frame isn't read successfully, skip this iteration.
            continue

        # Resize frames for consistent display (fix the height to 480 pixels).
        desired_height = 480
        scale1 = desired_height / frame1.shape[0]
        scale2 = desired_height / frame2.shape[0]
        frame1 = cv2.resize(frame1, (int(frame1.shape[1] * scale1), desired_height))
        frame2 = cv2.resize(frame2, (int(frame2.shape[1] * scale2), desired_height))

        # Process each frame.
        processed_frame1, centroid1, distance1 = process_frame(frame1)
        processed_frame2, centroid2, distance2 = process_frame(frame2)

        # Overlay text on feed 1.
        if centroid1 is not None and distance1 is not None:
            text1 = f"Feed1: {centroid1} | Dist: {distance1:.2f} m"
            cv2.putText(processed_frame1, text1, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        1, (0, 0, 255), 2)
        else:
            cv2.putText(processed_frame1, "Feed1: No Ball Found", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        # Overlay text on feed 2.
        if centroid2 is not None and distance2 is not None:
            text2 = f"Feed2: {centroid2} | Dist: {distance2:.2f} m"
            cv2.putText(processed_frame2, text2, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        1, (0, 0, 255), 2)
        else:
            cv2.putText(processed_frame2, "Feed2: No Ball Found", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        # Update global distance values.
        global_distance1 = distance1
        global_distance2 = distance2

        # Combine the two feeds side by side.
        combined_frame = np.hstack((processed_frame1, processed_frame2))

        ret, buffer = cv2.imencode('.jpg', combined_frame)
        if not ret:
            continue
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

# Expose the video feed via Flask.
@server.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# -----------------------------
# Dash Layout and Callback
# -----------------------------
app.layout = html.Div([
    html.H1("Ping Pong Ball Detection and Spatial Localization"),
    html.Div([
        html.H3("Live Video Feed"),
        html.Img(src="/video_feed", style={'width': '100%', 'maxWidth': '1200px'})
    ]),
    html.Hr(),
    html.Div([
        html.H3("Camera Setup Spatial Plot"),
        dcc.Graph(id="spatial-plot"),
        dcc.Interval(id="interval-component", interval=100, n_intervals=0)
    ])
])

@app.callback(
    Output("spatial-plot", "figure"),
    Input("interval-component", "n_intervals")
)
def update_spatial_plot(n):
    """
    Creates a Plotly figure showing:
      - Camera 1 (blue square) at (0,0)
      - Camera 2 (red square) at (100,0)
      - For Camera 1: if a ball is detected, its estimated position is (distance1*100, 0)
      - For Camera 2: if a ball is detected, its estimated position is (100 - distance2*100, 0)
    All positions are in centimeters.
    """
    d1 = global_distance1  # in meters
    d2 = global_distance2  # in meters

    # Compute ball positions in cm.
    ball1_x = d1 * 100 if d1 is not None else None
    ball2_x = 50 - (d2 * 100) if d2 is not None else None

    data = []
    # Camera positions.
    data.append(go.Scatter(x=[0], y=[0], mode="markers", marker=dict(color="blue", symbol="square", size=16), name="Cam1"))
    data.append(go.Scatter(x=[50], y=[0], mode="markers", marker=dict(color="red", symbol="square", size=16), name="Cam2"))
    # Ball positions.
    if ball1_x is not None:
        data.append(go.Scatter(x=[ball1_x], y=[0], mode="markers+text", marker=dict(color="blue", size=16),
                               text=[f"{ball1_x:.1f} cm"], textposition="top center", name="Ball Cam1"))
    else:
        data.append(go.Scatter(x=[0], y=[5], mode="text", text=["Cam1: No ball"], name="Ball Cam1"))
    if ball2_x is not None:
        data.append(go.Scatter(x=[ball2_x], y=[0], mode="markers+text", marker=dict(color="red", size=16),
                               text=[f"{ball2_x:.1f} cm"], textposition="top center", name="Ball Cam2"))
    else:
        data.append(go.Scatter(x=[50], y=[5], mode="text", text=["Cam2: No ball"], name="Ball Cam2"))

    layout = go.Layout(
        xaxis=dict(range=[-10, 60], title="X Position (cm)"),
        yaxis=dict(range=[-10, 10], title="Y Position (cm)"),
        title="Camera Setup and Estimated Ball Position",
        showlegend=False
    )
    fig = go.Figure(data=data, layout=layout)
    return fig

if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=5000)
