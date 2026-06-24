import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import Overview from './pages/Overview';
import NamespaceDive from './pages/NamespaceDive';
import Forecast from './pages/Forecast';
import BudgetAlerts from './pages/BudgetAlerts';
import Backtest from './pages/Backtest';

function UploadScreen({ onUpload }) {
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [mode, setMode] = useState('file'); // 'file' or 'mongodb'
  const [apiForm,setApiForm] = useState({ api_url: '' });
  const [mongoForm, setMongoForm] = useState({
    connection_string: '',
    database: '',
    collection: ''
  });

  async function handleFile(file) {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch('http://127.0.0.1:8000/upload', {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (data.message) {
        onUpload(data);
      } else {
        setError('Upload failed. Check your file format.');
      }
    } catch (e) {
      setError('Could not connect to backend. Make sure it is running.');
    }
    setLoading(false);
  }

  async function handleMongoDB() {
    if (!mongoForm.connection_string || !mongoForm.database || !mongoForm.collection) {
      setError('Please fill in all fields.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('http://127.0.0.1:8000/connect-mongodb', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(mongoForm)
      });
      const data = await res.json();
      if (data.message) {
        onUpload(data);
      } else {
        setError(data.error || 'Connection failed.');
      }
    } catch (e) {
      setError('Could not connect to backend. Make sure it is running.');
    }
    setLoading(false);
  }

  async function handleAPI(){
    if(!apiForm.api_url){
      setError('Please enter an API URL.');
    }
    setLoading(true);
    setError(null);
    try{
      const res = await fetch('http://127.0.0.1:8000/connect-api', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json'},
        body: JSON.stringify(apiForm)
      });
      const data = await res.json();
      if(data.message){
        onUpload(data);
      } 
      else{
        setError(data.error || 'Connection failed.');
      }
    }catch (e){
      setError('Could not connect to backend. Make sure its running.');
    }
    setLoading(false);
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex',
      flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', padding: '32px'
    }}>
      <h1 style={{ fontSize: '28px', fontWeight: '800', color: '#e11d48', marginBottom: '8px' }}>
        K8s Cost Dashboard
      </h1>
      <p style={{ color: '#64748b', fontSize: '15px', marginBottom: '32px' }}>
        Connect your Kubecost data to get started
      </p>

      {/* Mode Toggle */}
      <div style={{
        display: 'flex', gap: '8px', marginBottom: '32px',
        backgroundColor: '#ffffff',
        border: '1px solid #0f172a',
        borderRadius: '10px', padding: '4px'
      }}>
        {[
          { key: 'file', label: '📂 Upload JSON'},
          { key: 'mongodb', label: '🍃 MongoDB Atlas'},
          { key: 'api', label: '🔗 API Endpoint'},

        ].map(m =>(
          <button 
          key={m.key}
          onClick={() => { setMode(m.key); setError(null); }}
          style={{
            padding: '8px 24px', borderRadius: '8px', border: 'none',
            cursor: 'pointer', fontSize: '13px',
            fontWeight: mode=== m.key ? '600' : '400',
            backgroundColor: mode === m.key ? '#e11d48' : 'transparent',
            color: mode === m.key ? '#fff' : '#64748b',
            transition: 'all 0.2s'
          }}>{m.label}

          </button>
        ))}
      </div>

      {/* File Upload */}
      {mode === 'file' && (
        <div
          onDragOver={e => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={e => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0]); }}
          style={{
            width: '100%', maxWidth: '480px',
            border: `2px dashed ${dragging ? '#e11d48' : '#0f172a'}`,
            borderRadius: '16px', padding: '48px 32px',
            textAlign: 'center',
            backgroundColor: dragging ? '#fff1f2' : '#ffffff',
            transition: 'all 0.2s', cursor: 'pointer'
          }}
          onClick={() => document.getElementById('fileInput').click()}
        >
          <p style={{ fontSize: '40px', marginBottom: '16px' }}>📂</p>
          <p style={{ fontSize: '15px', color: '#0f172a', marginBottom: '8px' }}>
            Drag & drop your Kubecost JSON file here
          </p>
          <p style={{ fontSize: '13px', color: '#64748b', marginBottom: '24px' }}>or click to browse</p>
          <input
            id="fileInput" type="file" accept=".json"
            style={{ display: 'none' }}
            onChange={e => handleFile(e.target.files[0])}
          />
          <div style={{
            display: 'inline-block', backgroundColor: '#e11d48',
            color: '#fff', fontSize: '13px', fontWeight: '600',
            padding: '10px 24px', borderRadius: '8px'
          }}>
            Choose File
          </div>
        </div>
      )}

      {/* MongoDB Form */}
      {mode === 'mongodb' && (
        <div style={{
          width: '100%', maxWidth: '480px',
          backgroundColor: '#ffffff',
          border: '1px solid #0f172a',
          borderRadius: '16px', padding: '32px',
          display: 'flex', flexDirection: 'column', gap: '16px'
        }}>
          {[
            { key: 'connection_string', label: 'Connection String', placeholder: 'mongodb+srv://user:pass@cluster.mongodb.net' },
            { key: 'database', label: 'Database Name', placeholder: 'kubecost' },
            { key: 'collection', label: 'Collection Name', placeholder: 'allocations' },
          ].map(field => (
            <div key={field.key}>
              <label style={{ fontSize: '13px', color: '#64748b', display: 'block', marginBottom: '6px' }}>
                {field.label}
              </label>
              <input
                type={field.key === 'connection_string' ? 'password' : 'text'}
                placeholder={field.placeholder}
                value={mongoForm[field.key]}
                onChange={e => setMongoForm(prev => ({ ...prev, [field.key]: e.target.value }))}
                style={{
                  width: '100%', padding: '10px 14px',
                  backgroundColor: '#f8fafc',
                  border: '1px solid #0f172a',
                  borderRadius: '8px', color: '#0f172a',
                  fontSize: '14px', outline: 'none',
                  boxSizing: 'border-box'
                }}
              />
            </div>
          ))}

          <button
            onClick={handleMongoDB}
            style={{
              backgroundColor: '#e11d48', color: '#fff',
              border: 'none', borderRadius: '8px',
              padding: '12px', fontSize: '14px',
              fontWeight: '600', cursor: 'pointer',
              marginTop: '8px'
            }}
          >
            Connect to MongoDB
          </button>

          <p style={{ fontSize: '12px', color: '#64748b', textAlign: 'center' }}>
            Your connection string is sent only to your local backend and never stored.
          </p>
        </div>
      )}

      {mode === 'api' && (
        <div style={{
          width: '100%', maxWidth: '480px',
          backgroundColor: '#f8fafc',
          border: '1px solid #e2e8f0',
          borderRadius: '16px', padding: '32px',
          display:'flex', flexDirection: 'column', gap:'16px'
        }}>
          <div>
            <label style={{ fontSize: '13px', color: '#64748b', display:'block', marginBottom: '6px'}}>
              API Endpoint URL
            </label>
            <input
              type="text"
              placeholder="https://your-company.com/api/kubecost"
              value={apiForm.api_url}
              onChange={e => setApiForm({ api_url: e.target.value })}
              style={{
                width:'100%', padding: '10px 14px',
                backgroundColor: '#f1f5f9',
                border: '1px solid hsl(0,40%, 22%)',
                borderRadius: '8px', color: '#0f172a',
                fontSize: '14px', outline: 'none' ,
                boxSizing: 'border-box' 

              }}
            />
          </div>
          <button 
             onClick={handleAPI}
             style={{
              backgroundColor: '#e11d48', color: '#fff',
              border: 'none', borderRadius: '8px',
              padding: '12px', fontSize: '14px',
              fontWeight: '600', cursor: 'pointer',
              marginTop: '8px'
             }}
          > Connect to API </button>
          <p style={{ fontSize:'12px', color:'#64748b',textAlign:'center'}}>Your API must return Kubecost allocation data in standard JSON format.</p>
        </div>
      )}

      {loading && (
        <p style={{ color: '#64748b', marginTop: '24px', fontSize: '14px' }}>
          {mode === 'file' ? 'Uploading and processing...' : mode === 'mongodb' ? 'Connecting to MongoDB...' : 'Connecting to API...'}
        </p>
      )}
      {error && (
        <p style={{ color: '#e11d48', marginTop: '24px', fontSize: '14px' }}>{error}</p>
      )}

      <p style={{ color: '#64748b', fontSize: '12px', marginTop: '32px', maxWidth: '400px', textAlign: 'center' }}>
        Expected fields: name, date, cpuCost, ramCost, pvCost, podCount, totalCost, cpuEfficiency, ramEfficiency
      </p>
    </div>
  );
}

const REQUIRED_FIELDS = [
  { key: 'name',          label: 'Namespace Name' },
  { key: 'date',          label: 'Date' },
  { key: 'cpuCost',       label: 'CPU Cost' },
  { key: 'ramCost',       label: 'RAM Cost' },
  { key: 'pvCost',        label: 'Storage Cost (PV)' },
  { key: 'podCount',      label: 'Pod Count' },
  { key: 'totalCost',     label: 'Total Cost' },
  { key: 'cpuEfficiency', label: 'CPU Efficiency' },
  { key: 'ramEfficiency', label: 'RAM Efficiency' },
];

function FieldMappingScreen({ uploadInfo, onMapped, onBack }) {
  const [fields, setFields] = useState([]);
  const [mapping, setMapping] = useState({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [autoMapped, setAutoMapped] = useState(false);

  useEffect(() => {
    fetch('http://127.0.0.1:8000/fields')
      .then(res => res.json())
      .then(data => {
        if (data.fields) {
          setFields(data.fields);

          // Auto-map if field names match exactly
          const auto = {};
          REQUIRED_FIELDS.forEach(f => {
            if (data.fields.includes(f.key)) {
              auto[f.key] = f.key;
            }
          });
          setMapping(auto);

          // Check if all fields auto-mapped
          const allMapped = REQUIRED_FIELDS.every(f => data.fields.includes(f.key));
          setAutoMapped(allMapped);
        }
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  async function handleSubmit() {
    const missing = REQUIRED_FIELDS.filter(f => !mapping[f.key]);
    if (missing.length > 0) {
      setError(`Please map all fields. Missing: ${missing.map(f => f.label).join(', ')}`);
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const res = await fetch('http://127.0.0.1:8000/map-fields', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(mapping)
      });
      const data = await res.json();
      if (data.message) {
        onMapped(data);
      } else {
        setError(data.error || 'Mapping failed.');
      }
    } catch (e) {
      setError('Could not connect to backend.');
    }
    setSubmitting(false);
  }

  if (loading) return (
    <div style={{
      minHeight: '100vh', display: 'flex',
      alignItems: 'center', justifyContent: 'center'
    }}>
      <p style={{ color: '#64748b' }}>Detecting fields...</p>
    </div>
  );

  return (
    <div style={{
      minHeight: '100vh', display: 'flex',
      flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', padding: '32px',
      backgroundColor: '#f8fafc'
    }}>
      <h1 style={{ fontSize: '24px', fontWeight: '800', color: '#e11d48', marginBottom: '8px' }}>
        Map Your Fields
      </h1>
      <p style={{ color: '#64748b', fontSize: '14px', marginBottom: '32px', textAlign: 'center' }}>
        We detected <strong>{fields.length} fields</strong> in your data. Match them to our expected fields.
      </p>

      {autoMapped && (
        <div style={{
          backgroundColor: '#f0fdf4',
          border: '1px solid #bbf7d0',
          borderRadius: '8px', padding: '12px 20px',
          marginBottom: '24px', color: '#16a34a',
          fontSize: '13px'
        }}>
          ✅ All fields matched automatically — you can proceed directly.
        </div>
      )}

      <div style={{
        width: '100%', maxWidth: '560px',
        backgroundColor: '#ffffff',
        border: '1px solid #e2e8f0',
        borderRadius: '16px', padding: '32px',
        display: 'flex', flexDirection: 'column', gap: '16px'
      }}>
        {REQUIRED_FIELDS.map(field => (
          <div key={field.key} style={{
            display: 'grid', gridTemplateColumns: '1fr 1fr',
            alignItems: 'center', gap: '16px'
          }}>
            <label style={{ fontSize: '13px', color: '#0f172a', fontWeight: '500' }}>
              {field.label}
            </label>
            <select
              value={mapping[field.key] || ''}
              onChange={e => setMapping(prev => ({ ...prev, [field.key]: e.target.value }))}
              style={{
                padding: '8px 12px',
                backgroundColor: '#f8fafc',
                border: `1px solid ${mapping[field.key] ? '#e11d48' : '#e2e8f0'}`,
                borderRadius: '8px', color: '#0f172a',
                fontSize: '13px', outline: 'none', cursor: 'pointer'
              }}
            >
              <option value="">-- select field --</option>
              {fields.map(f => (
                <option key={f} value={f}>{f}</option>
              ))}
            </select>
          </div>
        ))}

        {error && (
          <p style={{ color: '#e11d48', fontSize: '13px' }}>{error}</p>
        )}

        <div style={{ display: 'flex', gap: '12px', marginTop: '8px' }}>
          <button
            onClick={onBack}
            style={{
              flex: 1, padding: '12px',
              backgroundColor: '#f1f5f9',
              border: '1px solid #e2e8f0',
              borderRadius: '8px', color: '#64748b',
              fontSize: '14px', cursor: 'pointer'
            }}
          >
            Back
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting}
            style={{
              flex: 2, padding: '12px',
              backgroundColor: '#e11d48',
              border: 'none', borderRadius: '8px',
              color: '#fff', fontSize: '14px',
              fontWeight: '600', cursor: 'pointer'
            }}
          >
            {submitting ? 'Applying...' : 'Continue to Dashboard'}
          </button>
        </div>
      </div>

      <p style={{ fontSize: '12px', color: '#94a3b8', marginTop: '16px' }}>
        {uploadInfo.total_records} records detected • {uploadInfo.date_range}
      </p>
    </div>
  );
}


function App() {
  const [uploadInfo, setUploadInfo] = useState(null);
  const [checking, setChecking] = useState(true);
  const [mappingInfo, setMappingInfo] = useState(null);

  useEffect(() => {
    fetch('http://127.0.0.1:8000/status')
      .then(res => res.json())
      .then(data => {
        if (data.has_data) {
          setUploadInfo(data);
          setMappingInfo(data);
        }
        setChecking(false);
      })
      .catch(() => setChecking(false));
  }, []);

  async function handleReset() {
    try {
      await fetch('http://127.0.0.1:8000/reset', { method: 'POST' });
    } catch (e) {}
    setUploadInfo(null);
    setMappingInfo(null);
  }

  if (checking) return (
    <div style={{
      minHeight: '100vh', display: 'flex',
      alignItems: 'center', justifyContent: 'center'
    }}>
      <p style={{ color: '#64748b' }}>Connecting to backend...</p>
    </div>
  );

  if (!uploadInfo) {
    return <UploadScreen onUpload={info => {
      setUploadInfo(info);
      setMappingInfo(null);
    }} />;
  }

  if (!mappingInfo) {
    return <FieldMappingScreen
      uploadInfo={uploadInfo}
      onMapped={setMappingInfo}
      onBack={() => setUploadInfo(null)}
    />;
  }

  return (
    <BrowserRouter>
      <Navbar namespaces={mappingInfo.namespaces} onReset={handleReset} />
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/namespace" element={<NamespaceDive namespaces={mappingInfo.namespaces} />} />
        <Route path="/forecast" element={<Forecast namespaces={mappingInfo.namespaces} />} />
        <Route path="/budget" element={<BudgetAlerts namespaces={mappingInfo.namespaces} />} />
        <Route path="/backtest" element={<Backtest namespaces={mappingInfo.namespaces} />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;