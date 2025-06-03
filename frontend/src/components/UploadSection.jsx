import React from 'react';

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
        className="text-input"
        placeholder="Nome da Amostra"
        value={nomeAmostra}
        onChange={e => setNomeAmostra(e.target.value)}
        disabled={processando}
      /><br />

      {mensagemErroUI && (
        <div className="error-message">
          <strong>Erro:</strong> {mensagemErroUI}
        </div>
      )}

      {!processando && (
        <button
          onClick={() => fileInputRef.current?.click()}
          className="btn"
          disabled={processando}
        >
          📤 Enviar Imagem
        </button>
      )}
    </>
  );
}

export default UploadSection;
