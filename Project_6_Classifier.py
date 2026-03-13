from keras.models import load_model
import numpy as np
from picamera2 import Picamera2
from libcamera import controls
import cv2 as cv
import time
from collections import Counter

model = None
class_names = None
picam2 = None

def setup():
    global model, class_names, picam2

    np.set_printoptions(suppress=True)

    model = load_model("keras_model.h5", compile=False)
    class_names = open("labels.txt", "r").readlines()

    picam2 = Picamera2()
    picam2.set_controls({"AfMode": controls.AfModeEnum.Continuous})
    picam2.start()

    time.sleep(1)

def preprocess_image(image):
    image_resized = cv.resize(image, (224, 224), interpolation=cv.INTER_AREA)
    input_image = cv.cvtColor(image_resized, cv.COLOR_BGR2RGB)
    input_image = np.asarray(input_image, dtype=np.float32).reshape(1, 224, 224, 3)
    input_image = (input_image / 127.5) - 1
    return image_resized, input_image

def predict_once(show_image=False):
    global model, class_names, picam2

    image = picam2.capture_array()
    image_resized, input_image = preprocess_image(image)

    if show_image:
        cv.imshow("PiCam Image", image_resized)
        cv.waitKey(1)

    prediction = model.predict(input_image, verbose=0)
    index = int(np.argmax(prediction))
    class_name = class_names[index].strip()
    confidence_score = float(prediction[0][index])

    return index, class_name, confidence_score

def classify(num_images=3, show_image=False, delay=0.05):
    predictions = []

    for _ in range(num_images):
        index, class_name, confidence_score = predict_once(show_image=show_image)
        predictions.append(index)

        print("Class:", class_name[2:] if len(class_name) > 2 else class_name)
        print("Confidence Score:", round(confidence_score * 100, 2), "%")

        time.sleep(delay)

    most_common_index = Counter(predictions).most_common(1)[0][0]
    return most_common_index

def cleanup():
    global picam2

    if picam2 is not None:
        picam2.stop()
    cv.destroyAllWindows()