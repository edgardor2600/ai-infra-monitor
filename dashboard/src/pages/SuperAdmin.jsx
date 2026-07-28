import React, { useState, useEffect } from 'react';
import {
  getAdminUsers,
  getAdminStats,
  changeUserTier,
  changeUserRole,
  resetUserPassword,
  deleteUserAccount
} from '../api';
import './SuperAdmin.css';

const SuperAdmin = () => {
  const [users, setUsers] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [tierFilter, setTierFilter] = useState('ALL');
  
  // Feedback alerts
  const [toast, setToast] = useState({ show: false, message: '', type: 'success' });

  // Modal states
  const [resetModal, setResetModal] = useState({ open: false, user: null, password: '' });
  const [deleteModal, setDeleteModal] = useState({ open: false, user: null });
  const [actionLoading, setActionLoading] = useState(false);

  const showToast = (message, type = 'success') => {
    setToast({ show: true, message, type });
    setTimeout(() => setToast({ show: false, message: '', type: 'success' }), 4000);
  };

  const fetchData = async () => {
    setLoading(true);
    try {
      const [usersRes, statsRes] = await Promise.all([getAdminUsers(), getAdminStats()]);
      setUsers(usersRes.users || []);
      setStats(statsRes.stats || null);
    } catch (err) {
      console.error('Error fetching admin data:', err);
      showToast(err.response?.data?.detail || 'Error al cargar datos del panel SuperAdmin', 'danger');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleTierChange = async (orgId, newTier, userEmail) => {
    try {
      await changeUserTier(orgId, newTier);
      showToast(`Plan de la organización de ${userEmail} actualizado a ${newTier.toUpperCase()}`);
      fetchData();
    } catch (err) {
      showToast(err.response?.data?.detail || 'Error al actualizar el plan', 'danger');
    }
  };

  const handleRoleChange = async (userId, newRole, userEmail) => {
    try {
      await changeUserRole(userId, newRole);
      showToast(`Rol de ${userEmail} actualizado a ${newRole.toUpperCase()}`);
      fetchData();
    } catch (err) {
      showToast(err.response?.data?.detail || 'Error al actualizar el rol', 'danger');
    }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    if (!resetModal.password || resetModal.password.length < 6) {
      showToast('La contraseña debe tener al menos 6 caracteres', 'danger');
      return;
    }
    setActionLoading(true);
    try {
      await resetUserPassword(resetModal.user.id, resetModal.password);
      showToast(`Contraseña restablecida correctamente para ${resetModal.user.email}`);
      setResetModal({ open: false, user: null, password: '' });
    } catch (err) {
      showToast(err.response?.data?.detail || 'Error al restablecer la contraseña', 'danger');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteUser = async () => {
    setActionLoading(true);
    try {
      await deleteUserAccount(deleteModal.user.id);
      showToast(`Cuenta de ${deleteModal.user.email} eliminada correctamente`);
      setDeleteModal({ open: false, user: null });
      fetchData();
    } catch (err) {
      showToast(err.response?.data?.detail || 'Error al eliminar usuario', 'danger');
    } finally {
      setActionLoading(false);
    }
  };

  const filteredUsers = users.filter((u) => {
    const matchesSearch =
      u.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
      u.org_name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesTier = tierFilter === 'ALL' || u.license_tier === tierFilter;
    return matchesSearch && matchesTier;
  });

  return (
    <div className="superadmin-container">
      {/* Toast Notification */}
      {toast.show && (
        <div className={`superadmin-toast ${toast.type}`}>
          {toast.type === 'success' ? '✅' : '⚠️'} {toast.message}
        </div>
      )}

      {/* Header Banner */}
      <div className="superadmin-header-card">
        <div className="superadmin-title-area">
          <h1>👑 Portal de Control SuperAdmin</h1>
          <p>Gestión global de empresas, suscripciones SaaS, credenciales y usuarios del sistema.</p>
        </div>
        <button onClick={fetchData} className="superadmin-refresh-btn">
          🔄 Actualizar Datos
        </button>
      </div>

      {/* KPI Stats Cards */}
      {stats && (
        <div className="superadmin-kpi-grid">
          <div className="superadmin-kpi-card gold">
            <div className="kpi-icon">👥</div>
            <div className="kpi-info">
              <span className="kpi-label">Total Usuarios</span>
              <span className="kpi-value">{stats.total_users}</span>
            </div>
          </div>

          <div className="superadmin-kpi-card cyan">
            <div className="kpi-icon">🏢</div>
            <div className="kpi-info">
              <span className="kpi-label">Empresas / Orgs</span>
              <span className="kpi-value">{stats.total_orgs}</span>
            </div>
          </div>

          <div className="superadmin-kpi-card purple">
            <div className="kpi-icon">💎</div>
            <div className="kpi-info">
              <span className="kpi-label">Planes Enterprise / Pro</span>
              <span className="kpi-value">
                {(stats.tier_distribution?.ENTERPRISE || 0) + (stats.tier_distribution?.PRO_SAAS || 0)}
              </span>
            </div>
          </div>

          <div className="superadmin-kpi-card green">
            <div className="kpi-icon">🖥️</div>
            <div className="kpi-info">
              <span className="kpi-label">Hosts Monitoreados</span>
              <span className="kpi-value">{stats.total_hosts}</span>
            </div>
          </div>
        </div>
      )}

      {/* Controls & Filters Bar */}
      <div className="superadmin-controls-card">
        <div className="search-box">
          <span className="search-icon">🔍</span>
          <input
            type="text"
            placeholder="Buscar por correo o empresa..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="filter-box">
          <label>Plan:</label>
          <select value={tierFilter} onChange={(e) => setTierFilter(e.target.value)}>
            <option value="ALL">Todos los Planes</option>
            <option value="ENTERPRISE">Enterprise</option>
            <option value="PRO_SAAS">Pro SaaS</option>
            <option value="STARTER">Starter</option>
          </select>
        </div>
      </div>

      {/* Main Table */}
      <div className="superadmin-table-card">
        {loading ? (
          <div className="superadmin-loading">⏳ Cargando listado de usuarios y empresas...</div>
        ) : (
          <table className="superadmin-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Usuario / Email</th>
                <th>Rol</th>
                <th>Organización / Empresa</th>
                <th>Plan de Suscripción</th>
                <th>Hosts</th>
                <th>Registro</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan="8" className="no-data">
                    No se encontraron usuarios matching con los filtros.
                  </td>
                </tr>
              ) : (
                filteredUsers.map((u) => (
                  <tr key={u.id}>
                    <td className="col-id">#{u.id}</td>
                    <td className="col-email">
                      <div className="user-email-badge">
                        <span>📧 {u.email}</span>
                      </div>
                    </td>
                    <td className="col-role">
                      <select
                        className={`role-select ${u.role}`}
                        value={u.role}
                        onChange={(e) => handleRoleChange(u.id, e.target.value, u.email)}
                      >
                        <option value="user">Usuario</option>
                        <option value="admin">Admin Org</option>
                        <option value="superadmin">👑 SuperAdmin</option>
                      </select>
                    </td>
                    <td className="col-org">🏢 {u.org_name}</td>
                    <td className="col-tier">
                      <select
                        className={`tier-select ${u.license_tier}`}
                        value={u.license_tier}
                        onChange={(e) => handleTierChange(u.org_id, e.target.value, u.email)}
                      >
                        <option value="STARTER">🌱 Starter</option>
                        <option value="PRO_SAAS">⚡ Pro SaaS</option>
                        <option value="ENTERPRISE">💎 Enterprise</option>
                      </select>
                    </td>
                    <td className="col-hosts">🖥️ {u.hosts_count}</td>
                    <td className="col-date">
                      {u.created_at ? new Date(u.created_at).toLocaleDateString() : 'N/A'}
                    </td>
                    <td className="col-actions">
                      <button
                        title="Restablecer Contraseña"
                        className="btn-action reset"
                        onClick={() => setResetModal({ open: true, user: u, password: '' })}
                      >
                        🔑 Password
                      </button>
                      <button
                        title="Eliminar Cuenta"
                        className="btn-action delete"
                        onClick={() => setDeleteModal({ open: true, user: u })}
                      >
                        🗑️ Borrar
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* Reset Password Modal */}
      {resetModal.open && (
        <div className="superadmin-modal-backdrop">
          <div className="superadmin-modal-card">
            <h3>🔑 Restablecer Contraseña</h3>
            <p>Usuario: <strong>{resetModal.user?.email}</strong></p>
            <form onSubmit={handleResetPassword}>
              <div className="form-group">
                <label>Nueva Contraseña (min 6 caracteres):</label>
                <input
                  type="password"
                  required
                  placeholder="Escribe la nueva contraseña..."
                  value={resetModal.password}
                  onChange={(e) => setResetModal({ ...resetModal, password: e.target.value })}
                />
              </div>
              <div className="modal-actions">
                <button
                  type="button"
                  className="btn-cancel"
                  onClick={() => setResetModal({ open: false, user: null, password: '' })}
                >
                  Cancelar
                </button>
                <button type="submit" className="btn-confirm" disabled={actionLoading}>
                  {actionLoading ? 'Guardando...' : '💾 Guardar Contraseña'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete User Modal */}
      {deleteModal.open && (
        <div className="superadmin-modal-backdrop">
          <div className="superadmin-modal-card danger">
            <h3>⚠️ Confirmar Eliminación de Cuenta</h3>
            <p>¿Estás seguro de que deseas eliminar permanentemente al usuario <strong>{deleteModal.user?.email}</strong>?</p>
            <div className="modal-actions">
              <button
                className="btn-cancel"
                onClick={() => setDeleteModal({ open: false, user: null })}
              >
                Cancelar
              </button>
              <button
                className="btn-delete-confirm"
                onClick={handleDeleteUser}
                disabled={actionLoading}
              >
                {actionLoading ? 'Eliminando...' : '🗑️ Confirmar Eliminación'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SuperAdmin;
