import { useState, useEffect } from 'react';

function getStatus(forecast, budget) {
  const ratio = forecast / budget;
  if (ratio >= 1.00)    return { label: 'Over Budget', color: '#e11d48', bg: '#fff1f2' };
  if (ratio >= 0.85) return { label: 'At Risk',     color: '#facc15', bg: '#fffbeb' };
  return               { label: 'On Track',         color: '#34d399', bg: '#f0fdf4' };
}

function BudgetAlerts({ namespaces }) {
  const [forecasts, setForecasts] = useState(null);
  const [budgets, setBudgets] = useState({});
  const [editing, setEditing] = useState(null);
  const [tempValue, setTempValue] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch('http://127.0.0.1:8000/budget-forecasts').then(r => r.json()),
      fetch('http://127.0.0.1:8000/budgets').then(r => r.json())
    ]).then(([forecastData, budgetData]) => {
      if (forecastData.forecasts) {
        setForecasts(forecastData.forecasts);
        
        // Use saved budgets if they exist, otherwise default to 90% of forecast
        const savedBudgets = budgetData.budgets || {};
        const defaultBudgets = {};
        Object.entries(forecastData.forecasts).forEach(([ns, cost]) => {
          defaultBudgets[ns] = savedBudgets[ns] ?? round(cost * 0.9);
        });
        setBudgets(defaultBudgets);
      }
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  function round(v) { return Math.round(v * 100) / 100; }

  function startEdit(ns) {
    setEditing(ns);
    setTempValue(String(budgets[ns]));
  }

  function commitEdit(ns) {
    const val = parseFloat(tempValue);
    if (!isNaN(val) && val > 0) {
      const newBudgets = { ...budgets, [ns]: val };
      setBudgets(newBudgets);
      
      // Save to backend
      fetch('http://127.0.0.1:8000/budgets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ budgets: newBudgets })
      });
    }
    setEditing(null);
  }

  if (loading) return (
    <div style={{ padding: '32px', color: '#64748b' }}>
      Running Linear Trend forecasts for all namespaces — this may take a minute...
    </div>
  );

  if (!forecasts) return (
    <div style={{ padding: '32px', color: '#e11d48' }}>Failed to load forecasts.</div>
  );

  const nsList = Object.keys(forecasts);
  const overCount = nsList.filter(ns => forecasts[ns] >= budgets[ns]).length;
  const riskCount = nsList.filter(ns => {
    const r = forecasts[ns] / budgets[ns];
    return r >= 0.85 && r < 1;
  }).length;
  const safeCount = nsList.length - overCount - riskCount;

  return (
    <div style={{ padding: '32px' }}>
      <h1 style={{ fontSize: '22px', fontWeight: '700', marginBottom: '8px' }}>
        Budget Alerts
      </h1>
      <p style={{ color: '#64748b', fontSize: '13px', marginBottom: '24px' }}>
        Forecasts powered by Linear Trend. Default budgets set to 90% of forecast — click any budget to edit.
      </p>

      {/* Summary Cards */}
      <div style={{ display: 'flex', gap: '16px', marginBottom: '32px', flexWrap: 'wrap' }}>
        {[
          { label: 'Over Budget', value: overCount,  color: '#e11d48' },
          { label: 'At Risk',     value: riskCount,  color: '#facc15' },
          { label: 'On Track',    value: safeCount,  color: '#34d399' },
        ].map(card => (
          <div key={card.label} style={{
            flex: 1, minWidth: '160px',
            backgroundColor: '#ffffff',
            border: `1px solid ${card.color}33`,
            borderRadius: '12px', padding: '20px',
            textAlign: 'center'
          }}>
            <p style={{ fontSize: '13px', color: '#64748b', marginBottom: '8px' }}>{card.label}</p>
            <p style={{ fontSize: '36px', fontWeight: '800', color: card.color }}>{card.value}</p>
            <p style={{ fontSize: '12px', color: '#64748b' }}>namespaces</p>
          </div>
        ))}
      </div>

      {/* Table */}
      <div style={{
        backgroundColor: '#ffffff',
        border: '1px solid #0f172a',
        borderRadius: '12px', overflow: 'hidden'
      }}>
        {/* Header */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '2fr 1fr 1fr 1fr 1fr',
          padding: '14px 24px',
          borderBottom: '1px solid #0f172a',
          backgroundColor: '#f8fafc'
        }}>
          {['Namespace', 'SARIMA Forecast', 'Budget', 'Difference', 'Status'].map(h => (
            <span key={h} style={{
              fontSize: '12px', color: '#64748b',
              fontWeight: '600', textTransform: 'uppercase',
              letterSpacing: '0.5px'
            }}>{h}</span>
          ))}
        </div>

        {/* Rows */}
        {nsList.map((ns, i) => {
          const forecast = forecasts[ns];
          const budget   = budgets[ns] ?? 0;
          const diff     = round(forecast - budget);
          const status   = getStatus(forecast, budget);

          return (
            <div key={ns} style={{
              display: 'grid',
              gridTemplateColumns: '2fr 1fr 1fr 1fr 1fr',
              padding: '16px 24px',
              alignItems: 'center',
              borderBottom: i < nsList.length - 1 ? '1px solid #f8fafc' : 'none',
              backgroundColor: status.bg,
              transition: 'background 0.2s'
            }}>
              <span style={{ fontSize: '14px', fontWeight: '500' }}>{ns}</span>
              <span style={{ fontSize: '14px', color: '#fb7185' }}>${forecast.toFixed(2)}</span>

              {editing === ns ? (
                <input
                  autoFocus
                  value={tempValue}
                  onChange={e => setTempValue(e.target.value)}
                  onBlur={() => commitEdit(ns)}
                  onKeyDown={e => e.key === 'Enter' && commitEdit(ns)}
                  style={{
                    width: '80px', padding: '4px 8px',
                    backgroundColor: '#f8fafc',
                    border: '1px solid #e11d48',
                    borderRadius: '6px', color: '#0f172a',
                    fontSize: '14px', outline: 'none'
                  }}
                />
              ) : (
                <span
                  onClick={() => startEdit(ns)}
                  style={{
                    fontSize: '14px', cursor: 'pointer',
                    color: '#0f172a',
                    textDecoration: 'underline dotted #64748b'
                  }}
                  title="Click to edit"
                >
                  ${budget.toFixed(2)}
                </span>
              )}

              <span style={{
                fontSize: '14px',
                color: diff > 0 ? '#e11d48' : '#34d399',
                fontWeight: '600'
              }}>
                {diff > 0 ? '+' : ''}{diff.toFixed(2)}
              </span>

              <span style={{
                fontSize: '12px', fontWeight: '600',
                color: status.color,
                backgroundColor: `${status.color}22`,
                padding: '4px 10px', borderRadius: '20px',
                display: 'inline-block'
              }}>
                {status.label}
              </span>
            </div>
          );
        })}
      </div>

      <p style={{ fontSize: '12px', color: '#64748b', marginTop: '12px' }}>
        💡 Click any budget value to edit it. Changes update status instantly.
      </p>
    </div>
  );
}

export default BudgetAlerts;