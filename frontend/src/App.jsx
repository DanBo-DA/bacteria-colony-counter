import React, { useRef, useState, useEffect } from 'react';
import UploadSection from './components/UploadSection';
import ProgressBar from './components/ProgressBar';
import ResultSection from './components/ResultSection';
import HistorySection from './components/HistorySection';

const API_URL = import.meta.env.VITE_API_URL;

function App() {
  const fileInputRef = useRef(null);
  const [imagem, setImagem] = useState(null);
  const [resultado, setResultado] = useState({});
  const [feedback, setFeedback] = useState({});
  const [processando, setProcessando] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [statusMensagem, setStatusMensagem] = useState(""); // Estado unificado para mensagens de status
  const [nomeArquivo, setNomeArquivo] = useState("");
  const [nomeAmostra, setNomeAmostra] = useState("");
  const [logAnalises, setLogAnalises] = useState([]);
  const [selecionados, setSelecionados] = useState({});
  const [todosSelecionados, setTodosSelecionados] = useState(false);
  const [mensagemErroUI, setMensagemErroUI] = useState("");

  const xhrRef = useRef(null);

  // Carrega histórico salvo no navegador ao inicializar
  useEffect(() => {
    try {
      const salvo = localStorage.getItem('logAnalises');
      if (salvo) {
        const parsed = JSON.parse(salvo);
        if (Array.isArray(parsed)) {
          setLogAnalises(parsed);
        }
      }
    } catch (e) {
      console.error('Falha ao carregar histórico do localStorage', e);
    }
  }, []);

  // Salva histórico sempre que sofrer alterações
  useEffect(() => {
    try {
      localStorage.setItem('logAnalises', JSON.stringify(logAnalises));
    } catch (e) {
      console.error('Falha ao salvar histórico no localStorage', e);
    }
  }, [logAnalises]);

  // Libera o objeto URL anterior quando a imagem muda
  useEffect(() => {
    return () => {
      if (imagem) {
        URL.revokeObjectURL(imagem);
      }
    };
  }, [imagem]);

  const normalize = (str) => str.toLowerCase().replace(/[^a-z0-9]/g, '');

  const handleReset = () => {
    if (imagem) {
      URL.revokeObjectURL(imagem);
    }
    setImagem(null);
    setResultado({});
    setFeedback({});
    setNomeArquivo("");
    if (fileInputRef.current) fileInputRef.current.value = "";
    setMensagemErroUI("");
    setProcessando(false);
    setUploadProgress(0);
    setStatusMensagem(""); // Limpa mensagem de status
    if (xhrRef.current) {
      xhrRef.current.abort();
    }
  };

  const handleImageUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setProcessando(true);
    setUploadProgress(0);
    setStatusMensagem("Preparando para enviar..."); // Mensagem inicial
    setResultado({});
    setFeedback({});
    setImagem(null);
    setNomeArquivo(file.name);
    setMensagemErroUI("");

    const formData = new FormData();
    formData.append('file', file);
    formData.append('nome_amostra', nomeAmostra || file.name);

    const xhr = new XMLHttpRequest();
    xhrRef.current = xhr;

    if (!API_URL) {
      setMensagemErroUI("URL da API não definida. Verifique o arquivo .env (VITE_API_URL).");
      setProcessando(false);
      setUploadProgress(0);
      return;
    }

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const percentComplete = Math.round((e.loaded / e.total) * 100);
        setUploadProgress(percentComplete);
        if (percentComplete < 100) {
          setStatusMensagem(`Enviando imagem: ${percentComplete}%`);
        } else {
          // O upload para o servidor (transferência de bytes) está completo.
          // Agora estamos aguardando o processamento do backend.
          setStatusMensagem("Upload concluído. Aguarde, processando no servidor...");
        }
      }
    };

    xhr.onload = () => {
      xhrRef.current = null;
      if (xhr.status >= 200 && xhr.status < 300) {
        const headers = {};
        const allHeaders = xhr.getAllResponseHeaders().trim().split(/[\r\n]+/);
        allHeaders.forEach(line => {
          const parts = line.split(': ');
          const header = parts.shift();
          const value = parts.join(': ');
          headers[header.toLowerCase()] = value;
        });

        const blob = xhr.response;
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
        setStatusMensagem("Processamento concluído!"); // Sucesso final

        const novaEntrada = {
          nomeAmostra: nomeAmostra || file.name,
          data: new Date().toLocaleDateString(),
          hora: new Date().toLocaleTimeString(),
          ...resumo,
          ...dadosFeedback
        };
        setLogAnalises(prev => [...prev, novaEntrada]);
        setProcessando(false); // Terminou tudo
        // Poderia limpar setStatusMensagem após um tempo ou deixar "Processamento concluído!"

      } else {
        let errorMsg = `Erro no servidor: ${xhr.status} ${xhr.statusText}`;
        try {
          if (xhr.responseText) {
            const errorData = JSON.parse(xhr.responseText);
            errorMsg = errorData.detail || errorMsg;
          }
        } catch (e) {
          // Falha ao parsear JSON
        }
        setMensagemErroUI(errorMsg);
        setResultado({ ERRO: "Falha no processamento." });
        setProcessando(false);
        setUploadProgress(0);
        setStatusMensagem("Falha no processamento."); // Erro do backend
      }
    };

    xhr.onerror = () => {
      xhrRef.current = null;
      setMensagemErroUI("Erro de rede ou requisição falhou. Verifique sua conexão.");
      setProcessando(false);
      setUploadProgress(0);
      setStatusMensagem("Falha na comunicação."); // Erro de rede
    };

    xhr.onabort = () => {
        xhrRef.current = null;
        // setMensagemErroUI("Upload cancelado."); // Pode ser redundante se o statusMensagem já indicar
        setProcessando(false);
        setUploadProgress(0);
        setStatusMensagem("Envio cancelado pelo usuário.");
    };


    xhr.open('POST', `${API_URL}/contar/`, true);
    xhr.responseType = 'blob';
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
    const url = URL.createObjectURL(blob);
    link.href = url;
    link.download = "analises_colonias.csv";
    document.body.appendChild(link);
    link.click();
    URL.revokeObjectURL(url);
    // Remove o elemento para limpar a memória (opcional)
    link.remove();
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

  const toggleSelecionado = (idx) => {
    setSelecionados(prev => ({ ...prev, [idx]: !prev[idx] }));
  };

  const total = parseInt(resultado.TOTAL || 0);
  const densidade = feedback["densidadecoloniascm2"] || 0;
  const estimativa = feedback["estimativatotalcolonias"] || 0;


  return (
    <div className="app-container">
      <h1 className="app-header">Contador de Colônias Bacterianas v1.6.6 (Alta Densidade)</h1>
      <p className="caution-msg">
        ⚠️ Esta versão é otimizada para imagens com <strong>grande número de colônias(&gt;300 UFC/placa)</strong>.
        Pode gerar falsos positivos em placas com baixa densidade ou interferências no fundo.
      </p>
      <UploadSection
        fileInputRef={fileInputRef}
        handleImageUpload={handleImageUpload}
        nomeAmostra={nomeAmostra}
        setNomeAmostra={setNomeAmostra}
        processando={processando}
        mensagemErroUI={mensagemErroUI}
      />

      <ProgressBar
        processando={processando}
        statusMensagem={statusMensagem}
        uploadProgress={uploadProgress}
        onCancel={() => {
          if (xhrRef.current) {
            xhrRef.current.abort();
          }
        }}
      />

      <ResultSection
        imagem={imagem}
        processando={processando}
        resultado={resultado}
        feedback={feedback}
        onBaixar={baixarImagem}
        onReset={handleReset}
      />

      <HistorySection
        logAnalises={logAnalises}
        selecionados={selecionados}
        todosSelecionados={todosSelecionados}
        selecionarTodos={selecionarTodos}
        toggleSelecionado={toggleSelecionado}
        exportarCSV={exportarCSV}
        excluirEntrada={excluirEntrada}
        excluirTodos={excluirTodos}
        processando={processando}
      />

      <footer className="footer-info">
        👨‍🔬 Powered by <strong>Daniel Borges</strong>
      </footer>
      </div>
  );
}


export default App;
