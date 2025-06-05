import React, { useState, useEffect } from 'react';

const API_URL = import.meta.env.VITE_API_URL;
const CORES = ['amarela', 'bege', 'clara', 'rosada'];

function TrainingModal({ token, onClose }) {
  const [dados, setDados] = useState([]);
  const [indice, setIndice] = useState(0);
  const [corEscolhida, setCorEscolhida] = useState('');
  const [correcoes, setCorrecoes] = useState([]);
  const [simCount, setSimCount] = useState(0);
  const [modoSelecao, setModoSelecao] = useState(false);
  const [agradecimento, setAgradecimento] = useState(false);

  useEffect(() => {
    if (!token) return;
    fetch(`${API_URL}/colony_data/${token}`)
      .then(res => (res.ok ? res.json() : Promise.reject(res.statusText)))
      .then(data => {
        setDados(data.data || []);
      })
      .catch(() => {});
  }, [token]);

  const avancarIndice = () => {
    setModoSelecao(false);
    setIndice((prev) => prev + 1);
  };

  const enviarFeedback = (linhas) => {
    if (linhas.length === 0) {
      setAgradecimento(true);
      return;
    }
    fetch(`${API_URL}/feedback_treinamento`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, corrections: linhas })
    }).then(() => setAgradecimento(true));
  };

  const handleNao = () => {
    if (indice >= dados.length - 1) {
      enviarFeedback(correcoes);
    } else {
      avancarIndice();
    }
  };

  const handleSim = () => {
    setCorEscolhida(dados[indice].pred);
    setModoSelecao(true);
  };

  const confirmarCor = () => {
    const nova = [...correcoes, { index: indice, label: corEscolhida }];
    const totalSim = simCount + 1;
    setCorrecoes(nova);
    setSimCount(totalSim);
    if (totalSim >= 3 || indice >= dados.length - 1) {
      enviarFeedback(nova);
    } else {
      avancarIndice();
    }
  };

  if (agradecimento) {
    return (
      <div className="modal">
        <div className="modal-content">
          <p>Obrigado por colaborar!</p>
          <button onClick={onClose} className="btn">Fechar</button>
        </div>
      </div>
    );
  }

  if (!dados[indice]) return null;

  return (
    <div className="modal">
      <div className="modal-content">
        <h3>🤖 Me ajude a treinar a IA</h3>
        {!modoSelecao ? (
          <div>
            <p>Esta região detectada é uma colônia? (Previsto: {dados[indice].pred})</p>
            <button onClick={handleSim} className="btn">Sim</button>
            <button onClick={handleNao} className="btn">Não</button>
          </div>
        ) : (
          <div>
            <p>Qual a cor correta?</p>
            <select value={corEscolhida} onChange={e => setCorEscolhida(e.target.value)}>
              {CORES.map(c => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            <button onClick={confirmarCor} className="btn">Confirmar</button>
          </div>
        )}
      </div>
    </div>
  );
}

export default TrainingModal;
