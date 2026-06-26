import { useState, useEffect } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend, ReferenceLine
} from 'recharts';

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

function MetricCard({ label, value, sub, color }) {
  return (
    <div style={{
      flex: 1, minWidth: '160px',
      backgroundColor: '#ffffff',
      border: `1px solid ${color}44`,
      borderRadius: '12px', padding: '20px',
      textAlign: 'center'
    }}>
      <p style={{ fontSize: '13px', color: '#64748b', marginBottom: '8px' }}>{label}</p>
      <p style={{ fontSize: '28px', fontWeight: '800', color }}>{value}</p>
      {sub && <p style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>{sub}</p>}
    </div>
  );
}

function Backtest({ namespaces = [] }) {
  const [namespace, setNamespace] = useState('');
  const [model, setModel] = useState('sarima');
  const [metric, setMetric] = useState('cost');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(namespaces?.[0] || '');

  useEffect(() => {
    if (namespaces && namespaces.length > 0) {
      setSelected(namespaces[0]);
      setData(null);
    }
  }, [namespaces]);

  // Set first namespace once namespaces loads
  useEffect(() => {
    if (namespaces.length > 0 && !namespace) {
      setNamespace(namespaces[0]);
    }
  }, [namespaces]);

  useEffect(() => {
    if (!namespace) return;
    setLoading(true);
    setError(null);
    setData(null);

    fetch(`http://127.0.0.1:8000/backtest/${namespace}?model=${model}&metric=${metric}`)
      .then(res => res.json())
      .then(d => {
        if (d.error) { setError(d.error); setLoading(false); return; }
        setData(d);
        setLoading(false);
      })
      .catch(() => { setError('Failed to connect to backend.'); setLoading(false); });
  }, [namespace, model, metric]);

  const chartData = (data && data.train_data && data.comparison) ? [
    ...data.train_data.map(d => ({ day: d.day, actual: d.actual })),
    ...data.comparison.map(d => ({ day: d.day, actual: d.actual, predicted: d.predicted }))
  ] : [];

  const splitDay = (data && data.train_data && data.train_data.length > 0)
    ? data.train_data[data.train_data.length - 1]?.day
    : null;

  

  const accuracyColor = (data && data.metrics)
    ? data.metrics.accuracy >= 90 ? '#34d399'
    : data.metrics.accuracy >= 75 ? '#facc15'
    : '#e11d48'
    : '#64748b';

  if (namespaces.length === 0) {
    return <div style={{ padding: '32px', color: '#64748b' }}>Loading namespaces...</div>;
  }

  return (
    <div style={{ padding: '32px' }}>
      <h1 style={{ fontSize: '22px', fontWeight: '700', marginBottom: '8px' }}>
        Backtest — Model Accuracy
      </h1>
      <p style={{ color: '#64748b', fontSize: '13px', marginBottom: '24px' }}>
        Trained on days 1-60, tested on days 61-90. Compares forecast vs actual to measure accuracy.
      </p>

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
          {namespaces.map(ns => <option key={ns} value={ns}>{ns}</option>)}
        </select>

        <div style={{ display: 'flex', gap: '8px' }}>
          <ToggleButton label="SARIMA" active={model === 'sarima'} onClick={() => setModel('sarima')} />
          <ToggleButton label="Prophet" active={model === 'prophet'} onClick={() => setModel('prophet')} />
        </div>

        <div style={{ display: 'flex', gap: '8px' }}>
          <ToggleButton
            label="Cost"
            active={metric === 'cost'}
            onClick={() => setMetric('cost')}
          />
          <ToggleButton
            label="Pod Count"
            active={metric === 'podCount'}
            onClick={() => setMetric('podCount')}
          />
        </div>
      </div>

      {loading && (
        <div style={{
          backgroundColor: '#ffffff',
          border: '1px solid #0f172a',
          borderRadius: '12px', padding: '48px',
          textAlign: 'center', color: '#64748b'
        }}>
          Running backtest... this may take a few seconds
        </div>
      )}

      {error && <p style={{ color: '#e11d48' }}>{error}</p>}

      {data && !loading && (
        <>
          {/* Metric Cards */}
          <div style={{ display: 'flex', gap: '16px', marginBottom: '24px', flexWrap: 'wrap' }}>
            <MetricCard
              label="Accuracy"
              value={`${data.metrics?.accuracy}%`}
              sub="100% - MAPE"
              color={accuracyColor}
            />
            <MetricCard
              label="MAPE"
              value={`${data.metrics?.mape}%`}
              sub="Mean Absolute % Error"
              color="#fb7185"
            />
            <MetricCard
              label="RMSE"
              value={data.metrics?.rmse}
              sub="Root Mean Square Error"
              color="#a78bfa"
            />
            <MetricCard
              label="MAE"
              value={data.metrics?.mae}
              sub="Mean Absolute Error"
              color="#38bdf8"
            />
          </div>

          {/* Chart */}
          <div style={{
            backgroundColor: '#ffffff',
            border: '1px solid #0f172a',
            borderRadius: '12px', padding: '24px',
            marginBottom: '24px'
          }}>
            <h2 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '8px', color: '#64748b' }}>
              Actual vs Predicted — {namespace} ({data.model})
            </h2>
            <p style={{ fontSize: '12px', color: '#64748b', marginBottom: '20px' }}>
              Left of dotted line: training data. Right: model predicted vs what actually happened.
            </p>
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#0f172a" />
                <XAxis dataKey="day" stroke="#64748b" fontSize={12}
                  label={{ value: 'Day Index', position: 'insideBottom', offset: -2, fill: '#64748b', fontSize: 12 }} />
                <YAxis stroke="#64748b" fontSize={12} tickFormatter={v => `$${v}`} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#ffffff', border: '1px solid #0f172a', borderRadius: '8px' }}
                  formatter={(v, name) => [`$${v}`, name]}
                />
                <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '16px' }} />
                <ReferenceLine x={splitDay} stroke="#fb7185" strokeDasharray="4 4"
                  label={{ value: 'Test Start', fill: '#fb7185', fontSize: 11 }} />
                <Line type="monotone" dataKey="actual" stroke="#e11d48" strokeWidth={2} dot={false} name="Actual" />
                <Line type="monotone" dataKey="predicted" stroke="#34d399" strokeWidth={2} strokeDasharray="5 5" dot={false} name="Predicted" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Interpretation */}
          <div style={{
            backgroundColor: '#ffffff',
            border: '1px solid #0f172a',
            borderLeft: '4px solid #e11d48',
            borderRadius: '12px', padding: '20px'
          }}>
            <h2 style={{ fontSize: '14px', fontWeight: '600', marginBottom: '8px', color: '#fb7185' }}>
              Interpretation
            </h2>
            <p style={{ fontSize: '14px', color: '#64748b', lineHeight: '1.6' }}>
              {data.metrics?.accuracy >= 90
                ? `${data.model} achieves ${data.metrics?.accuracy}% accuracy on ${namespace} — excellent forecasting performance. The model successfully captured the cost trends and weekly seasonality patterns.`
                : data.metrics?.accuracy >= 75
                ? `${data.model} achieves ${data.metrics?.accuracy}% accuracy on ${namespace} — good performance. Some variance exists but the model captures the general trend.`
                : `${data.model} achieves ${data.metrics?.accuracy}% accuracy on ${namespace} — this namespace may have irregular patterns that are difficult to forecast. Consider using a longer training window.`
              }
            </p>
          </div>
        </>
      )}
    </div>
  );
}

export default Backtest;