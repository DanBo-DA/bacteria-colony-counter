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

const errorStyle = {
  color: 'white',
  marginTop: 15,
  marginBottom: 10,
  padding: '10px 15px',
  border: '1px solid #ff4d4d',
  borderRadius: 8,
  backgroundColor: '#6b2222',
  maxWidth: 600,
  margin: '10px auto',
  fontSize: 14,
};

function UploadSection({ fileInputRef, handleImageUpload, nomeAmostra, setNomeAmostra, processando, mensagemErroUI }) {
  return (
    <>
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
        <div style={errorStyle}>
          <strong>Erro:</strong> {mensagemErroUI}
        </div>
      )}

      {!processando && (
        <button
          onClick={() => fileInputRef.current?.click()}
          style={botaoEstilo}
          disabled={processando}
        >
          📤 Enviar Imagem
        </button>
      )}
    </>
  );
}

export default UploadSection;
