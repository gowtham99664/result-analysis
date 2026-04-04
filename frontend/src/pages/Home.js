import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'react-toastify';
import axios from 'axios';

const API_URL = window.location.origin + '/api';

const LOGO_URL = 'https://www.spmvv.ac.in/jbframework/uploads/2022/05/logo-left.png';
const BANNER_URL = 'https://www.spmvv.ac.in/jbframework/uploads/2022/06/banner_arch.jpg';

function Home() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('student');
  const [loading, setLoading] = useState(false);

  const [studentForm, setStudentForm] = useState({
    roll_number: '',
    password: '',
  });

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
    <div className="home-page">
      {/* Top Banner */}
      <header className="home-banner">
        <img
          src={LOGO_URL}
          alt="SPMVV Logo"
          className="home-banner-logo"
          onError={(e) => {
            e.target.src = '/logo.svg';
          }}
        />
        <div className="home-banner-text">
          <span className="home-banner-english">SRI PADMAVATI MAHILA VISVAVIDYALAYAM</span>
          <span className="home-banner-sub">(Women's University) &mdash; Tirupati, Andhra Pradesh-517502, India</span>
          <span className="home-banner-accr">Accredited with "A+" Grade by NAAC &nbsp;|&nbsp; ISO 21001 : 2018 Certified</span>
        </div>
      </header>

      {/* Middle: Image (75%) + Login (25%) */}
      <main className="home-main">
        <div className="home-image-section">
          <img
            src={BANNER_URL}
            alt="SPMVV Campus Entrance"
            className="home-campus-image"
            onError={(e) => {
              e.target.src = '/entrance.svg';
            }}
          />
          <div className="home-image-overlay">
            <h1>Result Analysis System</h1>
          </div>
        </div>

        <div className="home-login-section">
          <div className="home-login-card">
            <h2>Login</h2>
            <p className="home-login-subtitle">Access your dashboard</p>

            {/* Tabs */}
            <div className="home-login-tabs">
              <button
                className={`home-login-tab ${activeTab === 'student' ? 'active' : ''}`}
                onClick={() => setActiveTab('student')}
              >
                Student
              </button>
              <button
                className={`home-login-tab ${activeTab === 'admin' ? 'active' : ''}`}
                onClick={() => setActiveTab('admin')}
              >
                Admin
              </button>
            </div>

            {/* Student Login */}
            {activeTab === 'student' && (
              <form onSubmit={handleStudentLogin} className="home-login-form">
                <div className="form-group">
                  <label>Roll / Hall Ticket No. <span className="required">*</span></label>
                  <input
                    type="text"
                    className="form-control"
                    placeholder="Enter roll number"
                    value={studentForm.roll_number}
                    onChange={(e) =>
                      setStudentForm({ ...studentForm, roll_number: e.target.value })
                    }
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Password <span className="required">*</span></label>
                  <input
                    type="password"
                    className="form-control"
                    placeholder="Enter password"
                    value={studentForm.password}
                    onChange={(e) =>
                      setStudentForm({ ...studentForm, password: e.target.value })
                    }
                    required
                  />
                </div>
                <button type="submit" className="form-submit" disabled={loading}>
                  {loading ? 'Logging in...' : 'Login'}
                </button>
              </form>
            )}

            {/* Admin Login */}
            {activeTab === 'admin' && (
              <form onSubmit={handleAdminLogin} className="home-login-form">
                <div className="form-group">
                  <label>Username <span className="required">*</span></label>
                  <input
                    type="text"
                    className="form-control"
                    placeholder="Enter username"
                    value={adminForm.username}
                    onChange={(e) =>
                      setAdminForm({ ...adminForm, username: e.target.value })
                    }
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Password <span className="required">*</span></label>
                  <input
                    type="password"
                    className="form-control"
                    placeholder="Enter password"
                    value={adminForm.password}
                    onChange={(e) =>
                      setAdminForm({ ...adminForm, password: e.target.value })
                    }
                    required
                  />
                </div>
                <button type="submit" className="form-submit" disabled={loading}>
                  {loading ? 'Logging in...' : 'Login'}
                </button>
              </form>
            )}

            <div className="home-login-footer">
              {activeTab === 'student' ? (
                <p>New student? <Link to="/register">Register here</Link></p>
              ) : (
                <p>Admin access only.</p>
              )}
            </div>
          </div>
        </div>
      </main>

      {/* Bottom Footer */}
      <footer className="home-footer">
        <p>
          &copy; {new Date().getFullYear()} Sri Padmavati Mahila Visvavidyalayam, Tirupati. All rights reserved. |{' '}
          <a href="https://www.spmvv.ac.in" target="_blank" rel="noopener noreferrer">
            www.spmvv.ac.in
          </a>
        </p>
      </footer>
    </div>
  );
}

export default Home;
