import React, { createContext, useContext, useState, useEffect } from 'react';
import api from '../api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('saas_token'));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (token) {
      fetchCurrentUser(token);
    } else {
      setLoading(false);
    }
  }, [token]);

  const fetchCurrentUser = async (currentToken) => {
    try {
      const res = await api.get('/auth/me');
      if (res.data.ok) {
        setUser(res.data.user);
      }
    } catch (err) {
      console.warn('Session expired or invalid token:', err);
      logout();
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password) => {
    const res = await api.post('/auth/login', { email, password });
    if (res.data.ok) {
      const newToken = res.data.access_token;
      localStorage.setItem('saas_token', newToken);
      setToken(newToken);
      setUser(res.data.user);
      return res.data;
    }
  };

  const register = async (organizationName, email, password, licenseTier = 'pro_saas') => {
    const res = await api.post('/auth/register', {
      organization_name: organizationName,
      email,
      password,
      license_tier: licenseTier
    });
    if (res.data.ok) {
      const newToken = res.data.access_token;
      localStorage.setItem('saas_token', newToken);
      setToken(newToken);
      setUser(res.data.user);
      return res.data;
    }
  };

  const logout = () => {
    localStorage.removeItem('saas_token');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout, setUser }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
