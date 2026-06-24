import { Link, useLocation } from 'react-router-dom';

function Navbar({ namespaces, onReset }) {
  const location = useLocation();

  const links = [
    { path: '/', label: 'Overview' },
    { path: '/namespace', label: 'Namespace Dive' },
    { path: '/forecast', label: 'Forecast' },
    { path: '/budget', label: 'Budget Alerts' },
    { path: '/backtest', label: 'Backtest' },
  ];

  return (
    <nav style={{
      backgroundColor: '#ffffff',
      padding: '16px 32px',
      display: 'flex',
      alignItems: 'center',
      gap: '32px',
      borderBottom: '1px solid #0f172a'
    }}>
      <span style={{
        fontWeight: '800', fontSize: '18px',
        color: '#e11d48', marginRight: '16px',
        letterSpacing: '0.5px'
      }}>
        K8s Cost Dashboard
      </span>

      {links.map(link => (
        <Link
          key={link.path}
          to={link.path}
          style={{
            color: location.pathname === link.path ? '#fb7185' : '#64748b',
            fontWeight: location.pathname === link.path ? '600' : '400',
            fontSize: '14px',
            borderBottom: location.pathname === link.path ? '2px solid #e11d48' : '2px solid transparent',
            paddingBottom: '4px',
            transition: 'color 0.2s'
          }}
        >
          {link.label}
        </Link>
      ))}

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Change Data Button */}
      <button
        onClick={onReset}
        style={{
          backgroundColor: 'transparent',
          border: '1px solid #0f172a',
          color: '#64748b',
          padding: '6px 16px',
          borderRadius: '8px',
          fontSize: '13px',
          cursor: 'pointer',
          transition: 'all 0.2s'
        }}
        onMouseOver={e => {
          e.target.style.borderColor = '#e11d48';
          e.target.style.color = '#e11d48';
        }}
        onMouseOut={e => {
          e.target.style.borderColor = '#0f172a';
          e.target.style.color = '#64748b';
        }}
      >
        Change Data
      </button>
    </nav>
  );
}

export default Navbar;