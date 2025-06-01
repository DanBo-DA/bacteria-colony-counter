import React, { useRef, useState } from 'react';

function App() {
  const fileInputRef = useRef(null);
  const [imagem, setImagem] = useState(null);
  const [resultado, setResultado] = useState({});
  const [processando, setProcessando] = useState(false);
  const [nomeArquivo, setNomeArquivo] = useState("");

  const handleReset = () => {
    setImagem(null);
    setResultado({});
    setNomeArquivo("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleImageUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setProcessando(true);
    setResultado({});
    setImagem(null);
    setNomeArquivo(file.name);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('https://bacteria-colony-counter-production.up.railway.app/contar/?v=3', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) throw new Error('Erro na requisição');

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      setImagem(url);

      // Extrai todos os headers que começam com 'x-resumo-'
      const resumo = {};
      response.headers.forEach((valor, chave) => {
        if (chave.toLowerCase().startsWith("x-resumo-")) {
          const label = chave.replace("x-resumo-", "").toUpperCase();
          resumo[label] = valor;
        }
      });
      setResultado(resumo);

    } catch (error) {
      console.error('Erro ao processar imagem:', error);
      setResultado({ ERRO: "Não foi possível processar." });
    } finally {
      setProcessando(false);
    }
  };

  const baixarImagem = () => {
    if (imagem) {
      const link = document.createElement('a');
      link.href = imagem;
      link.download = `resultado_${nomeArquivo}`;
      link.click();
    }
  };

  return (
    <div style={{ padding: 20, textAlign: 'center', backgroundColor: '#111', color: '#fff', minHeight: '100vh' }}>
      <h1 style={{ fontSize: 32 }}>Contador de Colônias Bacterianas</h1>

      <input
        type="file"
        accept="image/*"
        ref={fileInputRef}
        onChange={handleImageUpload}
        style={{ display: 'none' }}
      />
      {!imagem && (
        <button onClick={() => fileInputRef.current?.click()} style={botaoEstilo}>
          Enviar Imagem
        </button>
      )}

      {imagem && (
        <div style={{ marginTop: 20 }}>
          <img src={imagem} alt="Resultado" style={{ maxWidth: 500, width: '100%', borderRadius: 10 }} />

          {processando && <p style={{ marginTop: 10 }}>🔄 Processando imagem...</p>}

          {!processando && Object.keys(resultado).length > 0 && (
            <div style={{ marginTop: 15 }}>
              <h3>🧪 Colônias Detectadas</h3>
              <ul style={{ listStyle: 'none', padding: 0 }}>
                {Object.entries(resultado).map(([chave, valor]) => (
                  <li key={chave}><strong>{chave}:</strong> {valor}</li>
                ))}
              </ul>

              <div style={{ marginTop: 10 }}>
                <button onClick={baixarImagem} style={botaoEstilo}>📥 Baixar Resultado</button>{' '}
                <button onClick={handleReset} style={botaoEstilo}>♻️ Resetar</button>
              </div>
            </div>
          )}
        </div>
      )}

      <footer style={{ marginTop: 40, fontSize: 14, opacity: 0.6 }}>
        👨‍🔬 Powered by <strong>Daniel Borges</strong>
      </footer>
    </div>
  );
}

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

export default App;
