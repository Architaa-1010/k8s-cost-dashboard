import { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { DollarSign, Layers, TrendingUp, AlertTriangle } from 'lucide-react';

const namespaceColors = {
  'production-api': '#e11d48',
  'ml-training':    '#fb7185',
  'kafka':          '#f97316',
  'postgres-db':    '#facc15',
  'ingress-nginx':  '#a78bfa',
  'staging':        '#38bdf8',
  'kube-system':    '#34d399',
  'prometheus':     '#f472b6',
  'opencost':       '#64748b',
};

function StatCard({ label, value, sub, icon: Icon }) {
  return (
    <div style={{
      backgroundColor: '#ffffff',
      border: '1px solid #0f172a',
      borderRadius: '12px', padding: '24px',
      flex: 1, minWidth: '180px',
      display: 'flex', flexDirection: 'column', gap: '8px'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <p style={{ color: '#64748b', fontSize: '13px' }}>{label}</p>
        {Icon && <Icon size={18} color="#e11d48" />}
      </div>
      <p style={{ color: '#0f172a', fontSize: '28px', fontWeight: '700' }}>{value}</p>
      {sub && <p style={{ color: '#e11d48', fontSize: '12px' }}>{sub}</p>}
    </div>
  );
}

function Overview() {
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('http://127.0.0.1:8000/overview')
      .then(res => res.json())
      .then(d => { setOverview(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ padding: '32px', color: '#64748b' }}>Loading...</div>;
  if (!overview) return <div style={{ padding: '32px', color: '#e11d48' }}>Failed to load data.</div>;

  // Build per-namespace trend lines from flat trend data
  const trendByDate = {};
  overview.trend.forEach(({ date, cost }) => {
    trendByDate[date] = { date, total: cost };
  });
  const trendData = Object.values(trendByDate).map(d => ({
    date: d.date.slice(5), // show MM-DD only
    total: d.total
  }));

  return (
    <div style={{ padding: '32px' }}>
      <h1 style={{ fontSize: '22px', fontWeight: '700', marginBottom: '24px' }}>
        Cluster Overview
      </h1>

      {/* Stat Cards */}
      <div style={{ display: 'flex', gap: '16px', marginBottom: '32px', flexWrap: 'wrap' }}>
        <StatCard
          label="Total Cost (90 Days)"
          value={`$${overview.total_cost}`}
          icon={DollarSign}
        />
        <StatCard
          label="Active Namespaces"
          value={overview.namespace_count}
          icon={Layers}
        />
        <StatCard
          label="Avg Daily Cost"
          value={`$${overview.avg_daily_cost}`}
          icon={TrendingUp}
        />
        <StatCard
          label="Forecasted Month End"
          value={`$${overview.forecast_month_end}`}
          sub="↑ Based on linear trend"
          icon={AlertTriangle}
        />
      </div>

      {/* Cost Trend Chart */}
      <div style={{
        backgroundColor: '#ffffff',
        border: '1px solid #0f172a',
        borderRadius: '12px', padding: '24px',
        marginBottom: '32px'
      }}>
        <h2 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '20px', color: '#64748b' }}>
          Total Daily Cost Trend
        </h2>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={trendData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#0f172a" />
            <XAxis dataKey="date" stroke="#64748b" fontSize={11} interval={6} />
            <YAxis stroke="#64748b" fontSize={12} tickFormatter={v => `$${v}`} />
            <Tooltip
              contentStyle={{ backgroundColor: '#ffffff', border: '1px solid #0f172a', borderRadius: '8px' }}
              formatter={v => [`$${v}`, 'Total Cost']}
            />
            <Line type="monotone" dataKey="total" stroke="#e11d48" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Bottom Two Tables */}
      <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
        <div style={{
          flex: 1, minWidth: '280px',
          backgroundColor: '#ffffff',
          border: '1px solid #0f172a',
          borderRadius: '12px', padding: '24px'
        }}>
          <h2 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '16px', color: '#64748b' }}>
            Top 3 Most Expensive
          </h2>
          {overview.most_expensive.map((n, i) => (
            <div key={n.name} style={{
              display: 'flex', justifyContent: 'space-between',
              padding: '12px 0',
              borderBottom: i < 2 ? '1px solid #0f172a' : 'none'
            }}>
              <span style={{ fontSize: '14px' }}>{n.name}</span>
              <span style={{ color: '#e11d48', fontWeight: '600' }}>{n.cost}</span>
            </div>
          ))}
        </div>

        <div style={{
          flex: 1, minWidth: '280px',
          backgroundColor: '#ffffff',
          border: '1px solid #0f172a',
          borderRadius: '12px', padding: '24px'
        }}>
          <h2 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '16px', color: '#64748b' }}>
            Top 3 Most Wasteful
          </h2>
          {overview.most_wasteful.map((n, i) => (
            <div key={n.name} style={{
              display: 'flex', justifyContent: 'space-between',
              padding: '12px 0',
              borderBottom: i < 2 ? '1px solid #0f172a' : 'none'
            }}>
              <span style={{ fontSize: '14px' }}>{n.name}</span>
              <span style={{ color: '#fb7185', fontWeight: '600' }}>{n.efficiency} efficiency</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default Overview;