import React from 'react';

function UploadSection({ fileInputRef, handleImageUpload, nomeAmostra, setNomeAmostra, processando, mensagemErroUI }) {
  const [previewSrc, setPreviewSrc] = React.useState(null);

  const previewAndUpload = (files) => {
    const file = files && files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      setPreviewSrc(e.target.result);
      handleImageUpload({ target: { files } });
    };
    reader.readAsDataURL(file);
  };

  const handleFileSelect = (e) => {
    previewAndUpload(e.target.files);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    previewAndUpload(e.dataTransfer.files);
  };

  return (
    <>
      <input
        type="file"
        accept="image/*"
        ref={fileInputRef}
        onChange={handleFileSelect}
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

      <div
        className="drop-area"
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        Arraste e solte a imagem aqui ou clique para selecionar
      </div>

      {previewSrc && (
        <div className="preview-container">
          <img src={previewSrc} alt="Pré-visualização" className="preview-image" />
        </div>
      )}

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
