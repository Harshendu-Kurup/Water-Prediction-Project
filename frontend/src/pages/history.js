import { useEffect, useState } from "react";

function history() {
  const [data, setData] = useState([]);

  useEffect(() => {
    fetch("http://127.0.0.1:8000/prediction-history")
      .then(res => res.json())
      .then(data => setData(data));
  }, []);

  return (
    <div style={{ padding: "20px" }}>
      <h2>Prediction History</h2>

      <table border="1">
        <thead>
          <tr>
            <th>ID</th>
            <th>Prediction</th>
            <th>Time</th>
          </tr>
        </thead>

        <tbody>
          {data.map(item => (
            <tr key={item.id}>
              <td>{item.id}</td>
              <td>{item.prediction}</td>
              <td>{item.created_at}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default history;