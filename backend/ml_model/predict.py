import joblib
import numpy as np
import os

# load model once
BASE_DIR = os.path.dirname(__file__)
model_path = os.path.join(BASE_DIR, "best_model.pkl")

model = joblib.load(model_path)

def predict(data):
    data = np.array(data).reshape(1, -1)
    prediction = model.predict(data)
    return prediction[0]