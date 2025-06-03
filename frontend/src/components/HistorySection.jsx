import React from 'react';

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
    <div className="history-container">
      <h3>📋 Histórico de Análises</h3>
      <div className="history-actions">
        <button onClick={selecionarTodos} className="btn" disabled={processando}>
          {todosSelecionados ? '☑️ Desmarcar Todos' : '✅ Selecionar Todos'}
        </button>
        <button onClick={exportarCSV} className="btn" disabled={processando}>⬇️ Exportar Selecionados</button>
        <button onClick={excluirTodos} className="btn" disabled={processando}>🗑️ Excluir Tudo</button>
      </div>
      <table className="history-table">
        <thead>
          <tr>
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
            <tr key={idx} className={idx % 2 === 0 ? 'row-even' : 'row-odd'}>
              <td><input type="checkbox" checked={!!selecionados[idx]} onChange={() => toggleSelecionado(idx)} disabled={processando} /></td>
              <td>{item.data}</td>
              <td>{item.hora}</td>
              <td>{item.nomeAmostra}</td>
              <td>{item.TOTAL}</td>
              <td>{item.densidadecoloniascm2}</td>
              <td>{item.estimativatotalcolonias}</td>
              <td><button onClick={() => excluirEntrada(idx)} className="delete-btn" disabled={processando}>Excluir</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default HistorySection;
