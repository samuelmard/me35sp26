# Author: Sam Mard
# Attributions: Used Google Gemini & official python documentation to help
# w/ implementing dictionary datatype to match colors to rgb values, as well
# as fixing the motor stepping process

import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BOARD)

# Assign GPIO pin numbers to variables

s0 = 13
s1 = 15
s2 = 16
s3 = 18
sig = 22 #labeled "out" on your board
cycles = 10

# Define the GPIO pins for the first L298N motor driver
OUT1 = 36
OUT2 = 35
OUT3 = 38
OUT4 = 37

# Define the GPIO pins for the Second L298N motor driver
OUT5 = 21
OUT6 = 23
OUT7 = 24
OUT8 = 26

# Set the GPIO pins as output
GPIO.setup(OUT1, GPIO.OUT)
GPIO.setup(OUT2, GPIO.OUT)
GPIO.setup(OUT3, GPIO.OUT)
GPIO.setup(OUT4, GPIO.OUT)
GPIO.setup(OUT5, GPIO.OUT)
GPIO.setup(OUT6, GPIO.OUT)
GPIO.setup(OUT7, GPIO.OUT)
GPIO.setup(OUT8, GPIO.OUT)

# Set initial state of pins to low
GPIO.output(OUT1,GPIO.LOW)
GPIO.output(OUT2,GPIO.LOW)
GPIO.output(OUT3,GPIO.LOW)
GPIO.output(OUT4,GPIO.LOW)
GPIO.output(OUT5,GPIO.LOW)
GPIO.output(OUT6,GPIO.LOW)
GPIO.output(OUT7,GPIO.LOW)
GPIO.output(OUT8,GPIO.LOW)

# Setup GPIO and pins
GPIO.setmode(GPIO.BOARD)
GPIO.setup(s0, GPIO.OUT)
GPIO.setup(s1, GPIO.OUT)
GPIO.setup(s2, GPIO.OUT)
GPIO.setup(s3, GPIO.OUT)
GPIO.setup(sig, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# Set frequency scaling
GPIO.output(s0, GPIO.HIGH)
GPIO.output(s1, GPIO.LOW)

step_delay = 0.01
color_positions = {
    "red": 0,
    "green": 50,
    "blue": 100,
    "yellow": 150
}

# Initialize global tracking variables to keep phases in sync
ramp_current_phase = 0
sorting_current_phase = 0

def MoveSortingMotor(direction):
    global sorting_current_phase # Access the global tracker
    num_steps = 50
    
    for x in range(num_steps):
        if sorting_current_phase == 0:
            GPIO.output(OUT5,GPIO.HIGH); GPIO.output(OUT6,GPIO.LOW)
            GPIO.output(OUT7,GPIO.HIGH); GPIO.output(OUT8,GPIO.LOW)
        elif sorting_current_phase == 1:
            GPIO.output(OUT5,GPIO.LOW);  GPIO.output(OUT6,GPIO.HIGH)
            GPIO.output(OUT7,GPIO.HIGH); GPIO.output(OUT8,GPIO.LOW)
        elif sorting_current_phase == 2:
            GPIO.output(OUT5,GPIO.LOW);  GPIO.output(OUT6,GPIO.HIGH)
            GPIO.output(OUT7,GPIO.LOW);  GPIO.output(OUT8,GPIO.HIGH)
        elif sorting_current_phase == 3:
            GPIO.output(OUT5,GPIO.HIGH); GPIO.output(OUT6,GPIO.LOW)
            GPIO.output(OUT7,GPIO.LOW);  GPIO.output(OUT8,GPIO.HIGH)

        time.sleep(step_delay)
        
        # Update the global tracker instead of a local one
        if direction == 1: # Forward
            sorting_current_phase = (sorting_current_phase + 1) % 4
        else: # Backward
            sorting_current_phase = (sorting_current_phase - 1) % 4

    # Keep coils off when not moving to prevent heat, 
    # but the phase is saved in sorting_current_phase
    for pin in [OUT5, OUT6, OUT7, OUT8]:
        GPIO.output(pin, GPIO.LOW)

def MoveRampMotor(num_steps, direction):
    global ramp_current_phase # Access the global tracker
    
    for x in range(num_steps):
        if ramp_current_phase == 0:
            GPIO.output(OUT1,GPIO.HIGH); GPIO.output(OUT2,GPIO.LOW)
            GPIO.output(OUT3,GPIO.HIGH); GPIO.output(OUT4,GPIO.LOW)
        elif ramp_current_phase == 1:
            GPIO.output(OUT1,GPIO.LOW);  GPIO.output(OUT2,GPIO.HIGH)
            GPIO.output(OUT3,GPIO.HIGH); GPIO.output(OUT4,GPIO.LOW)
        elif ramp_current_phase == 2:
            GPIO.output(OUT1,GPIO.LOW);  GPIO.output(OUT2,GPIO.HIGH)
            GPIO.output(OUT3,GPIO.LOW);  GPIO.output(OUT4,GPIO.HIGH)
        elif ramp_current_phase == 3:
            GPIO.output(OUT1,GPIO.HIGH); GPIO.output(OUT2,GPIO.LOW)
            GPIO.output(OUT3,GPIO.LOW);  GPIO.output(OUT4,GPIO.HIGH)

        time.sleep(step_delay)
        
        if direction == 1:
            ramp_current_phase = (ramp_current_phase + 1) % 4
        else:
            ramp_current_phase = (ramp_current_phase - 1) % 4

    for pin in [OUT1, OUT2, OUT3, OUT4]:
        GPIO.output(pin, GPIO.LOW)

# Returns the average frequency of each color
def GetAvgFreq(s2_val, s3_val):
    GPIO.output(s2, s2_val)
    GPIO.output(s3, s3_val)
    time.sleep(0.05)
    total_freq = 0

    for _ in range(10):
        start_time = time.time()
        for count in range(cycles):
            GPIO.wait_for_edge(sig, GPIO.FALLING)
        duration = time.time() - start_time
        total_freq += (cycles/duration) # Sum Recorded Frequencies
    
    avg_freq = total_freq / 10 # Take Average Frequency
    return avg_freq

# Returns a dictionary of color and rbg value pairs by calling GetAvgFreq
# for each color
def Calibrate():
    ball_colors = {} # Dictionary for colors & corresponding rgb values
    colors = ["red", "green", "blue", "yellow"]

    print("Beginning Calibration: ")
    MoveSortingMotor(-1)

    for color in colors:
        input(f"Place the {color} colored ball in front of the sensor and press 'Enter'")

        # Setting which filter to use
        r = GetAvgFreq(GPIO.LOW, GPIO.LOW)
        g = GetAvgFreq(GPIO.HIGH, GPIO.HIGH)
        b = GetAvgFreq(GPIO.LOW, GPIO.HIGH)

        ball_colors[color] = (r,g,b) # Saves rgb values for each color

        steps_needed = color_positions[color]
        MoveRampMotor(steps_needed, direction=1)

        time.sleep(1)

        MoveSortingMotor(-1)
            
        # Wait for ball to roll off
        time.sleep(1)
            
        # Return to neutral
        MoveRampMotor(steps_needed, direction=-1)

        time.sleep(1)

        print(f"Saved {color}: R{int(r)} G{int(g)} B{int(b)}")
    return ball_colors

try:

    targets = Calibrate() # targets holds calibrated values
    print(f"Calibration Complete!")
    time.sleep(3)

    while True:
        r = GetAvgFreq(GPIO.LOW, GPIO.LOW)
        g = GetAvgFreq(GPIO.HIGH, GPIO.HIGH)
        b = GetAvgFreq(GPIO.LOW, GPIO.HIGH)

        best_match = "" # blank if there is no match
        min_dist = 999999 # very large so caluclated distances are always less

        for ball_colors, (tr, tg, tb) in targets.items():
            dist = ((r-tr)**2 + (g-tg)**2 + (b-tb)**2)**0.5 # distance formula
            if dist < min_dist:
                min_dist = dist # closest distance
                best_match = ball_colors # corresponding color

        print(best_match)

        # Move to the bin
        steps_needed = color_positions[best_match]
        MoveRampMotor(steps_needed, direction=1)

        time.sleep(1)

        MoveSortingMotor(-1)
            
        # Wait for ball to roll off
        time.sleep(3)
            
        # Return to neutral
        MoveRampMotor(steps_needed, direction=-1)

        time.sleep(1)

except KeyboardInterrupt:
    print("\nExiting Program")
finally:
    GPIO.cleanup()