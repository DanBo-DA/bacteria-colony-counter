import React from 'react';

const botaoEstilo = {
  backgroundColor: '#000',
  color: '#fff',
  border: '1px solid #fff',
  padding: '10px 18px',
  margin: '5px',
  borderRadius: 8,
  cursor: 'pointer',
  fontWeight: 'bold',
};

function ResultSection({ imagem, processando, resultado, feedback, onBaixar, onReset }) {
  if (!imagem) return null;

  const total = parseInt(resultado.TOTAL || 0);
  const densidade = feedback["densidadecoloniascm2"] || 0;
  const estimativa = feedback["estimativatotalcolonias"] || 0;

  return (
    <div style={{ marginTop: 20 }}>
      <img src={imagem} alt="Resultado do Processamento" style={{ maxWidth: 500, width: '100%', borderRadius: 10 }} />

      {!processando && Object.keys(resultado).length > 0 && !resultado.ERRO && (
        <div style={{ marginTop: 15 }}>
          <h3>🧪 Resumo de Colônias</h3>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <span style={{ color: '#fff', marginBottom: 4 }}><strong>TOTAL:</strong> {total}</span>
            <span style={{ color: '#fff', marginBottom: 4 }}><strong>Densidade (UFC/cm2):</strong> {densidade}</span>
            <span style={{ color: '#fff', marginBottom: 4 }}><strong>Estimativa Total (Placa 57.5cm2):</strong> {estimativa}</span>
          </div>
          {Object.keys(feedback).length > 0 && (
            <div style={{ marginTop: 20 }}>
              <h4>⚙️ Detalhes Técnicos</h4>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                {Object.entries(feedback).map(([chave, valor]) => (
                  !["densidadecoloniascm2", "estimativatotalcolonias"].includes(chave) && (
                    <span key={chave} style={{ color: '#ccc', fontSize: 13, marginBottom: 3 }}><strong>{chave}:</strong> {valor}</span>
                  )
                ))}
              </div>
            </div>
          )}
          <div style={{ marginTop: 10 }}>
            <button onClick={onBaixar} style={botaoEstilo} disabled={processando}>
              📥 Baixar Resultado
            </button>
            <button onClick={onReset} style={botaoEstilo} disabled={processando}>
              ♻️ Nova Imagem
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default ResultSection;
