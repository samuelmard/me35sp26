# Authors: Caroline Carr, Sam Mard
# PID control of dual DC motors based on IR sensor readings

import RPi.GPIO as GPIO
import time

# --- Pin Configuration ---
ena, in1, in2 = 24, 26, 32
enb, in3, in4 = 31, 29, 23
SensorLL, SensorL, SensorM, SensorR, SensorRR = 8, 10, 12, 16, 18

# --- GPIO Setup ---
GPIO.setmode(GPIO.BOARD)
GPIO.setup([ena, in1, in2, enb, in3, in4], GPIO.OUT)
GPIO.setup([SensorLL, SensorL, SensorM, SensorR, SensorRR], GPIO.IN)

motorL = GPIO.PWM(ena, 100)
motorR = GPIO.PWM(enb, 100)
motorL.start(0)
motorR.start(0)

# PID Constants
Kp = 15.0  # Proportional
Ki = 0.01  # Integral
Kd = 8.0   # Derivative

base_speed = 20
last_error = 0
integral = 0

def set_motors(speed_l, speed_r):
    # Left Motor
    GPIO.output(in1, GPIO.HIGH if speed_l >= 0 else GPIO.LOW)
    GPIO.output(in2, GPIO.LOW if speed_l >= 0 else GPIO.HIGH)
    # Right Motor
    GPIO.output(in3, GPIO.HIGH if speed_r >= 0 else GPIO.LOW)
    GPIO.output(in4, GPIO.LOW if speed_r >= 0 else GPIO.HIGH)
    
    # Constrain speeds to 0-100 range
    motorL.ChangeDutyCycle(max(0, min(abs(speed_l), 100)))
    motorR.ChangeDutyCycle(max(0, min(abs(speed_r), 100)))

def get_error():
    """Assigns weights to sensors: LL=-2, L=-1, M=0, R=1, RR=2"""
    ll, l, m, r, rr = [GPIO.input(s) for s in [SensorLL, SensorL, SensorM, SensorR, SensorRR]]
    
    # If no line is seen, use the last error to stay in a turn
    if not any([ll, l, m, r, rr]):
        return "LOST"
        
    # Weighted average logic
    error = (ll * -2) + (l * -1) + (m * 0) + (r * 1) + (rr * 2)
    return error

try:
    while True:
        error = get_error()
        
        if error == "LOST":
            # If lost, keep last_error to spin in place or stop
            error = last_error 
        
        # PID Calculation
        integral += error
        derivative = error - last_error
        
        correction = (Kp * error) + (Ki * integral) + (Kd * derivative)
        
        # Apply correction to base speed
        # For a right error (positive), speed up left motor and slow down right
        speed_l = base_speed + correction
        speed_r = base_speed - correction
        
        set_motors(speed_l, speed_r)
        
        last_error = error
        time.sleep(0.01)

except KeyboardInterrupt:
    motorL.stop()
    motorR.stop()
    GPIO.cleanup()