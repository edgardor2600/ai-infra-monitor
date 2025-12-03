import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import HostsList from './pages/HostsList';
import HostDetail from './pages/HostDetail';
import AlertsFeed from './pages/AlertsFeed';
import ProcessMonitor from './pages/ProcessMonitor';
import './App.css';

function App() {
  return (
    <Router>
      <div className="app">
        <nav className="navbar">
          <div className="nav-container">
            <Link to="/" className="nav-brand">AI Infra Monitor</Link>
            <div className="nav-links">
              <Link to="/hosts" className="nav-link">Hosts</Link>
              <Link to="/alerts" className="nav-link">Alerts</Link>
            </div>
          </div>
        </nav>
        
        <main className="main-content">
          <Routes>
            <Route path="/" element={<HostsList />} />
            <Route path="/hosts" element={<HostsList />} />
            <Route path="/hosts/:id" element={<HostDetail />} />
            <Route path="/hosts/:id/processes" element={<ProcessMonitor />} />
            <Route path="/alerts" element={<AlertsFeed />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
