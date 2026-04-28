import cv2
import numpy as np
import time
import RPi.GPIO as GPIO
from picamera2 import Picamera2
from libcamera import controls

# Existing green output
OUTPUT_PIN = 40

# Blue output
BLUE_OUTPUT_PIN = 35

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)
GPIO.setup(OUTPUT_PIN, GPIO.OUT)
GPIO.setup(BLUE_OUTPUT_PIN, GPIO.OUT)
GPIO.output(OUTPUT_PIN, GPIO.LOW)
GPIO.output(BLUE_OUTPUT_PIN, GPIO.LOW)

picam2 = Picamera2()
config = picam2.create_preview_configuration(
    main={"size": (640, 480), "format": "RGB888"}
)
picam2.configure(config)
picam2.set_controls({"AfMode": controls.AfModeEnum.Continuous})
picam2.start()
time.sleep(0.5)

frame_width = 640
frame_height = 480

# Green trigger line (vertical)
trigger_x = 542

# Blue trigger line (horizontal)
trigger_y = 90

min_green_contour_area = 500
min_blue_contour_area = 500

# ---- GREEN HSV RANGE ----
lower_neon_green = np.array([60, 60, 100])
upper_neon_green = np.array([87, 255, 255])

# ---- LIGHT BLUE HSV RANGE ----
lower_light_blue = np.array([85, 150, 150])
upper_light_blue = np.array([115, 255, 255])

last_green_pin_state = GPIO.LOW
last_blue_pin_state = GPIO.LOW

try:
    while True:
        frame = picam2.capture_array()
        frame = cv2.flip(frame, -1)

        blur = cv2.GaussianBlur(frame, (5, 5), 0)
        hsv = cv2.cvtColor(blur, cv2.COLOR_BGR2HSV)

        green_mask = cv2.inRange(hsv, lower_neon_green, upper_neon_green)
        blue_mask = cv2.inRange(hsv, lower_light_blue, upper_light_blue)

        kernel = np.ones((5, 5), np.uint8)
        green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_OPEN, kernel)
        green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_CLOSE, kernel)

        blue_mask = cv2.morphologyEx(blue_mask, cv2.MORPH_OPEN, kernel)
        blue_mask = cv2.morphologyEx(blue_mask, cv2.MORPH_CLOSE, kernel)

        green_contours, _ = cv2.findContours(
            green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        blue_contours, _ = cv2.findContours(
            blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        display = frame.copy()

        cv2.line(display, (trigger_x, 0), (trigger_x, frame_height), (255, 0, 0), 2)
        cv2.putText(display, "Green trigger line", (trigger_x - 170, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

        cv2.line(display, (0, trigger_y), (frame_width, trigger_y), (255, 255, 0), 2)
        cv2.putText(display, "Blue height trigger", (20, trigger_y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

        green_target_here = False
        blue_target_here = False

        # GREEN DETECTION
        if green_contours:
            c_green = max(green_contours, key=cv2.contourArea)
            green_area = cv2.contourArea(c_green)

            if green_area > min_green_contour_area:
                cv2.drawContours(display, [c_green], -1, (0, 255, 0), 3)

                xg, yg, wg, hg = cv2.boundingRect(c_green)
                cv2.rectangle(display, (xg, yg), (xg + wg, yg + hg), (0, 255, 255), 2)

                Mg = cv2.moments(c_green)
                if Mg["m00"] != 0:
                    green_cx = int(Mg["m10"] / Mg["m00"])
                    green_cy = int(Mg["m01"] / Mg["m00"])

                    cv2.circle(display, (green_cx, green_cy), 6, (255, 255, 255), -1)
                    cv2.putText(display, f"Green centroid: ({green_cx},{green_cy})",
                                (xg, yg - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

                    green_h, green_s, green_v = hsv[green_cy, green_cx]
                    cv2.putText(display,
                                f"G HSV: ({int(green_h)},{int(green_s)},{int(green_v)})",
                                (xg, yg + hg + 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)

                    if green_cx <= trigger_x:
                        green_target_here = True

        # BLUE DETECTION
        if blue_contours:
            c_blue = max(blue_contours, key=cv2.contourArea)
            blue_area = cv2.contourArea(c_blue)

            if blue_area > min_blue_contour_area:
                cv2.drawContours(display, [c_blue], -1, (255, 200, 0), 3)

                xb, yb, wb, hb = cv2.boundingRect(c_blue)
                cv2.rectangle(display, (xb, yb), (xb + wb, yb + hb), (255, 0, 255), 2)

                Mb = cv2.moments(c_blue)
                if Mb["m00"] != 0:
                    blue_cx = int(Mb["m10"] / Mb["m00"])
                    blue_cy = int(Mb["m01"] / Mb["m00"])

                    cv2.circle(display, (blue_cx, blue_cy), 6, (255, 255, 0), -1)
                    cv2.putText(display, f"Blue centroid: ({blue_cx},{blue_cy})",
                                (xb, yb - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

                    blue_h, blue_s, blue_v = hsv[blue_cy, blue_cx]
                    cv2.putText(display,
                                f"B HSV: ({int(blue_h)},{int(blue_s)},{int(blue_v)})",
                                (xb, yb + hb + 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 2)

                    print(
                        f"BLUE centroid ({blue_cx},{blue_cy}) | "
                        f"HSV=({int(blue_h)},{int(blue_s)},{int(blue_v)})"
                    )

                    # Blue trigger now uses centroid crossing the line
                    if blue_cy >= trigger_y:
                        blue_target_here = True

        # Existing green output behavior
        GPIO.output(OUTPUT_PIN, GPIO.HIGH if green_target_here else GPIO.LOW)

        # Blue output behavior
        GPIO.output(BLUE_OUTPUT_PIN, GPIO.HIGH if blue_target_here else GPIO.LOW)

        new_green_pin_state = GPIO.HIGH if green_target_here else GPIO.LOW
        new_blue_pin_state = GPIO.HIGH if blue_target_here else GPIO.LOW

        if green_target_here:
            cv2.putText(display, "GREEN TARGET HERE", (40, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 3)

        if blue_target_here:
            cv2.putText(display, "BLUE HEIGHT TRIGGERED", (40, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 0), 3)

        if new_green_pin_state != last_green_pin_state:
            print(f"GREEN PIN {OUTPUT_PIN} -> {'HIGH' if new_green_pin_state else 'LOW'}")
            last_green_pin_state = new_green_pin_state

        if new_blue_pin_state != last_blue_pin_state:
            print(f"BLUE PIN {BLUE_OUTPUT_PIN} -> {'HIGH' if new_blue_pin_state else 'LOW'}")
            last_blue_pin_state = new_blue_pin_state

        cv2.imshow("Plate Detection", display)
        cv2.imshow("Green Mask", green_mask)
        cv2.imshow("Blue Mask", blue_mask)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break

except KeyboardInterrupt:
    pass

finally:
    GPIO.output(OUTPUT_PIN, GPIO.LOW)
    GPIO.output(BLUE_OUTPUT_PIN, GPIO.LOW)
    GPIO.cleanup()
    cv2.destroyAllWindows()