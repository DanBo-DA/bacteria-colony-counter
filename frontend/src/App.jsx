import React, { useRef, useState, useEffect } from 'react'; // Adicionado useEffect

function App() {
  const fileInputRef = useRef(null);
  const [imagem, setImagem] = useState(null);
  const [resultado, setResultado] = useState({});
  const [feedback, setFeedback] = useState({});
  const [processando, setProcessando] = useState(false); // Abrangerá upload e processamento backend
  const [uploadProgress, setUploadProgress] = useState(0); // Novo estado para progresso
  const [statusUpload, setStatusUpload] = useState(""); // Mensagem durante o upload/processamento
  const [nomeArquivo, setNomeArquivo] = useState("");
  const [nomeAmostra, setNomeAmostra] = useState("");
  const [logAnalises, setLogAnalises] = useState([]);
  const [selecionados, setSelecionados] = useState({});
  const [todosSelecionados, setTodosSelecionados] = useState(false);
  const [mensagemErroUI, setMensagemErroUI] = useState("");

  // Referência para o XHR para poder abortar se necessário (opcional)
  const xhrRef = useRef(null);

  const normalize = (str) => str.toLowerCase().replace(/[^a-z0-9]/g, '');

  const handleReset = () => {
    setImagem(null);
    setResultado({});
    setFeedback({});
    setNomeArquivo("");
    if (fileInputRef.current) fileInputRef.current.value = "";
    setMensagemErroUI("");
    setProcessando(false);
    setUploadProgress(0);
    setStatusUpload("");
    if (xhrRef.current) {
      xhrRef.current.abort(); // Abortar requisição em andamento se houver
    }
  };

  const handleImageUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setProcessando(true);
    setUploadProgress(0);
    setStatusUpload("Enviando imagem...");
    setResultado({});
    setFeedback({});
    setImagem(null); // Limpa imagem anterior
    setNomeArquivo(file.name);
    setMensagemErroUI("");

    const formData = new FormData();
    formData.append('file', file);
    formData.append('nome_amostra', nomeAmostra || file.name);

    const xhr = new XMLHttpRequest();
    xhrRef.current = xhr; // Salva a referência

    // Monitorar progresso do upload
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const percentComplete = Math.round((e.loaded / e.total) * 100);
        setUploadProgress(percentComplete);
        if (percentComplete < 100) {
          setStatusUpload(`Enviando imagem: ${percentComplete}%`);
        } else {
          setStatusUpload("Upload completo. Processando no servidor...");
        }
      }
    };

    // Upload concluído (não necessariamente com sucesso na API)
    xhr.onload = () => {
      xhrRef.current = null; // Limpa a referência
      if (xhr.status >= 200 && xhr.status < 300) {
        // Sucesso no upload e na resposta do backend
        const headers = {};
        const allHeaders = xhr.getAllResponseHeaders().trim().split(/[\r\n]+/);
        allHeaders.forEach(line => {
          const parts = line.split(': ');
          const header = parts.shift();
          const value = parts.join(': ');
          headers[header.toLowerCase()] = value;
        });

        // Assumindo que a resposta é um blob (imagem)
        const blob = xhr.response; // xhr.responseType = 'blob' deve ser setado
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
        setStatusUpload("Processamento concluído!");

        const novaEntrada = {
          nomeAmostra: nomeAmostra || file.name,
          data: new Date().toLocaleDateString(),
          hora: new Date().toLocaleTimeString(),
          ...resumo,
          ...dadosFeedback
        };
        setLogAnalises(prev => [...prev, novaEntrada]);
        setProcessando(false); // Terminou tudo

      } else {
        // Erro do servidor
        let errorMsg = `Erro no servidor: ${xhr.status} ${xhr.statusText}`;
        try {
          if (xhr.responseText) {
            const errorData = JSON.parse(xhr.responseText);
            errorMsg = errorData.detail || errorMsg;
          }
        } catch (e) {
          // Falha ao parsear JSON do erro
        }
        setMensagemErroUI(errorMsg);
        setResultado({ ERRO: "Falha no processamento." });
        setProcessando(false);
        setUploadProgress(0); // Resetar progresso em caso de erro
        setStatusUpload("Falha no envio/processamento.");
      }
    };

    // Erro na requisição (rede, etc.)
    xhr.onerror = () => {
      xhrRef.current = null; // Limpa a referência
      setMensagemErroUI("Erro de rede ou requisição falhou. Verifique sua conexão.");
      setProcessando(false);
      setUploadProgress(0);
      setStatusUpload("Falha na comunicação.");
    };

    // Requisição abortada
    xhr.onabort = () => {
        xhrRef.current = null; // Limpa a referência
        setMensagemErroUI("Upload cancelado.");
        setProcessando(false);
        setUploadProgress(0);
        setStatusUpload("Upload cancelado pelo usuário.");
    };


    xhr.open('POST', 'https://bacteria-colony-counter-production.up.railway.app/contar/', true);
    xhr.responseType = 'blob'; // Importante para receber a imagem como blob
    xhr.send(formData);
  };

  // ... (resto do código: baixarImagem, exportarCSV, etc. permanecem os mesmos)


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
    if (selecionadosParaExportar.length === 0) {
        setMensagemErroUI("Nenhuma análise selecionada para exportação.");
        return;
    }
    setMensagemErroUI(""); // Limpa msg de erro se houver
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

  const excluirEntrada = (index) => {
    setLogAnalises(prev => prev.filter((_, i) => i !== index));
    setSelecionados(prev => {
      const novo = { ...prev };
      delete novo[index];
      return novo;
    });
  };

  const excluirTodos = () => {
    setLogAnalises([]);
    setSelecionados({});
    setTodosSelecionados(false);
  };

  const selecionarTodos = () => {
    const novoEstado = {};
    logAnalises.forEach((_, idx) => {
      novoEstado[idx] = !todosSelecionados;
    });
    setSelecionados(novoEstado);
    setTodosSelecionados(!todosSelecionados);
  };

  const total = parseInt(resultado.TOTAL || 0);
  const densidade = feedback["densidadecoloniascm2"] || 0;
  const estimativa = feedback["estimativatotalcolonias"] || 0;


  return (
    <div style={{ padding: 20, textAlign: 'center', backgroundColor: '#111', color: '#fff', minHeight: '100vh' }}>
      <h1 style={{ fontSize: 32 }}>Contador de Colônias Bacterianas v1.5.2 (Alta Densidade)</h1>
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
        disabled={processando}
      />

      <input
        type="text"
        placeholder="Nome da Amostra"
        value={nomeAmostra}
        onChange={e => setNomeAmostra(e.target.value)}
        style={{ padding: 8, marginTop: 10, borderRadius: 6, border: '1px solid #444', backgroundColor: '#222', color: '#fff' }}
        disabled={processando}
      /><br />

      {mensagemErroUI && (
        <div style={{ 
            color: 'white', 
            marginTop: 15, 
            marginBottom: 10, 
            padding: '10px 15px', 
            border: '1px solid #ff4d4d',
            borderRadius: 8, 
            backgroundColor: '#6b2222',
            maxWidth: 600,
            margin: '10px auto',
            fontSize: 14
        }}>
          <strong>Erro:</strong> {mensagemErroUI}
        </div>
      )}

      {/* Barra de Progresso e Status do Upload/Processamento */}
      {processando && (
        <div style={{ marginTop: 20, padding: 15, backgroundColor: 'rgba(50,50,50,0.8)', borderRadius: 8, maxWidth: 400, margin: '10px auto' }}>
          <p style={{fontSize: 16, fontWeight: 'bold', marginBottom: 10}}>{statusUpload}</p>
          {uploadProgress > 0 && ( // Só mostra a barra se o progresso for maior que 0
            <div style={{ width: '100%', backgroundColor: '#555', borderRadius: 4, overflow: 'hidden', border: '1px solid #777' }}>
              <div 
                style={{ 
                  width: `${uploadProgress}%`, 
                  height: '20px', 
                  backgroundColor: '#4caf50', 
                  textAlign: 'center', 
                  lineHeight: '20px', 
                  color: 'white',
                  transition: 'width 0.3s ease-in-out'
                }}
              >
                {uploadProgress}%
              </div>
            </div>
          )}
           <button 
            onClick={() => {
                if (xhrRef.current) {
                    xhrRef.current.abort();
                }
            }} 
            style={{...botaoEstilo, backgroundColor: '#c00', marginTop:10, padding: '8px 15px', fontSize: '0.9em'}}
            hidden={!xhrRef.current} // Só mostra se houver uma requisição XHR ativa
            >
            Cancelar Upload
           </button>
        </div>
      )}

      {!processando && !imagem && (
        <button 
          onClick={() => fileInputRef.current?.click()} 
          style={botaoEstilo} 
          disabled={processando}
        >
          📤 Enviar Imagem
        </button>
      )}


      {imagem && ( // Mostra a imagem se ela existir (mesmo que o processamento tenha falhado, para ver o que foi enviado)
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
                <button onClick={baixarImagem} style={botaoEstilo} disabled={processando}>
                  📥 Baixar Resultado
                </button>
                <button onClick={handleReset} style={botaoEstilo} disabled={processando}>
                  ♻️ Nova Imagem
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {logAnalises.length > 0 && (
        <div style={{ marginTop: 30 }}>
          <h3>📋 Histórico de Análises</h3>
          <div style={{ marginBottom: 10 }}>
            <button onClick={selecionarTodos} style={botaoEstilo} disabled={processando}>{todosSelecionados ? "☑️ Desmarcar Todos" : "✅ Selecionar Todos"}</button>
            <button onClick={exportarCSV} style={botaoEstilo} disabled={processando}>⬇️ Exportar Selecionados</button>
            <button onClick={excluirTodos} style={botaoEstilo} disabled={processando}>🗑️ Excluir Tudo</button>
          </div>
          <table style={{ width: '100%', marginTop: 10, borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ backgroundColor: '#222', color: '#ddd' }}>
                <th><input type="checkbox" onChange={selecionarTodos} checked={todosSelecionados} disabled={processando} /></th>
                <th>Data</th>
                <th>Hora</th>
                <th>Amostra</th>
                <th>Total</th>
                <th>Densidade</th>
                <th>Estimativa</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {logAnalises.map((item, idx) => (
                <tr key={idx} style={{ backgroundColor: idx % 2 === 0 ? '#1c1c1c' : '#2c2c2c' }}>
                  <td><input type="checkbox" checked={!!selecionados[idx]} onChange={() => setSelecionados(prev => ({ ...prev, [idx]: !prev[idx] }))} disabled={processando} /></td>
                  <td>{item.data}</td>
                  <td>{item.hora}</td>
                  <td>{item.nomeAmostra}</td>
                  <td>{item.TOTAL}</td>
                  <td>{item.densidadecoloniascm2}</td>
                  <td>{item.estimativatotalcolonias}</td>
                  <td><button onClick={() => excluirEntrada(idx)} style={{ fontSize: 11, backgroundColor: '#800', color: '#fff', border: 'none', padding: '4px 8px', borderRadius: 4, cursor: 'pointer' }} disabled={processando}>Excluir</button></td>
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
