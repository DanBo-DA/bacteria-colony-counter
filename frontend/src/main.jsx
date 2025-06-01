import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';
// Forçando novo deploy para quebrar cache persistente.
console.log('Versão 2 do main.jsx carregada.');

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
