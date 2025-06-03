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

function ProgressBar({ processando, statusMensagem, uploadProgress, onCancel }) {
  if (!processando) return null;

  return (
    <div style={{ marginTop: 20, padding: 15, backgroundColor: 'rgba(50,50,50,0.8)', borderRadius: 8, maxWidth: 400, margin: '10px auto' }}>
      <p style={{fontSize: 16, fontWeight: 'bold', marginBottom: 10}}>{statusMensagem}</p>
      {uploadProgress > 0 && uploadProgress < 100 && (
        <div style={{ width: '100%', backgroundColor: '#555', borderRadius: 4, overflow: 'hidden', border: '1px solid #777', marginBottom: 10 }}>
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
      {uploadProgress === 100 && statusMensagem.includes('Aguarde, processando') && (
        <div style={{ width: '100%', backgroundColor: '#555', borderRadius: 4, overflow: 'hidden', border: '1px solid #777', marginBottom: 10 }}>
          <div
            style={{
              width: '100%',
              height: '20px',
              backgroundColor: '#2a782c',
              textAlign: 'center',
              lineHeight: '20px',
              color: 'white'
            }}
          >
            Enviado!
          </div>
        </div>
      )}
      <button
        onClick={onCancel}
        style={{...botaoEstilo, backgroundColor: '#c00', padding: '8px 15px', fontSize: '0.9em'}}
      >
        Cancelar
      </button>
    </div>
  );
}

export default ProgressBar;
