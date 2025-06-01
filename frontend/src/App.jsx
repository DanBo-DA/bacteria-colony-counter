import React, { useRef, useState } from 'react';

function App() {
  const fileInputRef = useRef(null);
  const [imagem, setImagem] = useState(null);
  const [resultado, setResultado] = useState(null);
  const [processando, setProcessando] = useState(false);

  const handleImageUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setProcessando(true);
    setResultado(null);
    setImagem(null);

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

      // CORREÇÃO AQUI: Mudança de 'X-Colonias' para 'X-Resumo-Total'
      const totalColonias = response.headers.get('x-resumo-total');
      setResultado(totalColonias !== null ? totalColonias : 'Indisponível');
    } catch (error) {
      console.error('Erro ao processar imagem:', error);
      setResultado('Erro');
    } finally {
      setProcessando(false);
    }
  };

  return (
    <div style={{ padding: 20, textAlign: 'center' }}>
      <h1>Contador de Colônias Bacterianas</h1>
      <input
        type="file"
        accept="image/*"
        ref={fileInputRef}
        onChange={handleImageUpload}
        style={{ display: 'none' }}
      />
      <button onClick={() => fileInputRef.current?.click()}>Enviar Imagem</button>

      {imagem && (
        <div style={{ marginTop: 20 }}>
          <img src={imagem} alt="Resultado" style={{ width: '100%', maxWidth: 400 }} />
          {processando && <p>Processando imagem...</p>}
          {!processando && resultado !== null && (
            <p>Colônias Detectadas: {resultado}</p>
          )}
        </div>
      )}
    </div>
  );
}

export default App;
