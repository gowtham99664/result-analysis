import React from 'react';
import { Link, useNavigate } from 'react-router-dom';

const LOGO_URL = 'https://www.spmvv.ac.in/jbframework/uploads/2022/05/logo-left.png';

function Navbar() {
  const navigate = useNavigate();
  const token = localStorage.getItem('token');
  const user = JSON.parse(localStorage.getItem('user') || '{}');

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    navigate('/');
  };

  return (
    <nav className="navbar">
      <Link to="/" className="navbar-brand">
        <img
          src={LOGO_URL}
          alt="SPMVV Logo"
          className="navbar-logo"
          onError={(e) => {
            e.target.src = '/logo.svg';
          }}
        />
        <div className="navbar-title">
          SRI PADMAVATI MAHILA VISVAVIDYALAYAM
          <small>Result Analysis System</small>
        </div>
      </Link>
      <div className="navbar-links">
        {!token ? (
          <>
            <Link to="/">Home</Link>
            <Link to="/login">Login</Link>
            <Link to="/register">Register</Link>
          </>
        ) : (
          <>
            <button className="btn-logout" onClick={handleLogout}>
              Logout
            </button>
          </>
        )}
      </div>
    </nav>
  );
}

export default Navbar;
