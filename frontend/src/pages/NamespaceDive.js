import { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

function EfficiencyBar({ label, value }) {
  const percent = Math.round(value * 100);
  const color = percent >= 70 ? '#34d399' : percent >= 30 ? '#facc15' : '#e11d48';
  return (
    <div style={{ marginBottom: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
        <span style={{ fontSize: '13px', color: '#64748b' }}>{label}</span>
        <span style={{ fontSize: '13px', fontWeight: '600', color }}>{percent}%</span>
      </div>
      <div style={{ backgroundColor: '#e2e8f0', borderRadius: '4px', height: '8px' }}>
        <div style={{
          width: `${percent}%`, height: '8px',
          backgroundColor: color, borderRadius: '4px',
          transition: 'width 0.5s ease'
        }} />
      </div>
    </div>
  );
}

function NamespaceDive({ namespaces }) {
  const [selected, setSelected] = useState(namespaces?.[0] || '');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (namespaces && namespaces.length > 0) {
      setSelected(namespaces[0]);
      setData(null);
    }
  }, [namespaces]);

  useEffect(() => {
    if (!selected) return;
    setLoading(true);
    fetch(`http://127.0.0.1:8000/namespace/${selected}`)
      .then(res => res.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [selected]);

  const chartData = data ? [
    { name: 'CPU',     cost: data.cpu_cost },
    { name: 'RAM',     cost: data.ram_cost },
    { name: 'Storage', cost: data.storage_cost },
  ] : [];

  return (
    <div style={{ padding: '32px' }}>
      <h1 style={{ fontSize: '22px', fontWeight: '700', marginBottom: '24px' }}>
        Namespace Deep Dive
      </h1>

      <select
        value={selected}
        onChange={e => setSelected(e.target.value)}
        style={{
          backgroundColor: '#ffffff',
          border: '1px solid #0f172a',
          color: '#0f172a', padding: '10px 16px',
          borderRadius: '8px', fontSize: '14px',
          marginBottom: '28px', cursor: 'pointer', outline: 'none'
        }}
      >
        {namespaces?.map(ns => <option key={ns} value={ns}>{ns}</option>)}
      </select>

      {loading && <p style={{ color: '#64748b' }}>Loading...</p>}

      {data && !loading && (
        <>
          <div style={{ display: 'flex', gap: '16px', marginBottom: '16px', flexWrap: 'wrap' }}>

            {/* Cost Breakdown Chart — real data from API */}
            <div style={{
              flex: 2, minWidth: '280px',
              backgroundColor: '#ffffff',
              border: '1px solid #0f172a',
              borderRadius: '12px', padding: '24px'
            }}>
              <h2 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '20px', color: '#64748b' }}>
                Cost Breakdown (USD)
              </h2>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#0f172a" />
                  <XAxis dataKey="name" stroke="#64748b" fontSize={12} />
                  <YAxis stroke="#64748b" fontSize={12} tickFormatter={v => `$${v}`} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#ffffff', border: '1px solid #0f172a', borderRadius: '8px' }}
                    formatter={v => [`$${v}`, 'Cost']}
                  />
                  <Bar dataKey="cost" fill="#e11d48" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Efficiency + Stats */}
            <div style={{
              flex: 1, minWidth: '240px',
              backgroundColor: '#ffffff',
              border: '1px solid #0f172a',
              borderRadius: '12px', padding: '24px'
            }}>
              <h2 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '20px', color: '#64748b' }}>
                Resource Efficiency
              </h2>
              <EfficiencyBar label="CPU Efficiency" value={data.cpu_efficiency} />
              <EfficiencyBar label="RAM Efficiency" value={data.ram_efficiency} />
              <div style={{ marginTop: '24px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '13px', color: '#64748b' }}>Avg Pods</span>
                  <span style={{ fontSize: '13px', fontWeight: '600' }}>{data.avg_pods}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '13px', color: '#64748b' }}>30-Day Forecast</span>
                  <span style={{ fontSize: '13px', fontWeight: '600', color: '#e11d48' }}>{data.forecast_30d}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Recommendation */}
          <div style={{
            backgroundColor: '#ffffff',
            border: '1px solid #0f172a',
            borderLeft: '4px solid #e11d48',
            borderRadius: '12px', padding: '20px'
          }}>
            <h2 style={{ fontSize: '14px', fontWeight: '600', marginBottom: '8px', color: '#fb7185' }}>
              Right-Sizing Recommendation
            </h2>
            <p style={{ fontSize: '14px', color: '#64748b', lineHeight: '1.6' }}>
              {data.recommendation}
            </p>
          </div>
        </>
      )}
    </div>
  );
}

export default NamespaceDive;