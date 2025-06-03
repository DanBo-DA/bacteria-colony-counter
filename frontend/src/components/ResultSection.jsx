import React from 'react';

function ResultSection({ imagem, processando, resultado, feedback, onBaixar, onReset }) {
  if (!imagem) return null;

  const total = parseInt(resultado.TOTAL || 0);
  const densidade = feedback["densidadecoloniascm2"] || 0;
  const estimativa = feedback["estimativatotalcolonias"] || 0;

  return (
    <div className="result-section">
      <img src={imagem} alt="Resultado do Processamento" className="result-image" />

      {!processando && Object.keys(resultado).length > 0 && !resultado.ERRO && (
        <div className="summary-container">
          <h3>🧪 Resumo de Colônias</h3>
          <div className="summary-content">
            <span className="summary-row"><strong>TOTAL:</strong> {total}</span>
            <span className="summary-row"><strong>Densidade (UFC/cm2):</strong> {densidade}</span>
            <span className="summary-row"><strong>Estimativa Total (Placa 57.5cm2):</strong> {estimativa}</span>
          </div>
          {Object.keys(feedback).length > 0 && (
            <div className="details-container">
              <h4>⚙️ Detalhes Técnicos</h4>
              <div className="details-content">
                {Object.entries(feedback).map(([chave, valor]) => (
                  !["densidadecoloniascm2", "estimativatotalcolonias"].includes(chave) && (
                    <span key={chave} className="details-item"><strong>{chave}:</strong> {valor}</span>
                  )
                ))}
              </div>
            </div>
          )}
          <div className="buttons-container">
            <button onClick={onBaixar} className="btn" disabled={processando}>
              📥 Baixar Resultado
            </button>
            <button onClick={onReset} className="btn" disabled={processando}>
              ♻️ Nova Imagem
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default ResultSection;
