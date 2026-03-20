import joblib
import numpy as np

# load model once
model = joblib.load("ml_model/best_model.pkl")

def predict(data):
    data = np.array(data).reshape(1, -1)
    prediction = model.predict(data)
    return prediction[0]