import RPi.GPIO as GPIO
import time
import airtable_module as airtable

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)

# pins
Knife_PINS = [36, 40, 38, 37]
Pusher_PINS = [10, 7, 12, 8]
SECOND_CONVEYOR_PINS = [18, 15, 19, 16]
SERVO_PIN = 3

# Existing green trigger input from camera Pi
TRIGGER_PIN = 11

# Blue trigger input from camera Pi
BLUE_TRIGGER_PIN = 31

# --- Pin Configuration ---
SensorM = 35
GPIO.setup([SensorM], GPIO.IN)

GPIO.setup(TRIGGER_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(BLUE_TRIGGER_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

STEP_SEQ = [
    [1, 0, 0, 0],
    [1, 1, 0, 0],
    [0, 1, 0, 0],
    [0, 1, 1, 0],
    [0, 0, 1, 0],
    [0, 0, 1, 1],
    [0, 0, 0, 1],
    [1, 0, 0, 1],
]

for pin in Knife_PINS + Pusher_PINS + SECOND_CONVEYOR_PINS:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, 0)

GPIO.setup(SERVO_PIN, GPIO.OUT)
pwm = GPIO.PWM(SERVO_PIN, 50)
pwm.start(0)

def print_switches(label=""):
    green = GPIO.input(TRIGGER_PIN)
    blue = GPIO.input(BLUE_TRIGGER_PIN)
    print(f"{label} GREEN={green} BLUE={blue}")

SERVO_DOWN = 90
SERVO_UP = 15

def SetAngle(angle):
    duty = 2.5 + (angle / 180.0) * 10.0
    pwm.ChangeDutyCycle(duty)
    time.sleep(0.35)
    pwm.ChangeDutyCycle(0)

STEP_DELAY_1 = 0.004
STEP_DELAY_2 = 0.02
STEP_DELAY_3 = 0.02

def stepper_run(pins, steps, delay, forward=True, label="stepper"):
    seq = STEP_SEQ if forward else list(reversed(STEP_SEQ))

    for i in range(steps):
        pattern = seq[i % 8]

        for pin, val in zip(pins, pattern):
            GPIO.output(pin, val)

        time.sleep(delay)

    for pin in pins:
        GPIO.output(pin, 0)

current_pos = 0
closed_pos = -1520
open_pos = 0

def move_knife(target):
    global current_pos
    steps_to_move = target - current_pos

    print(f"move_knife: current={current_pos}, target={target}, delta={steps_to_move}")

    if steps_to_move != 0:
        stepper_run(
            Knife_PINS,
            abs(steps_to_move),
            STEP_DELAY_1,
            forward=(steps_to_move > 0),
            label="knife"
        )
        current_pos = target
        print(f"knife moved to {current_pos}")
        time.sleep(0.1)
    else:
        print("knife already at target")

def move_knife_down_until_blue_trigger(max_steps=3200, chunk_steps=8):
    global current_pos

    print("move_knife_down_until_blue_trigger: starting")
    moved = 0

    while moved < max_steps:
        if GPIO.input(BLUE_TRIGGER_PIN) == 1:
            print(f"Blue trigger seen at knife position {current_pos}")
            return True

        stepper_run(
            Knife_PINS,
            chunk_steps,
            STEP_DELAY_1,
            forward=False,
            label="knife_down_search"
        )

        current_pos -= chunk_steps
        moved += chunk_steps

        if moved % 40 == 0:
            print(
                f"Knife moving down... moved={moved}, "
                f"current_pos={current_pos}, "
                f"blue_trigger={GPIO.input(BLUE_TRIGGER_PIN)}"
            )

    print("WARNING: max_steps reached before blue trigger")
    return False

def knife_cut_once():
    global current_pos
    print("knife_cut_once: DOWN")
    move_knife(closed_pos)
    time.sleep(0.4)

    print("knife_cut_once: UP")
    stepper_run(Knife_PINS, 1520, STEP_DELAY_1, forward=True, label="knife_up")
    current_pos = open_pos
    time.sleep(0.4)

def first_conveyor():
    global current_pos
    print("=== first_conveyor start ===")
    print_switches("At start:")

    SetAngle(SERVO_DOWN)

    timeout = time.time() + 10
    loop_count = 0

    print("Starting pusher homing toward green trigger")

    while True:
        loop_count += 1
        print(f"{GPIO.input(TRIGGER_PIN)}")

        if time.time() > timeout:
            raise RuntimeError("Timeout waiting for green trigger")

        if loop_count % 20 == 1:
            print_switches(f"Homing loop {loop_count}:")

        stepper_run(Pusher_PINS, 8, STEP_DELAY_2, forward=False, label="stepper")

        if GPIO.input(TRIGGER_PIN) == 1:
            print("done")
            break

    print_switches("After hit:")
    print("Green trigger activated")
    stepper_run(Pusher_PINS, 20 * 2, STEP_DELAY_2, forward=True, label="stepper")

    time.sleep(0.2)

    if not move_knife_down_until_blue_trigger():
        raise RuntimeError("Blue trigger not received")

    time.sleep(0.5)

    print("Servo kick")
    SetAngle(SERVO_UP)
    time.sleep(0.5)
    SetAngle(SERVO_DOWN)
    time.sleep(1)
    print("Servo kicked")

    stepper_run(Knife_PINS, 1520, STEP_DELAY_1, forward=True, label="knife_up")
    current_pos = open_pos
    time.sleep(0.5)

    print("Servo kick")
    SetAngle(SERVO_UP)
    time.sleep(0.5)
    SetAngle(SERVO_DOWN)
    time.sleep(1)
    print("Servo kicked")

    print("Servo kick")
    SetAngle(SERVO_UP)
    time.sleep(0.2)
    SetAngle(SERVO_DOWN)
    time.sleep(0.2)
    print("Servo kicked")

    print("Servo kick")
    SetAngle(SERVO_UP)
    time.sleep(0.2)
    SetAngle(SERVO_DOWN)
    time.sleep(0.2)
    print("Servo kicked")

    time.sleep(0.25)
    print("=== first_conveyor end ===")

CutThickness = 9 * 2
NumCuts = 5
StartPushSteps = 32 * 2
More = 5
Backwards = StartPushSteps + CutThickness * (NumCuts - 1) + CutThickness + More

def second_conveyor():
    global current_pos
    print("=== second_conveyor start ===")

    stepper_run(SECOND_CONVEYOR_PINS, StartPushSteps, STEP_DELAY_3, forward=True, label="stepper2")

    for i in range(NumCuts - 1):
        stepper_run(SECOND_CONVEYOR_PINS, CutThickness, STEP_DELAY_3, forward=True, label="stepper2")
        time.sleep(1)

        if not move_knife_down_until_blue_trigger():
            raise RuntimeError(f"Blue trigger not received during second conveyor cut {i + 1}")

        time.sleep(0.5)

        stepper_run(Knife_PINS, 1520, STEP_DELAY_1, forward=True, label="knife_up")
        current_pos = open_pos
        time.sleep(0.5)
        print(f"second round {i + 1}")

    stepper_run(SECOND_CONVEYOR_PINS, CutThickness + More, STEP_DELAY_3, forward=True, label="stepper2")
    time.sleep(1)
    stepper_run(SECOND_CONVEYOR_PINS, Backwards, STEP_DELAY_3, forward=False, label="stepper2")

    print("=== second_conveyor end ===")

try:
    print("Program start")
    print_switches("Startup:")

    airtable.update_status("strawberry", "ready")

    while True:
        print("Waiting for strawberry ready...")
        airtable.update_status("strawberry", "ready")
        airtable.wait_until_ready("strawberry")
        print("Strawberry request received. Starting robot...")

        airtable.update_status("strawberry", "executing")

        try:
            first_conveyor()
            print("First conveyor complete. Starting second conveyor...")

            second_conveyor()
            print("Second conveyor complete.")

            airtable.update_status("strawberry", "success")
            time.sleep(1)

        except Exception as e:
            print(f"Error during strawberry cycle: {e}")
            airtable.update_status("strawberry", "failure")
            time.sleep(1)
            break

except KeyboardInterrupt:
    print("\nKeyboard Interrupt")

finally:
    print("Cleaning up GPIO")
    pwm.stop()
    for pin in Knife_PINS + Pusher_PINS + SECOND_CONVEYOR_PINS:
        GPIO.output(pin, 0)
    GPIO.cleanup()