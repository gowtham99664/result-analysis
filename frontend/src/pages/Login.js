import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'react-toastify';
import axios from 'axios';

const API_URL = window.location.origin + '/api';
const LOGO_URL = 'https://www.spmvv.ac.in/jbframework/uploads/2022/05/logo-left.png';

function Login() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('student');
  const [loading, setLoading] = useState(false);

  // Student login state
  const [studentForm, setStudentForm] = useState({
    roll_number: '',
    password: '',
  });

  // Admin login state
  const [adminForm, setAdminForm] = useState({
    username: '',
    password: '',
  });

  const handleStudentLogin = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const response = await axios.post(`${API_URL}/auth/student/login`, studentForm);
      localStorage.setItem('token', response.data.access_token);
      localStorage.setItem('user', JSON.stringify(response.data.user));
      toast.success('Login successful!');
      navigate('/student/dashboard');
    } catch (error) {
      toast.error(error.response?.data?.error || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const handleAdminLogin = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const response = await axios.post(`${API_URL}/auth/admin/login`, adminForm);
      localStorage.setItem('token', response.data.access_token);
      localStorage.setItem('user', JSON.stringify(response.data.user));
      toast.success('Login successful!');
      navigate('/admin/dashboard');
    } catch (error) {
      toast.error(error.response?.data?.error || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-header">
          <img
            src={LOGO_URL}
            alt="SPMVV Logo"
            className="auth-logo"
            onError={(e) => { e.target.src = '/logo.svg'; }}
          />
          <p className="college-name">SRI PADMAVATI MAHILA VISVAVIDYALAYAM</p>
          <h2>Login</h2>
          <p>Access your result analysis dashboard</p>
        </div>

        {/* Tabs */}
        <div className="auth-tabs">
          <button
            className={`auth-tab ${activeTab === 'student' ? 'active' : ''}`}
            onClick={() => setActiveTab('student')}
          >
            Student Login
          </button>
          <button
            className={`auth-tab ${activeTab === 'admin' ? 'active' : ''}`}
            onClick={() => setActiveTab('admin')}
          >
            Admin Login
          </button>
        </div>

        {/* Student Login Form */}
        {activeTab === 'student' && (
          <form onSubmit={handleStudentLogin}>
            <div className="form-group">
              <label>
                Roll / Hall Ticket Number <span className="required">*</span>
              </label>
              <input
                type="text"
                className="form-control"
                placeholder="Enter your roll number"
                value={studentForm.roll_number}
                onChange={(e) =>
                  setStudentForm({ ...studentForm, roll_number: e.target.value })
                }
                required
              />
            </div>

            <div className="form-group">
              <label>
                Password <span className="required">*</span>
              </label>
              <input
                type="password"
                className="form-control"
                placeholder="Enter your password"
                value={studentForm.password}
                onChange={(e) =>
                  setStudentForm({ ...studentForm, password: e.target.value })
                }
                required
              />
            </div>

            <button type="submit" className="form-submit" disabled={loading}>
              {loading ? 'Logging in...' : 'Login as Student'}
            </button>
          </form>
        )}

        {/* Admin Login Form */}
        {activeTab === 'admin' && (
          <form onSubmit={handleAdminLogin}>
            <div className="form-group">
              <label>
                Username <span className="required">*</span>
              </label>
              <input
                type="text"
                className="form-control"
                placeholder="Enter admin username"
                value={adminForm.username}
                onChange={(e) =>
                  setAdminForm({ ...adminForm, username: e.target.value })
                }
                required
              />
            </div>

            <div className="form-group">
              <label>
                Password <span className="required">*</span>
              </label>
              <input
                type="password"
                className="form-control"
                placeholder="Enter admin password"
                value={adminForm.password}
                onChange={(e) =>
                  setAdminForm({ ...adminForm, password: e.target.value })
                }
                required
              />
            </div>

            <button type="submit" className="form-submit" disabled={loading}>
              {loading ? 'Logging in...' : 'Login as Admin'}
            </button>
          </form>
        )}

        <div className="auth-footer">
          {activeTab === 'student' ? (
            <p>
              Don't have an account?{' '}
              <Link to="/register">Register here</Link>
            </p>
          ) : (
            <p>Admin access only. Contact administrator for credentials.</p>
          )}
          <p style={{ marginTop: '0.5rem' }}>
            <Link to="/">Back to Home</Link>
          </p>
        </div>
      </div>
    </div>
  );
}

export default Login;
