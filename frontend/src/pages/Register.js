import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'react-toastify';
import axios from 'axios';

const API_URL = window.location.origin + '/api';
const LOGO_URL = 'https://www.spmvv.ac.in/jbframework/uploads/2022/05/logo-left.png';

function Register() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    full_name: '',
    roll_number: '',
    branch: '',
    section: '',
    password: '',
    confirm_password: '',
  });
  const [errors, setErrors] = useState({});

  const branches = [
    { value: '', label: 'Select Branch' },
    { value: 'CSE', label: 'Computer Science & Engineering (CSE)' },
    { value: 'ECE', label: 'Electronics & Communication Engineering (ECE)' },
    { value: 'EEE', label: 'Electrical & Electronics Engineering (EEE)' },
    { value: 'MECH', label: 'Mechanical Engineering (MECH)' },
  ];

  const sections = [
    { value: '', label: 'Select Section' },
    { value: 'A', label: 'Section A' },
    { value: 'B', label: 'Section B' },
    { value: 'C', label: 'Section C' },
  ];

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData({ ...formData, [name]: value });

    // Clear error for this field
    if (errors[name]) {
      setErrors({ ...errors, [name]: '' });
    }
  };

  const validate = () => {
    const newErrors = {};

    if (!formData.full_name.trim()) {
      newErrors.full_name = 'Full name is required';
    }

    if (!formData.roll_number.trim()) {
      newErrors.roll_number = 'Roll/Hall Ticket number is required';
    }

    if (!formData.branch) {
      newErrors.branch = 'Please select a branch';
    }

    if (!formData.section) {
      newErrors.section = 'Please select a section';
    }

    if (!formData.password) {
      newErrors.password = 'Password is required';
    } else if (formData.password.length < 6) {
      newErrors.password = 'Password must be at least 6 characters';
    }

    if (!formData.confirm_password) {
      newErrors.confirm_password = 'Please confirm your password';
    } else if (formData.password !== formData.confirm_password) {
      newErrors.confirm_password = 'Passwords do not match';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!validate()) {
      toast.error('Please fix the errors in the form');
      return;
    }

    setLoading(true);

    try {
      const response = await axios.post(`${API_URL}/auth/student/register`, formData);
      toast.success(response.data.message || 'Registration successful!');
      navigate('/login');
    } catch (error) {
      toast.error(error.response?.data?.error || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card auth-card-register">
        <div className="auth-header">
          <img
            src={LOGO_URL}
            alt="SPMVV Logo"
            className="auth-logo"
            onError={(e) => { e.target.src = '/logo.svg'; }}
          />
          <p className="college-name">SRI PADMAVATI MAHILA VISVAVIDYALAYAM</p>
          <h2>Student Registration</h2>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>
              Full Name (as per SSC) <span className="required">*</span>
            </label>
            <input
              type="text"
              name="full_name"
              className={`form-control ${errors.full_name ? 'error' : ''}`}
              placeholder="Enter your full name as per SSC certificate"
              value={formData.full_name}
              onChange={handleChange}
            />
            {errors.full_name && <p className="form-error">{errors.full_name}</p>}
          </div>

          <div className="form-group">
            <label>
              Roll / Hall Ticket Number <span className="required">*</span>
            </label>
            <input
              type="text"
              name="roll_number"
              className={`form-control ${errors.roll_number ? 'error' : ''}`}
              placeholder="Enter your roll/hall ticket number"
              value={formData.roll_number}
              onChange={handleChange}
            />
            {errors.roll_number && (
              <p className="form-error">{errors.roll_number}</p>
            )}
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>
                Branch <span className="required">*</span>
              </label>
              <select
                name="branch"
                className={`form-control ${errors.branch ? 'error' : ''}`}
                value={formData.branch}
                onChange={handleChange}
              >
                {branches.map((b) => (
                  <option key={b.value} value={b.value}>
                    {b.label}
                  </option>
                ))}
              </select>
              {errors.branch && <p className="form-error">{errors.branch}</p>}
            </div>

            <div className="form-group">
              <label>
                Section <span className="required">*</span>
              </label>
              <select
                name="section"
                className={`form-control ${errors.section ? 'error' : ''}`}
                value={formData.section}
                onChange={handleChange}
              >
                {sections.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
              {errors.section && <p className="form-error">{errors.section}</p>}
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>
                Password <span className="required">*</span>
              </label>
              <input
                type="password"
                name="password"
                className={`form-control ${errors.password ? 'error' : ''}`}
                placeholder="Min 6 characters"
                value={formData.password}
                onChange={handleChange}
              />
              {errors.password && (
                <p className="form-error">{errors.password}</p>
              )}
            </div>

            <div className="form-group">
              <label>
                Confirm Password <span className="required">*</span>
              </label>
              <input
                type="password"
                name="confirm_password"
                className={`form-control ${errors.confirm_password ? 'error' : ''}`}
                placeholder="Re-enter password"
                value={formData.confirm_password}
                onChange={handleChange}
              />
              {errors.confirm_password && (
                <p className="form-error">{errors.confirm_password}</p>
              )}
            </div>
          </div>

          <button type="submit" className="form-submit" disabled={loading}>
            {loading ? 'Registering...' : 'Register'}
          </button>
        </form>

        <div className="auth-footer">
          <p>
            Already have an account? <Link to="/login">Login here</Link>
          </p>
          <p style={{ marginTop: '0.5rem' }}>
            <Link to="/">Back to Home</Link>
          </p>
        </div>
      </div>
    </div>
  );
}

export default Register;
