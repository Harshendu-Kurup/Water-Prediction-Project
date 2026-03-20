import { useState } from "react";

function Prediction() {
  const [prediction, setPrediction] = useState("");
  const [loading, setLoading] = useState(false);

  const getPrediction = async () => {
    setLoading(true);

    try {
      const response = await fetch("http://127.0.0.1:8000/predict", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
        features: [
        Math.random() * 120,  // random distance
        20 + Math.random() * 10  // random temp
         ]
        }),
      });

      const data = await response.json();
      setPrediction(data.prediction);
    } catch (error) {
      console.error(error);
    }

    setLoading(false);
  };

  return (
    <div style={{ padding: "20px" }}>
      <h2>Prediction Page</h2>

      <button onClick={getPrediction}>
        Get Prediction
      </button>

      {loading && <p>Loading...</p>}

      {prediction && (
        <h3>Prediction: {prediction}</h3>
      )}
    </div>
  );
}

export default Prediction;