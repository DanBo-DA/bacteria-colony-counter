import React from 'react';

function UploadSection({ fileInputRef, handleImageUpload, nomeAmostra, setNomeAmostra, processando, mensagemErroUI, resetSignal }) {
  const [previewSrc, setPreviewSrc] = React.useState(null);
  const [selectedFile, setSelectedFile] = React.useState(null);
  const [advanced, setAdvanced] = React.useState(false);
  const [areaMin, setAreaMin] = React.useState(4.0);
  const [circularidadeMin, setCircularidadeMin] = React.useState(0.30);
  const [maxSizeFactor, setMaxSizeFactor] = React.useState(0.2);
  const canvasRef = React.useRef(null);
  const imgRef = React.useRef(null);
  const [drawing, setDrawing] = React.useState(false);
  const [startPt, setStartPt] = React.useState(null);
  const [circle, setCircle] = React.useState({ x: null, y: null, r: null });

  React.useEffect(() => {
    setPreviewSrc(null);
    setSelectedFile(null);
    setCircle({ x: null, y: null, r: null });
  }, [resetSignal]);

  React.useEffect(() => {
    if (previewSrc && canvasRef.current && imgRef.current) {
      const canvas = canvasRef.current;
      const img = imgRef.current;
      canvas.width = img.width;
      canvas.height = img.height;
    }
  }, [previewSrc, advanced]);

  const previewFile = (files) => {
    const file = files && files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      setPreviewSrc(e.target.result);
      setSelectedFile(file);
    };
    reader.readAsDataURL(file);
  };

  const handleFileSelect = (e) => {
    previewFile(e.target.files);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    previewFile(e.dataTransfer.files);
  };

  const drawCircle = (x, y, r) => {
    const ctx = canvasRef.current.getContext('2d');
    ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
    if (r > 0) {
      ctx.beginPath();
      ctx.strokeStyle = 'red';
      ctx.lineWidth = 2;
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.stroke();
    }
  };

  const handleMouseDown = (e) => {
    if (!advanced) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setStartPt({ x, y });
    setDrawing(true);
  };

  const handleMouseMove = (e) => {
    if (!drawing) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const r = Math.sqrt(Math.pow(x - startPt.x, 2) + Math.pow(y - startPt.y, 2));
    drawCircle(startPt.x, startPt.y, r);
  };

  const handleMouseUp = (e) => {
    if (!drawing) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const r = Math.sqrt(Math.pow(x - startPt.x, 2) + Math.pow(y - startPt.y, 2));
    drawCircle(startPt.x, startPt.y, r);
    setCircle({ x: startPt.x, y: startPt.y, r });
    setDrawing(false);
  };

  const handleProcessar = () => {
    if (!selectedFile) return;

    const extras = {
      area_min: areaMin,
      circularidade_min: circularidadeMin,
      max_colony_size_factor: maxSizeFactor,
    };

    if (circle.x != null && imgRef.current) {
      const img = imgRef.current;
      const scaleX = img.naturalWidth / img.width;
      const scaleY = img.naturalHeight / img.height;
      extras.x = Math.round(circle.x * scaleX);
      extras.y = Math.round(circle.y * scaleY);
      extras.r = Math.round(circle.r * Math.max(scaleX, scaleY));
    }

    handleImageUpload(selectedFile, extras);
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
          <div style={{ position: 'relative', display: 'inline-block' }}>
            <img
              src={previewSrc}
              alt="Pré-visualização"
              className="preview-image"
              ref={imgRef}
            />
            {advanced && (
              <canvas
                ref={canvasRef}
                className="draw-canvas"
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
              />
            )}
          </div>
        </div>
      )}

      <button
        type="button"
        className="btn"
        onClick={() => setAdvanced(a => !a)}
        disabled={processando}
      >
        {advanced ? 'Ocultar Avançado' : '⚙️ Análise Avançada'}
      </button>

      {advanced && (
        <div className="advanced-options">
          <p className="draw-hint">Clique no centro da placa e arraste para a borda para definir a ROI.</p>
          <label>
            Área mínima <span className="help-icon" title="Tamanho mínimo da colônia em pixels">!</span>:
            <input
              type="number"
              step="0.1"
              value={areaMin}
              onChange={e => setAreaMin(e.target.value)}
              className="text-input"
            />
          </label>
          <label>
            Circularidade mínima <span className="help-icon" title="0 = formato irregular, 1 = círculo perfeito">!</span>:
            <input
              type="number"
              step="0.01"
              value={circularidadeMin}
              onChange={e => setCircularidadeMin(e.target.value)}
              className="text-input"
            />
          </label>
          <label>
            Fator máximo do raio <span className="help-icon" title="Limite superior do raio de uma colônia em relação ao raio da placa">!</span>:
            <input
              type="number"
              step="0.01"
              value={maxSizeFactor}
              onChange={e => setMaxSizeFactor(e.target.value)}
              className="text-input"
            />
          </label>
        </div>
      )}

      {mensagemErroUI && (
        <div className="error-message">
          <strong>Erro:</strong> {mensagemErroUI}
        </div>
      )}

      {!processando && (
        <>
          <button
            onClick={() => fileInputRef.current?.click()}
            className="btn"
            disabled={processando}
          >
            📁 Selecionar Imagem
          </button>
          {selectedFile && (
            <button onClick={handleProcessar} className="btn" disabled={processando}>
              🚀 Processar
            </button>
          )}
        </>
      )}
    </>
  );
}

export default UploadSection;
