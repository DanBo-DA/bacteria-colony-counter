import React, { useState, useEffect } from 'react';

const API_URL = import.meta.env.VITE_API_URL;
const CORES = ['amarela', 'bege', 'clara', 'rosada'];

function TrainingModal({ token, onClose }) {
  const [dados, setDados] = useState([]);
  const [labels, setLabels] = useState([]);

  useEffect(() => {
    if (!token) return;
    fetch(`${API_URL}/colony_data/${token}`)
      .then(res => res.ok ? res.json() : Promise.reject(res.statusText))
      .then(data => {
        setDados(data.data || []);
        setLabels((data.data || []).map(d => d.pred));
      })
      .catch(() => {});
  }, [token]);

  const handleChange = (idx, value) => {
    setLabels(prev => {
      const copy = [...prev];
      copy[idx] = value;
      return copy;
    });
  };

  const handleSubmit = () => {
    const corrections = labels.map((lab, idx) => ({ index: idx, label: lab }));
    fetch(`${API_URL}/feedback_treinamento`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, corrections })
    }).then(() => onClose());
  };

  return (
    <div className="modal">
      <div className="modal-content">
        <h3>🤖 Me ajude a treinar a IA</h3>
        <ul>
          {dados.map((item, idx) => (
            <li key={idx} className="feedback-item">
              Colônia {idx + 1} - Modelo: {item.pred}
              <select value={labels[idx]} onChange={e => handleChange(idx, e.target.value)}>
                {CORES.map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </li>
          ))}
        </ul>
        <button onClick={handleSubmit} className="btn">Enviar Minhas Sugestões</button>
        <button onClick={onClose} className="btn">Fechar</button>
      </div>
    </div>
  );
}

export default TrainingModal;
