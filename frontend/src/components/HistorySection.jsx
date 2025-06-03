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

function HistorySection({
  logAnalises,
  selecionados,
  todosSelecionados,
  selecionarTodos,
  toggleSelecionado,
  exportarCSV,
  excluirEntrada,
  excluirTodos,
  processando,
}) {
  if (logAnalises.length === 0) return null;

  return (
    <div style={{ marginTop: 30 }}>
      <h3>📋 Histórico de Análises</h3>
      <div style={{ marginBottom: 10 }}>
        <button onClick={selecionarTodos} style={botaoEstilo} disabled={processando}>
          {todosSelecionados ? '☑️ Desmarcar Todos' : '✅ Selecionar Todos'}
        </button>
        <button onClick={exportarCSV} style={botaoEstilo} disabled={processando}>⬇️ Exportar Selecionados</button>
        <button onClick={excluirTodos} style={botaoEstilo} disabled={processando}>🗑️ Excluir Tudo</button>
      </div>
      <table style={{ width: '100%', marginTop: 10, borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ backgroundColor: '#222', color: '#ddd' }}>
            <th><input type="checkbox" onChange={selecionarTodos} checked={todosSelecionados} disabled={processando} /></th>
            <th>Data</th>
            <th>Hora</th>
            <th>Amostra</th>
            <th>Total</th>
            <th>Densidade</th>
            <th>Estimativa</th>
            <th>Ações</th>
          </tr>
        </thead>
        <tbody>
          {logAnalises.map((item, idx) => (
            <tr key={idx} style={{ backgroundColor: idx % 2 === 0 ? '#1c1c1c' : '#2c2c2c' }}>
              <td><input type="checkbox" checked={!!selecionados[idx]} onChange={() => toggleSelecionado(idx)} disabled={processando} /></td>
              <td>{item.data}</td>
              <td>{item.hora}</td>
              <td>{item.nomeAmostra}</td>
              <td>{item.TOTAL}</td>
              <td>{item.densidadecoloniascm2}</td>
              <td>{item.estimativatotalcolonias}</td>
              <td><button onClick={() => excluirEntrada(idx)} style={{ fontSize: 11, backgroundColor: '#800', color: '#fff', border: 'none', padding: '4px 8px', borderRadius: 4, cursor: 'pointer' }} disabled={processando}>Excluir</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default HistorySection;
