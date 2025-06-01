import React, { useRef, useState } from 'react';

function App() {
  const fileInputRef = useRef(null);
  const [imagem, setImagem] = useState(null);
  const [resultado, setResultado] = useState({});
  const [feedback, setFeedback] = useState({});
  const [processando, setProcessando] = useState(false);
  const [nomeArquivo, setNomeArquivo] = useState("");
  const [nomeAmostra, setNomeAmostra] = useState("");
  const [logAnalises, setLogAnalises] = useState([]);
  const [selecionados, setSelecionados] = useState({});

  const normalize = (str) => str.toLowerCase().replace(/[^a-z0-9]/g, '');

  const handleReset = () => {
    setImagem(null);
    setResultado({});
    setFeedback({});
    setNomeArquivo("");
    setNomeAmostra("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleImageUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setProcessando(true);
    setResultado({});
    setFeedback({});
    setImagem(null);
    setNomeArquivo(file.name);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('nome_amostra', nomeAmostra || file.name);

    try {
      const response = await fetch('https://bacteria-colony-counter-production.up.railway.app/contar/', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) throw new Error('Erro na requisição');

      const headers = {};
      response.headers.forEach((valor, chave) => {
        headers[chave] = valor;
      });

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      setImagem(url);

      const resumo = {};
      const dadosFeedback = {};

      Object.entries(headers).forEach(([chave, valor]) => {
        if (chave.toLowerCase().startsWith("x-resumo-")) {
          const label = chave.replace("x-resumo-", "").toUpperCase();
          resumo[label] = valor;
        }
        if (chave.toLowerCase().startsWith("x-feedback-")) {
          const key = normalize(chave.replace("x-feedback-", ""));
          dadosFeedback[key] = valor;
        }
      });

      setResultado(resumo);
      setFeedback(dadosFeedback);

      const novaEntrada = {
        nomeAmostra: nomeAmostra || file.name,
        data: new Date().toLocaleDateString(),
        hora: new Date().toLocaleTimeString(),
        ...resumo,
        ...dadosFeedback
      };
      setLogAnalises(prev => [...prev, novaEntrada]);

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

  const exportarCSV = () => {
    const selecionadosParaExportar = logAnalises.filter((_, idx) => selecionados[idx]);
    if (selecionadosParaExportar.length === 0) return;
    const colunas = ["nomeAmostra", "data", "hora", "TOTAL", "densidadecoloniascm2", "estimativatotalcolonias"];
    const linhas = [colunas.join(",")];
    selecionadosParaExportar.forEach(item => {
      const linha = colunas.map(c => item[c] || "").join(",");
      linhas.push(linha);
    });
    const blob = new Blob([linhas.join("\n")], { type: 'text/csv' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = "analises_colonias.csv";
    link.click();
  };

  const total = parseInt(resultado.TOTAL || 0);
  const densidade = feedback["densidadecoloniascm2"] || 0;
  const estimativa = feedback["estimativatotalcolonias"] || 0;

  return (
    <div style={{ padding: 20, textAlign: 'center', backgroundColor: '#111', color: '#fff', minHeight: '100vh' }}>
      <h1 style={{ fontSize: 32 }}>Contador de Colônias Bacterianas v2 (Alta Densidade)</h1>
      <p style={{ backgroundColor: '#222', color: '#ddd', padding: '10px 15px', borderRadius: 8, maxWidth: 600, margin: '10px auto', fontSize: 14 }}>
        ⚠️ Esta versão é otimizada para imagens com <strong>grande número de colônias(&gt;500 UFC/placa)</strong>.
        Pode gerar falsos positivos em placas com baixa densidade ou interferências no fundo.
      </p>

      <input
        type="file"
        accept="image/*"
        ref={fileInputRef}
        onChange={handleImageUpload}
        style={{ display: 'none' }}
      />

      <input
        type="text"
        placeholder="Nome da Amostra"
        value={nomeAmostra}
        onChange={e => setNomeAmostra(e.target.value)}
        style={{ padding: 8, marginTop: 10, borderRadius: 6, border: '1px solid #444', backgroundColor: '#222', color: '#fff' }}
      /><br />

      {!imagem && (
        <button onClick={() => fileInputRef.current?.click()} style={botaoEstilo}>📤 Enviar Imagem</button>
      )}

      {imagem && (
        <div style={{ marginTop: 20 }}>
          <img src={imagem} alt="Resultado" style={{ maxWidth: 500, width: '100%', borderRadius: 10 }} />
          {processando && <p style={{ marginTop: 10 }}>🔄 Processando imagem...</p>}

          {!processando && (
            <div style={{ marginTop: 15 }}>
              <h3>🧪 Resumo de Colônias</h3>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                <span style={{ color: '#fff', marginBottom: 4 }}><strong>TOTAL:</strong> {total}</span>
                <span style={{ color: '#fff', marginBottom: 4 }}><strong>Densidade (UFC/cm²):</strong> {densidade}</span>
                <span style={{ color: '#fff', marginBottom: 4 }}><strong>Estimativa Total (Placa 57.5cm²):</strong> {estimativa}</span>
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
                <button onClick={baixarImagem} style={botaoEstilo}>📥 Baixar Resultado</button>
                <button onClick={handleReset} style={botaoEstilo}>♻️ Resetar</button>
              </div>
            </div>
          )}
        </div>
      )}

      {logAnalises.length > 0 && (
        <div style={{ marginTop: 30 }}>
          <h3>📋 Histórico de Análises</h3>
          <button onClick={exportarCSV} style={botaoEstilo}>⬇️ Exportar CSV</button>
          <table style={{ width: '100%', marginTop: 10, borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ backgroundColor: '#222', color: '#ddd' }}>
                <th></th>
                <th>Data</th>
                <th>Hora</th>
                <th>Nome da Amostra</th>
                <th>Total</th>
                <th>Densidade (UFC/cm²)</th>
                <th>Estimativa Total</th>
              </tr>
            </thead>
            <tbody>
              {logAnalises.map((item, idx) => (
                <tr key={idx} style={{ backgroundColor: idx % 2 === 0 ? '#1c1c1c' : '#2c2c2c', color: '#fff' }}>
                  <td>
                    <input
                      type="checkbox"
                      checked={!!selecionados[idx]}
                      onChange={() => setSelecionados(prev => ({ ...prev, [idx]: !prev[idx] }))}
                    />
                  </td>
                  <td>{item.data}</td>
                  <td>{item.hora}</td>
                  <td>{item.nomeAmostra}</td>
                  <td>{item.TOTAL}</td>
                  <td>{item.densidadecoloniascm2}</td>
                  <td>{item.estimativatotalcolonias}</td>
                </tr>
              ))}
            </tbody>
          </table>
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
