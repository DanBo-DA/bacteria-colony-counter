import React from 'react';

function ProgressBar({ processando, statusMensagem, uploadProgress, onCancel }) {
  if (!processando) return null;

  return (
    <div className="progress-container">
      <p className="status-message">{statusMensagem}</p>
      {uploadProgress > 0 && uploadProgress < 100 && (
        <div className="progress-bar-wrapper">
          <div
            className="progress-bar"
            style={{ width: `${uploadProgress}%` }}
          >
            {uploadProgress}%
          </div>
        </div>
      )}
      {uploadProgress === 100 && statusMensagem.includes('Aguarde, processando') && (
        <div className="progress-bar-wrapper">
          <div className="progress-bar progress-complete">Enviado!</div>
        </div>
      )}
      <button onClick={onCancel} className="btn btn-danger">Cancelar</button>
    </div>
  );
}

export default ProgressBar;
