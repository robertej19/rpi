from picamera2 import Picamera2
import cv2

# Initialize Picamera2 and start the camera
picam2 = Picamera2()
picam2.start()

# Capture a single frame as a NumPy array
frame = picam2.capture_array()

# Define text parameters
text = "frame 1"
position = (50, 50)               # Coordinates where the text will be placed
font = cv2.FONT_HERSHEY_SIMPLEX   # Font type
font_scale = 1                    # Font scale (size)
color = (0, 0, 255)               # Red color in BGR format
thickness = 2                     # Thickness of the text stroke

# Put the text onto the frame
cv2.putText(frame, text, position, font, font_scale, color, thickness)

# Display the frame with the text
cv2.imshow("Frame", frame)
cv2.waitKey(0)  # Wait for a key press to close the window

# Cleanup
cv2.destroyAllWindows()
picam2.close()
