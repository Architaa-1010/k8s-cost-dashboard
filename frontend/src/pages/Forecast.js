import { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

function ToggleButton({ label, active, onClick }) {
  return (
    <button onClick={onClick} style={{
      padding: '8px 20px', borderRadius: '8px', border: 'none',
      cursor: 'pointer', fontSize: '13px',
      fontWeight: active ? '600' : '400',
      backgroundColor: active ? '#e11d48' : '#f1f5f9',
color: active ? '#fff' : '#64748b',
      transition: 'all 0.2s'
    }}>
      {label}
    </button>
  );
}

function Forecast({ namespaces }) {
  const [namespace, setNamespace] = useState(namespaces?.[0] || '');
  const [model, setModel] = useState('SARIMA');
  const [metric, setMetric] = useState('cost');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!namespace) return;
    setLoading(true);
    setError(null);
    setData(null);

    let url;
    if (model === 'SARIMA' && metric === 'cost') {
      url = `http://127.0.0.1:8000/forecast/sarima/${namespace}`;
    } else if (model === 'SARIMA' && metric === 'pods') {
      url = `http://127.0.0.1:8000/forecast/sarima-pods/${namespace}`;
    } else if (model === 'Prophet' && metric === 'cost') {
      url = `http://127.0.0.1:8000/forecast/prophet/${namespace}`;
    } else {
      url = `http://127.0.0.1:8000/forecast/prophet-pods/${namespace}`;
    }
    fetch(url)
      .then(res => res.json())
      .then(d => {
        if (d.error) { setError(d.error); setLoading(false); return; }
        setData(d);
        setLoading(false);
      })
      .catch(() => { setError('Failed to connect to backend.'); setLoading(false); });
  }, [namespace, model, metric]);

  const splitDay = data ? data.historical[data.historical.length - 1]?.day : null;

  const combined = data ? [
    ...data.historical.map(d => ({ day: d.day, historical: d.value })),
    ...data.forecast.slice(1).map(d => ({ day: d.day, forecast: d.value })),
  ] : [];

  return (
    <div style={{ padding: '32px' }}>
      <h1 style={{ fontSize: '22px', fontWeight: '700', marginBottom: '24px' }}>Forecast</h1>

      {/* Controls */}
      <div style={{ display: 'flex', gap: '16px', marginBottom: '28px', flexWrap: 'wrap', alignItems: 'center' }}>
        <select
          value={namespace}
          onChange={e => setNamespace(e.target.value)}
          style={{
            backgroundColor: '#ffffff',
            border: '1px solid #0f172a',
            color: '#0f172a', padding: '10px 16px',
            borderRadius: '8px', fontSize: '14px',
            cursor: 'pointer', outline: 'none'
          }}
        >
          {namespaces?.map(ns => <option key={ns} value={ns}>{ns}</option>)}
        </select>

        <div style={{ display: 'flex', gap: '8px' }}>
          <ToggleButton label="SARIMA" active={model === 'SARIMA'} onClick={() => setModel('SARIMA')} />
          <ToggleButton label="Prophet" active={model === 'Prophet'} onClick={() => setModel('Prophet')} />
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <ToggleButton label="Cost" active={metric === 'cost'} onClick={() => setMetric('cost')} />
          <ToggleButton label="Pod Count" active={metric === 'pods'} onClick={() => setMetric('pods')} />
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div style={{
          backgroundColor: '#ffffff',
          border: '1px solid #0f172a',
          borderRadius: '12px', padding: '48px',
          textAlign: 'center', color: '#64748b'
        }}>
          {model === 'SARIMA' ? 'Running SARIMA model... this may take a few seconds' : 'Running Prophet model... this may take a few seconds'}
        </div>
      )}

      {error && <p style={{ color: '#e11d48' }}>{error}</p>}

      {data && !loading && (
        <>
          {/* Chart */}
          <div style={{
            backgroundColor: '#ffffff',
            border: '1px solid #0f172a',
            borderRadius: '12px', padding: '24px', marginBottom: '24px'
          }}>
            <h2 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '20px', color: '#64748b' }}>
              {namespace} — {model} Cost Forecast (Next 30 Days)
            </h2>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={combined}>
                <CartesianGrid strokeDasharray="3 3" stroke="#0f172a" />
                <XAxis dataKey="day" stroke="#64748b" fontSize={12}
                  label={{ value: 'Day Index', position: 'insideBottom', offset: -2, fill: '#64748b', fontSize: 12 }} />
                <YAxis stroke="#64748b" fontSize={12} tickFormatter={v => metric === 'cost' ? `$${v}` : v} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#ffffff', border: '1px solid #0f172a', borderRadius: '8px' }}
                  formatter={(v, name) => [metric === 'cost' ? `$${v}` : v, name]}
                />
                <ReferenceLine x={splitDay} stroke="#fb7185" strokeDasharray="4 4"
                  label={{ value: 'Forecast Start', fill: '#fb7185', fontSize: 11 }} />
                <Line type="monotone" dataKey="historical" stroke="#e11d48" strokeWidth={2} dot={false} name="Historical" />
                <Line type="monotone" dataKey="forecast" stroke="#fb7185" strokeWidth={2} strokeDasharray="5 5" dot={false} name="Forecast" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Weekly + Monthly */}
          <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
            <div style={{
              flex: 2, minWidth: '280px',
              backgroundColor: '#ffffff',
              border: '1px solid #0f172a',
              borderRadius: '12px', padding: '24px'
            }}>
              <h2 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '16px', color: '#64748b' }}>
                Weekly Breakdown
              </h2>
              {data.weekly.map((val, i) => (
                <div key={i} style={{
                  display: 'flex', justifyContent: 'space-between',
                  padding: '12px 0',
                  borderBottom: i < 3 ? '1px solid #0f172a' : 'none'
                }}>
                  <span style={{ fontSize: '14px', color: '#64748b' }}>Week {i + 1}</span>
                  <span style={{ fontSize: '14px', fontWeight: '600', color: '#fb7185' }}>{val}</span>
                </div>
              ))}
            </div>

            <div style={{
              flex: 1, minWidth: '200px',
              backgroundColor: '#ffffff',
              border: '1px solid #0f172a',
              borderRadius: '12px', padding: '24px',
              display: 'flex', flexDirection: 'column',
              justifyContent: 'center', alignItems: 'center'
            }}>
              <p style={{ fontSize: '13px', color: '#64748b', marginBottom: '12px' }}>30-Day Total Forecast</p>
              <p style={{ fontSize: '42px', fontWeight: '800', color: '#e11d48' }}>{data.monthly}</p>
              <p style={{ fontSize: '12px', color: '#64748b', marginTop: '8px' }}>{model} model</p>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default Forecast;