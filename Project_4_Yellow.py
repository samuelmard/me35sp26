# Authors: Sam Mard, Owen Pallatroni
# Attributions: Used Gemini and Claude to help implement camera functionality

import numpy as np
import cv2
from picamera2 import Picamera2
import RPi.GPIO as GPIO
import time

# GPIO Setup
ena, in1, in2 = 25, 8, 7
enb, in3, in4 = 18, 14, 15

GPIO.setmode(GPIO.BCM)
GPIO.setup([ena, in1, in2, enb, in3, in4], GPIO.OUT)

motorL = GPIO.PWM(ena, 500)
motorR = GPIO.PWM(enb, 500)
motorL.start(0)
motorR.start(0)

def set_motors(left_speed, right_speed):
    # Left motor
    if left_speed >= 0:
        GPIO.output(in1, GPIO.HIGH); GPIO.output(in2, GPIO.LOW)
    else:
        GPIO.output(in1, GPIO.LOW); GPIO.output(in2, GPIO.HIGH)
    motorL.ChangeDutyCycle(min(abs(left_speed), 100))

    # Right motor 
    if right_speed >= 0:
        GPIO.output(in3, GPIO.LOW); GPIO.output(in4, GPIO.HIGH)
    else:
        GPIO.output(in3, GPIO.HIGH); GPIO.output(in4, GPIO.LOW)
    motorR.ChangeDutyCycle(min(abs(right_speed), 100))

# Camera Setup
picam2 = Picamera2()
config = picam2.create_preview_configuration(main={"size": (640, 480)})
picam2.configure(config)
picam2.start()
time.sleep(1)

# Color HSV value calibration
lower_color = np.array([15, 110, 90])
upper_color = np.array([105, 255, 255])

lower_orange = np.array([10, 150, 150])
upper_orange = np.array([25, 255, 255])

# Tuning Parameters
BASE_SPEED = 40    # Minimum reliable speed above stall threshold
KP = 0.1          # Proportional gain — how hard it corrects based on error size
KD = 0.06        # Derivative gain — how hard it corrects based on how fast error changes
MAX_SPEED = 60     # Allows fast wheel to speed up enough to steer quickly
SPIN_SPEED = 35    # Search spin speed — keep close to BASE_SPEED
FRAME_CENTER = 320 # Horizontal center of 640px frame

last_error = 0

# Opening Display window
USE_DISPLAY = True
try:
    test = np.zeros((10, 10), dtype=np.uint8)
    cv2.imshow('test', test)
    cv2.waitKey(1)
    cv2.destroyAllWindows()
except Exception:
    USE_DISPLAY = False
    print("No display detected — running headless. Terminal output only.")

print("Green line follower started. Press Ctrl+C to stop.")

try:
    while True:
        image = picam2.capture_array("main")

        # Crop to front-facing portion of frame
        crop_img = image[0:240, 0:640]

        hsv = cv2.cvtColor(crop_img, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, lower_color, upper_color)

        orange_mask = cv2.inRange(hsv, lower_orange, upper_orange)
        orange_detected = cv2.countNonZero(orange_mask) > 500

        if orange_detected:
            set_motors(BASE_SPEED, BASE_SPEED)
            print("Orange intersection — driving straight through...")
            time.sleep(0.4)
            continue

        M = cv2.moments(mask)

        if M['m00'] > 0:
            # Line found: steer toward it using PD control
            cx = int(M['m10'] / M['m00'])
            error = cx - FRAME_CENTER        # Negative = line left, Positive = line right
            derivative = error - last_error  # Rate of change of error
            last_error = error

            left_speed  = BASE_SPEED - (error * KP) - (derivative * KD)
            right_speed = BASE_SPEED + (error * KP) + (derivative * KD)

            # Clamp to speed range — floor at 0 so wheels never reverse during correction
            left_speed  = max(0, min(MAX_SPEED, left_speed))
            right_speed = max(0, min(MAX_SPEED, right_speed))

            set_motors(left_speed, right_speed)
            print(f"Following | cx: {cx} | error: {error:+d} | deriv: {derivative:+d} | L: {left_speed:.1f} R: {right_speed:.1f}")

        else:
            # Line lost: turn right to catch the acute-angle green turn
            set_motors(SPIN_SPEED, SPIN_SPEED)   # Left wheel forward, right wheel back = turn right
            last_error = 0
            print("Line lost — turning right to search...")

        if USE_DISPLAY:
            cv2.imshow('Green Line Mask', mask)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        

except KeyboardInterrupt:
    print("Stopped by user.")

finally:
    set_motors(0, 0)
    motorL.stop()
    motorR.stop()
    GPIO.cleanup()
    if USE_DISPLAY:
        cv2.destroyAllWindows()
    picam2.stop()
    print("Cleaned up.")