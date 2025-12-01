import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getHosts } from '../api';
import './HostsList.css';

function HostsList() {
  const [hosts, setHosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadHosts();
  }, []);

  const loadHosts = async () => {
    try {
      setLoading(true);
      const data = await getHosts();
      setHosts(data);
      setError(null);
    } catch (err) {
      setError('Failed to load hosts: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading hosts...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  return (
    <div className="hosts-list">
      <h1>Hosts</h1>
      <div className="hosts-table">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Hostname</th>
              <th>Created At</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {hosts.map((host) => (
              <tr key={host.id}>
                <td>{host.id}</td>
                <td>{host.hostname}</td>
                <td>{new Date(host.created_at).toLocaleString()}</td>
                <td>
                  <Link to={`/hosts/${host.id}`} className="btn-view">
                    View Details
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {hosts.length === 0 && (
          <div className="no-data">No hosts found</div>
        )}
      </div>
    </div>
  );
}

export default HostsList;
