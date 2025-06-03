import React from 'react';

function ErrorMessage({ message, onClose }) {
  if (!message) return null;

  const style = {
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

  return (
    <div style={style} role="alert" aria-live="assertive">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span><strong>Erro:</strong> {message}</span>
        {onClose && (
          <button
            onClick={onClose}
            style={{
              marginLeft: 10,
              background: 'none',
              border: 'none',
              color: '#fff',
              cursor: 'pointer',
              fontWeight: 'bold',
            }}
            aria-label="Fechar mensagem de erro"
          >
            ✖
          </button>
        )}
      </div>
    </div>
  );
}

export default ErrorMessage;
