import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-toastify';
import axios from 'axios';
import Navbar from '../components/Navbar';

const API_URL = window.location.origin + '/api';

const YEAR_LABELS = { 1: 'I', 2: 'II', 3: 'III', 4: 'IV' };
const SEM_LABELS = { 1: 'I', 2: 'II' };

function StudentDashboard() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [results, setResults] = useState([]);
  const [semesterSummaries, setSemesterSummaries] = useState([]);
  const [cgpa, setCgpa] = useState(0);
  const [pendingSubjects, setPendingSubjects] = useState([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [filterYear, setFilterYear] = useState('');
  const [filterSemester, setFilterSemester] = useState('');

  // Upload state
  const [uploadFile, setUploadFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [parsedData, setParsedData] = useState(null);
  const [saving, setSaving] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef(null);

  // Password change
  const [showChangePassword, setShowChangePassword] = useState(false);
  const [passwordForm, setPasswordForm] = useState({
    current_password: '', new_password: '', confirm_password: '',
  });

  // Correction Request
  const [showCorrectionForm, setShowCorrectionForm] = useState(null); // semester key e.g. "1-2"
  const [correctionForm, setCorrectionForm] = useState({
    title: '', description: '', result_id: null,
  });
  const [correctionFile, setCorrectionFile] = useState(null);
  const [submittingCorrection, setSubmittingCorrection] = useState(false);
  const correctionFileRef = useRef(null);

  // Student Notifications (resolved/rejected requests)
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [showNotifications, setShowNotifications] = useState(false);

  // Add subject to saved results
  const [showAddSubject, setShowAddSubject] = useState(null); // semester key e.g. "1-2"
  const [addSubjectForm, setAddSubjectForm] = useState({
    subject_code: '', subject_name: '', year: '', semester: '',
  });
  const [addingSubject, setAddingSubject] = useState(false);

  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const token = localStorage.getItem('token');
  const headers = { Authorization: `Bearer ${token}` };

  useEffect(() => {
    if (!token) {
      navigate('/login');
      return;
    }
    // Prevent admin users from accessing student dashboard
    if (user.role !== 'student') {
      toast.error('Please login as a student to access this page.');
      navigate('/');
      return;
    }
    fetchProfile();
    fetchData();
    fetchNotifications();
    // eslint-disable-next-line
  }, []);

  const fetchProfile = async () => {
    try {
      const res = await axios.get(`${API_URL}/student/profile`, { headers });
      setProfile(res.data.student);
    } catch (error) {
      if (error.response?.status === 401 || error.response?.status === 403) {
        toast.error(error.response?.status === 403 
          ? 'Please login as a student to access this page.' 
          : 'Session expired. Please login again.');
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        navigate('/login');
      }
    }
  };

  const fetchData = async (year, semester) => {
    try {
      let url = `${API_URL}/student/results`;
      const params = [];
      const y = year !== undefined ? year : filterYear;
      const s = semester !== undefined ? semester : filterSemester;
      if (y) params.push(`year=${y}`);
      if (s) params.push(`semester=${s}`);
      if (params.length) url += '?' + params.join('&');

      const res = await axios.get(url, { headers });
      setResults(res.data.results || []);
      setSemesterSummaries(res.data.semester_summaries || []);
      setCgpa(res.data.cgpa || 0);
      setPendingSubjects(res.data.pending_subjects || []);
    } catch (error) {
      if (error.response?.status === 401) {
        toast.error('Session expired. Please login again.');
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        navigate('/login');
      } else {
        toast.error('Failed to load results');
      }
    } finally {
      setLoading(false);
    }
  };

  const fetchNotifications = async () => {
    try {
      const res = await axios.get(`${API_URL}/student/correction-requests`, { headers });
      const allRequests = res.data.requests || [];
      setNotifications(allRequests);
      // Count unread resolved/rejected/in_progress notifications
      const unread = allRequests.filter(r => 
        (r.status === 'RESOLVED' || r.status === 'REJECTED' || r.status === 'IN_PROGRESS') && !r.student_read
      ).length;
      setUnreadCount(unread);
    } catch (error) {
      // silently fail
    }
  };

  const handleMarkNotificationsRead = async () => {
    try {
      await axios.put(`${API_URL}/student/notifications/mark-read`, {}, { headers });
      setUnreadCount(0);
      // Update local state
      setNotifications(prev => prev.map(n => ({ ...n, student_read: 1 })));
    } catch (error) {
      // silently fail
    }
  };

  const handleApplyFilter = () => {
    fetchData(filterYear, filterSemester);
  };

  const handleClearFilter = () => {
    setFilterYear('');
    setFilterSemester('');
    fetchData('', '');
  };

  const getGradeClass = (grade) => {
    if (!grade) return '';
    const g = grade.replace('+', 'plus');
    return `grade-${g}`;
  };

  const getStatusClass = (status) => {
    if (status === 'PASS') return 'status-pass';
    if (status === 'FAIL') return 'status-fail';
    return 'status-other';
  };

  const getRequestStatusClass = (status) => {
    if (status === 'PENDING') return 'status-pending';
    if (status === 'IN_PROGRESS') return 'status-in-progress';
    if (status === 'RESOLVED') return 'status-pass';
    if (status === 'REJECTED') return 'status-fail';
    return 'status-other';
  };

  // ========================
  // UPLOAD HANDLERS
  // ========================

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleFileInputChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelect(e.target.files[0]);
    }
  };

  const handleFileSelect = (file) => {
    const validTypes = ['application/pdf', 'image/png', 'image/jpeg', 'image/jpg'];
    if (!validTypes.includes(file.type)) {
      toast.error('Invalid file type. Please upload a PDF or image (PNG, JPG).');
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      toast.error('File too large. Maximum size is 20MB.');
      return;
    }
    setUploadFile(file);
    setParsedData(null);
  };

  const handleUpload = async () => {
    if (!uploadFile) {
      toast.error('Please select a file first');
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append('file', uploadFile);

    try {
      const res = await axios.post(`${API_URL}/student/upload-memo`, formData, {
        headers: { ...headers, 'Content-Type': 'multipart/form-data' },
        timeout: 120000,
      });

      setParsedData(res.data);
      toast.success(`Parsed ${res.data.total_subjects} subjects from ${res.data.total_semesters} semester(s)`);
    } catch (error) {
      const msg = error.response?.data?.error || 'Failed to parse file';
      toast.error(msg);
    } finally {
      setUploading(false);
    }
  };

  const handleEditParsedField = (semIdx, subjIdx, field, value) => {
    // Only allow editing: subject_code, subject_name
    const editable = ['subject_code', 'subject_name'];
    if (!editable.includes(field)) return;

    const updated = { ...parsedData };
    updated.semesters[semIdx].subjects[subjIdx][field] = value;
    setParsedData(updated);
  };

  const handleEditSemesterField = (semIdx, field, value) => {
    // Allow editing year, semester, academic_year
    const editable = ['year', 'semester', 'academic_year'];
    if (!editable.includes(field)) return;

    const updated = { ...parsedData };
    if (field === 'year' || field === 'semester') {
      updated.semesters[semIdx][field] = parseInt(value) || 0;
    } else {
      updated.semesters[semIdx][field] = value;
    }
    setParsedData(updated);
  };

  const handleAddSubject = (semIdx) => {
    const updated = { ...parsedData };
    updated.semesters[semIdx].subjects.push({
      subject_code: '',
      subject_name: '',
      internal_marks: 0,
      external_marks: 0,
      total_marks: 0,
      grade_points: 0,
      grade: '',
      status: 'PASS',
    });
    updated.total_subjects = (updated.total_subjects || 0) + 1;
    setParsedData(updated);
  };

  const handleRemoveSubject = (semIdx, subjIdx) => {
    const updated = { ...parsedData };
    updated.semesters[semIdx].subjects.splice(subjIdx, 1);
    updated.total_subjects = Math.max(0, (updated.total_subjects || 1) - 1);
    setParsedData(updated);
  };

  const handleConfirmSave = async () => {
    if (!parsedData || !parsedData.semesters) return;

    // Validate: every semester must have year and semester
    for (const sem of parsedData.semesters) {
      if (!sem.year || !sem.semester) {
        toast.error('Please set Year and Semester for all sections before saving.');
        return;
      }
    }

    setSaving(true);
    try {
      const res = await axios.post(`${API_URL}/student/confirm-memo`, {
        semesters: parsedData.semesters,
        filename: uploadFile?.name || 'unknown',
      }, { headers });

      toast.success(res.data.message);
      setParsedData(null);
      setUploadFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      // Refresh data
      fetchData();
    } catch (error) {
      const msg = error.response?.data?.error || 'Failed to save results';
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  };

  const handleCancelUpload = () => {
    setParsedData(null);
    setUploadFile(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // ========================
  // CORRECTION REQUEST
  // ========================

  const handleOpenCorrectionForm = (semKey, resultId = null) => {
    const [y, s] = semKey.split('-');
    setCorrectionForm({ title: `Marks Correction - Year ${YEAR_LABELS[y]} Sem ${SEM_LABELS[s]}`, description: '', result_id: resultId, year: y, semester: s });
    setCorrectionFile(null);
    setShowCorrectionForm(semKey);
    setShowAddSubject(null); // close add subject if open
  };

  const handleSubmitCorrection = async (e) => {
    e.preventDefault();
    if (!correctionForm.title.trim() || !correctionForm.description.trim()) {
      toast.error('Title and description are required');
      return;
    }

    setSubmittingCorrection(true);
    try {
      const formData = new FormData();
      formData.append('title', correctionForm.title);
      formData.append('description', correctionForm.description);
      if (correctionForm.result_id) formData.append('result_id', correctionForm.result_id);
      if (correctionForm.year) formData.append('year', correctionForm.year);
      if (correctionForm.semester) formData.append('semester', correctionForm.semester);
      if (correctionFile) formData.append('attachment', correctionFile);

      await axios.post(`${API_URL}/student/correction-request`, formData, {
        headers: { ...headers, 'Content-Type': 'multipart/form-data' },
      });
      toast.success('Correction request submitted successfully!');
      setShowCorrectionForm(null);
      setCorrectionForm({ title: '', description: '', result_id: null, year: null, semester: null });
      setCorrectionFile(null);
      fetchNotifications();
    } catch (error) {
      toast.error(error.response?.data?.error || 'Failed to submit correction request');
    } finally {
      setSubmittingCorrection(false);
    }
  };

  // Calculate stats
  const totalSubjects = results.length;
  const passedSubjects = results.filter((r) => r.status === 'PASS').length;
  const failedSubjects = results.filter((r) => r.status === 'FAIL').length;

  // Change password handler
  const handleChangePassword = async (e) => {
    e.preventDefault();
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      toast.error('New passwords do not match');
      return;
    }
    if (passwordForm.new_password.length < 6) {
      toast.error('New password must be at least 6 characters');
      return;
    }
    try {
      await axios.put(`${API_URL}/student/change-password`, {
        current_password: passwordForm.current_password,
        new_password: passwordForm.new_password,
      }, { headers });
      toast.success('Password changed successfully!');
      setPasswordForm({ current_password: '', new_password: '', confirm_password: '' });
      setShowChangePassword(false);
    } catch (error) {
      toast.error(error.response?.data?.error || 'Failed to change password');
    }
  };

  // Open add subject form for a specific semester
  const handleOpenAddSubject = (semKey) => {
    const [y, s] = semKey.split('-');
    setAddSubjectForm({ subject_code: '', subject_name: '', year: y, semester: s });
    setShowAddSubject(semKey);
    setShowCorrectionForm(null); // close correction form if open
  };

  // Add missing subject to saved results
  const handleAddSubjectToResults = async (e) => {
    e.preventDefault();
    if (!addSubjectForm.subject_code.trim() || !addSubjectForm.subject_name.trim() || !addSubjectForm.year || !addSubjectForm.semester) {
      toast.error('All fields are required');
      return;
    }
    setAddingSubject(true);
    try {
      await axios.post(`${API_URL}/student/add-subject`, addSubjectForm, { headers });
      toast.success('Subject added successfully! Admin can update the marks.');
      setShowAddSubject(null);
      setAddSubjectForm({ subject_code: '', subject_name: '', year: '', semester: '' });
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.error || 'Failed to add subject');
    } finally {
      setAddingSubject(false);
    }
  };

  // Group results by year-semester
  const groupedResults = {};
  results.forEach((r) => {
    const key = `${r.year}-${r.semester}`;
    if (!groupedResults[key]) groupedResults[key] = [];
    groupedResults[key].push(r);
  });
  const sortedKeys = Object.keys(groupedResults).sort();

  if (loading) {
    return (
      <>
        <Navbar />
        <div className="dashboard-container">
          <div className="loading"><div className="spinner"></div></div>
        </div>
      </>
    );
  }

  return (
    <>
      <Navbar />
      <div className="dashboard-container">
        {/* Welcome Card */}
        <div className="welcome-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap' }}>
            <div>
              <h2>Welcome, {user.full_name || profile?.full_name || 'Student'}!</h2>
              <p>Here's your academic performance overview</p>
            </div>
            {/* Notification Bell */}
            <div className="student-notification-bell" onClick={() => {
              setShowNotifications(!showNotifications);
              if (!showNotifications && unreadCount > 0) handleMarkNotificationsRead();
            }}>
              <span className="bell-icon">&#128276;</span>
              {unreadCount > 0 && <span className="notification-badge">{unreadCount}</span>}
            </div>
          </div>
          <div className="info-grid">
            <div className="info-item">
              <label>Roll Number</label>
              <span>{profile?.roll_number || user.roll_number}</span>
            </div>
            <div className="info-item">
              <label>Branch</label>
              <span>{profile?.branch || user.branch}</span>
            </div>
            <div className="info-item">
              <label>Section</label>
              <span>{profile?.section || user.section}</span>
            </div>
          </div>
        </div>

        {/* Notifications Panel */}
        {showNotifications && (
          <div className="notifications-panel">
            <div className="notifications-header">
              <h3>Notifications</h3>
              <button className="btn btn-secondary btn-sm" onClick={() => setShowNotifications(false)} style={{ color: '#666' }}>Close</button>
            </div>
            {notifications.length > 0 ? (
              <div className="notifications-list">
                {notifications.map((n) => (
                  <div key={n.id} className={`notification-item ${!n.student_read && (n.status === 'RESOLVED' || n.status === 'REJECTED') ? 'unread' : ''}`}>
                    <div className="notification-item-header">
                      <strong>{n.title}</strong>
                      <span className={`status-badge ${getRequestStatusClass(n.status)}`}>{n.status}</span>
                    </div>
                    <p className="notification-desc">{n.description}</p>
                    {n.admin_remarks && (
                      <div className="admin-remarks-box">
                        <strong>Admin remarks:</strong> {n.admin_remarks}
                      </div>
                    )}
                    <small className="notification-date">{n.created_at ? new Date(n.created_at).toLocaleString() : ''}</small>
                  </div>
                ))}
              </div>
            ) : (
              <div className="no-data" style={{ padding: '2rem' }}>
                <p>No correction requests yet.</p>
              </div>
            )}
          </div>
        )}

        {/* Upload Marks Memo Section */}
        <div className="upload-section">
          <div className="upload-header">
            <h3>Upload Marks Memo</h3>
            <p>Upload your marks memo (PDF or image) to automatically extract and save your results</p>
          </div>

          {!parsedData ? (
            <div className="upload-area">
              <div
                className={`drop-zone ${dragActive ? 'drag-active' : ''} ${uploadFile ? 'has-file' : ''}`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
              >
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileInputChange}
                  accept=".pdf,.png,.jpg,.jpeg"
                  style={{ display: 'none' }}
                />
                {uploadFile ? (
                  <div className="file-selected">
                    <div className="file-icon">{uploadFile.name.endsWith('.pdf') ? '\u{1F4C4}' : '\u{1F5BC}'}</div>
                    <div className="file-name">{uploadFile.name}</div>
                    <div className="file-size">{(uploadFile.size / 1024).toFixed(1)} KB</div>
                  </div>
                ) : (
                  <div className="drop-prompt">
                    <div className="upload-icon">{'\u{2B06}'}</div>
                    <p><strong>Drag & drop</strong> your marks memo here</p>
                    <p className="drop-hint">or click to browse (PDF, PNG, JPG - max 20MB)</p>
                  </div>
                )}
              </div>

              <div className="upload-actions">
                <button
                  className="btn btn-primary"
                  onClick={handleUpload}
                  disabled={!uploadFile || uploading}
                >
                  {uploading ? 'Parsing...' : 'Upload & Parse'}
                </button>
                {uploadFile && (
                  <button className="btn btn-secondary" onClick={handleCancelUpload} style={{ color: '#666' }}>
                    Clear
                  </button>
                )}
              </div>

              {uploading && (
                <div className="upload-progress">
                  <div className="spinner"></div>
                  <p>Extracting data from your memo... This may take a moment.</p>
                </div>
              )}
            </div>
          ) : (
            /* Parsed Data Preview */
            <div className="parsed-preview">
              <div className="parsed-summary">
                <div className="parsed-stat">
                  <span className="parsed-stat-num">{parsedData.total_semesters}</span>
                  <span className="parsed-stat-label">Semester(s)</span>
                </div>
                <div className="parsed-stat">
                  <span className="parsed-stat-num">{parsedData.total_subjects}</span>
                  <span className="parsed-stat-label">Subject(s)</span>
                </div>
              </div>

              <div className="parsed-notice">
                <strong>Review the extracted data below.</strong> You can edit Subject Code, Subject Name, Year, Semester, and Academic Year. Marks, grade points, and grades can only be edited by the admin. If a subject is missing, click "+ Add Missing Subject" to add it. If marks are wrong, submit a correction request after saving.
              </div>

              {parsedData.semesters.map((sem, semIdx) => (
                <div className="table-container parsed-semester" key={semIdx}>
                  <div className="table-header parsed-sem-header">
                    <div className="parsed-sem-controls">
                      <div className="parsed-field">
                        <label>Year</label>
                        <select
                          className="form-control form-control-sm"
                          value={sem.year || ''}
                          onChange={(e) => handleEditSemesterField(semIdx, 'year', e.target.value)}
                        >
                          <option value="">--</option>
                          <option value="1">I</option>
                          <option value="2">II</option>
                          <option value="3">III</option>
                          <option value="4">IV</option>
                        </select>
                      </div>
                      <div className="parsed-field">
                        <label>Semester</label>
                        <select
                          className="form-control form-control-sm"
                          value={sem.semester || ''}
                          onChange={(e) => handleEditSemesterField(semIdx, 'semester', e.target.value)}
                        >
                          <option value="">--</option>
                          <option value="1">I</option>
                          <option value="2">II</option>
                        </select>
                      </div>
                      <div className="parsed-field">
                        <label>Academic Year</label>
                        <input
                          type="text"
                          className="form-control form-control-sm"
                          value={sem.academic_year || ''}
                          onChange={(e) => handleEditSemesterField(semIdx, 'academic_year', e.target.value)}
                          placeholder="e.g. 2023-24"
                        />
                      </div>
                    </div>
                    {sem.sgpa && (
                      <span className="sgpa-badge">SGPA: {sem.sgpa.toFixed ? sem.sgpa.toFixed(2) : sem.sgpa}</span>
                    )}
                  </div>

                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Code</th>
                          <th>Subject Name</th>
                          <th>Total Marks</th>
                          <th>Grade Pts</th>
                          <th>Grade</th>
                          <th>Status</th>
                          <th style={{width: '40px'}}></th>
                        </tr>
                      </thead>
                      <tbody>
                        {sem.subjects.map((subj, subjIdx) => (
                          <tr key={subjIdx} className={subj.status === 'FAIL' ? 'fail-row' : ''}>
                            <td>
                              <input
                                type="text"
                                className="inline-edit-input"
                                value={subj.subject_code}
                                onChange={(e) => handleEditParsedField(semIdx, subjIdx, 'subject_code', e.target.value)}
                              />
                            </td>
                            <td>
                              <input
                                type="text"
                                className="inline-edit-input wide"
                                value={subj.subject_name}
                                onChange={(e) => handleEditParsedField(semIdx, subjIdx, 'subject_name', e.target.value)}
                              />
                            </td>
                            <td className="readonly-cell"><strong>{subj.total_marks}</strong></td>
                            <td className="readonly-cell">{subj.grade_points}</td>
                            <td className="readonly-cell">
                              <span className={`grade-badge ${getGradeClass(subj.grade)}`}>{subj.grade}</span>
                            </td>
                            <td className="readonly-cell">
                              <span className={`status-badge ${getStatusClass(subj.status)}`}>{subj.status}</span>
                            </td>
                            <td>
                              <button
                                className="btn-icon-remove"
                                title="Remove subject"
                                onClick={() => handleRemoveSubject(semIdx, subjIdx)}
                              >
                                x
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <button
                    className="btn btn-outline btn-sm add-subject-btn"
                    onClick={() => handleAddSubject(semIdx)}
                  >
                    + Add Missing Subject
                  </button>
                </div>
              ))}

              <div className="parsed-actions">
                <button
                  className="btn btn-primary btn-lg"
                  onClick={handleConfirmSave}
                  disabled={saving}
                >
                  {saving ? 'Saving...' : 'Confirm & Save Results'}
                </button>
                <button
                  className="btn btn-secondary btn-lg"
                  onClick={handleCancelUpload}
                  style={{ color: '#666' }}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>

        {/* CGPA Card */}
        <div className="cgpa-card">
          <div className="cgpa-main">
            <div className="cgpa-value">{cgpa.toFixed(2)}</div>
            <div className="cgpa-label">CGPA</div>
            <div className="cgpa-sub">Cumulative Grade Point Average</div>
          </div>
          <div className="sgpa-list">
            {semesterSummaries.map((ss) => (
              <div className="sgpa-item" key={`${ss.year}-${ss.semester}`}>
                <span className="sgpa-sem">Year {YEAR_LABELS[ss.year]} - Sem {SEM_LABELS[ss.semester]}</span>
                <span className="sgpa-val">{ss.sgpa?.toFixed(2) || '0.00'}</span>
              </div>
            ))}
            {semesterSummaries.length === 0 && (
              <div className="sgpa-item"><span className="sgpa-sem">No semester data available</span></div>
            )}
          </div>
        </div>

        {/* Stats */}
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-icon blue">&#128214;</div>
            <div className="stat-info">
              <h3>{totalSubjects}</h3>
              <p>Total Subjects</p>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon green">&#9989;</div>
            <div className="stat-info">
              <h3>{passedSubjects}</h3>
              <p>Passed</p>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon red">&#10060;</div>
            <div className="stat-info">
              <h3>{failedSubjects}</h3>
              <p>Failed</p>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon gold">&#127942;</div>
            <div className="stat-info">
              <h3>{cgpa.toFixed(2)}</h3>
              <p>CGPA</p>
            </div>
          </div>
        </div>

        {/* Year/Semester Filter */}
        <div className="filter-section">
          <div className="filter-row">
            <div className="filter-group">
              <label>Year</label>
              <select className="form-control" value={filterYear} onChange={(e) => setFilterYear(e.target.value)}>
                <option value="">All Years</option>
                <option value="1">Year I</option>
                <option value="2">Year II</option>
                <option value="3">Year III</option>
                <option value="4">Year IV</option>
              </select>
            </div>
            <div className="filter-group">
              <label>Semester</label>
              <select className="form-control" value={filterSemester} onChange={(e) => setFilterSemester(e.target.value)}>
                <option value="">All Semesters</option>
                <option value="1">Semester I</option>
                <option value="2">Semester II</option>
              </select>
            </div>
            <button className="btn btn-primary filter-btn" onClick={handleApplyFilter}>Apply</button>
            <button className="btn btn-secondary filter-btn" style={{ color: 'var(--primary-color)', borderColor: 'var(--primary-color)' }} onClick={handleClearFilter}>Clear</button>
          </div>
          {(filterYear || filterSemester) && (
            <p className="filter-info">
              Showing results up to {filterYear ? `Year ${YEAR_LABELS[filterYear]}` : 'All Years'}
              {filterSemester ? ` - Semester ${SEM_LABELS[filterSemester]}` : ''}
            </p>
          )}
        </div>

        {/* Results Tables grouped by Year-Semester */}
        {sortedKeys.length > 0 ? (
          sortedKeys.map((key) => {
            const [y, s] = key.split('-');
            const semSummary = semesterSummaries.find(
              (ss) => String(ss.year) === y && String(ss.semester) === s
            );
            return (
              <div className="table-container" key={key}>
                <div className="table-header" style={{ flexWrap: 'wrap', gap: '0.5rem' }}>
                  <h3>Year {YEAR_LABELS[y]} - Semester {SEM_LABELS[s]}</h3>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                    {semSummary && (
                      <span className="sgpa-badge">SGPA: {semSummary.sgpa?.toFixed(2) || '-'}</span>
                    )}
                    <button className="btn btn-primary" style={{ padding: '0.3rem 0.7rem', fontSize: '0.8rem' }} onClick={() => handleOpenCorrectionForm(key)}>
                      Request Marks Correction
                    </button>
                    <button className="btn btn-secondary" style={{ padding: '0.3rem 0.7rem', fontSize: '0.8rem', color: 'var(--primary-color)', borderColor: 'var(--primary-color)' }} onClick={() => showAddSubject === key ? setShowAddSubject(null) : handleOpenAddSubject(key)}>
                      {showAddSubject === key ? 'Cancel' : '+ Add Missing Subject'}
                    </button>
                  </div>
                </div>
                <table>
                  <thead>
                    <tr>
                      <th>Code</th>
                      <th>Subject</th>
                      <th>Total Marks</th>
                      <th>Grade Pts</th>
                      <th>Grade</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {groupedResults[key].map((result) => (
                      <tr key={result.id} className={result.status === 'FAIL' ? 'fail-row' : ''}>
                        <td>{result.subject_code}</td>
                        <td>{result.subject_name}</td>
                        <td><strong>{result.total_marks}</strong></td>
                        <td>{result.grade_points}</td>
                        <td><span className={`grade-badge ${getGradeClass(result.grade)}`}>{result.grade}</span></td>
                        <td><span className={`status-badge ${getStatusClass(result.status)}`}>{result.status}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {/* Inline Add Missing Subject Form */}
                {showAddSubject === key && (
                  <div className="correction-form-card" style={{ padding: '1.5rem', marginTop: '0.5rem', borderTop: '2px solid var(--primary-color)' }}>
                    <h4 style={{ color: 'var(--primary-color)', marginBottom: '0.75rem' }}>Add Missing Subject — Year {YEAR_LABELS[y]} Sem {SEM_LABELS[s]}</h4>
                    <form onSubmit={handleAddSubjectToResults}>
                      <div className="form-row">
                        <div className="form-group">
                          <label>Subject Code <span className="required">*</span></label>
                          <input type="text" className="form-control" placeholder="e.g., 20CST04" value={addSubjectForm.subject_code} onChange={(e) => setAddSubjectForm({...addSubjectForm, subject_code: e.target.value})} required />
                        </div>
                        <div className="form-group">
                          <label>Subject Name <span className="required">*</span></label>
                          <input type="text" className="form-control" placeholder="e.g., Data Structures" value={addSubjectForm.subject_name} onChange={(e) => setAddSubjectForm({...addSubjectForm, subject_name: e.target.value})} required />
                        </div>
                      </div>
                      <div style={{ display: 'flex', gap: '0.75rem' }}>
                        <button type="submit" className="form-submit" style={{ padding: '0.4rem 1rem', fontSize: '0.85rem' }} disabled={addingSubject}>
                          {addingSubject ? 'Adding...' : 'Add Subject'}
                        </button>
                        <button type="button" className="btn btn-secondary" onClick={() => setShowAddSubject(null)} style={{ color: '#666', padding: '0.4rem 1rem', fontSize: '0.85rem' }}>
                          Cancel
                        </button>
                      </div>
                    </form>
                  </div>
                )}

                {/* Inline Correction Request Form */}
                {showCorrectionForm === key && (
                  <div className="correction-form-card" style={{ padding: '1.5rem', marginTop: '0.5rem', borderTop: '2px solid #ffc107' }}>
                    <h4 style={{ color: 'var(--primary-color)', marginBottom: '0.75rem' }}>Correction Request — Year {YEAR_LABELS[y]} Sem {SEM_LABELS[s]}</h4>
                    <form onSubmit={handleSubmitCorrection}>
                      <div className="form-group">
                        <label>Title <span className="required">*</span></label>
                        <input type="text" className="form-control" placeholder="e.g., Wrong marks in Data Structures" value={correctionForm.title} onChange={(e) => setCorrectionForm({ ...correctionForm, title: e.target.value })} required />
                      </div>
                      <div className="form-group">
                        <label>Description <span className="required">*</span></label>
                        <textarea className="form-control" rows="3" placeholder="Describe which marks are wrong and what they should be..." value={correctionForm.description} onChange={(e) => setCorrectionForm({ ...correctionForm, description: e.target.value })} required />
                      </div>
                      <div className="form-group">
                        <label>Attachment (optional)</label>
                        <input type="file" className="form-control" ref={correctionFileRef} accept=".pdf,.png,.jpg,.jpeg" onChange={(e) => setCorrectionFile(e.target.files[0] || null)} />
                      </div>
                      <div style={{ display: 'flex', gap: '0.75rem' }}>
                        <button type="submit" className="form-submit" style={{ padding: '0.4rem 1rem', fontSize: '0.85rem' }} disabled={submittingCorrection}>
                          {submittingCorrection ? 'Submitting...' : 'Submit Request'}
                        </button>
                        <button type="button" className="btn btn-secondary" onClick={() => setShowCorrectionForm(null)} style={{ color: '#666', padding: '0.4rem 1rem', fontSize: '0.85rem' }}>
                          Cancel
                        </button>
                      </div>
                    </form>
                  </div>
                )}
              </div>
            );
          })
        ) : (
          <div className="table-container">
            <div className="no-data">
              <div className="no-data-icon">&#128196;</div>
              <h3>No Results Available</h3>
              <p>Upload your marks memo above to add your results, or wait for the admin to publish them.</p>
            </div>
          </div>
        )}

        {/* Pending / Failed Subjects */}
        {pendingSubjects.length > 0 && (
          <div className="table-container pending-section">
            <div className="table-header">
              <h3 className="pending-title">Pending / Failed Subjects ({pendingSubjects.length})</h3>
            </div>
            <table>
              <thead>
                <tr>
                  <th>Year</th>
                  <th>Sem</th>
                  <th>Code</th>
                  <th>Subject</th>
                  <th>Total Marks</th>
                  <th>Grade</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {pendingSubjects.map((ps) => (
                  <tr key={ps.id} className="pending-row">
                    <td>{YEAR_LABELS[ps.year]}</td>
                    <td>{SEM_LABELS[ps.semester]}</td>
                    <td>{ps.subject_code}</td>
                    <td>{ps.subject_name}</td>
                    <td>{ps.total_marks}</td>
                    <td><span className={`grade-badge ${getGradeClass(ps.grade)}`}>{ps.grade}</span></td>
                    <td><span className="status-badge status-fail">{ps.status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* My Requests Section */}
        {notifications.length > 0 && (
          <div className="table-container" style={{ marginTop: '1.5rem' }}>
            <div className="table-header">
              <h3>My Requests</h3>
            </div>
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Title</th>
                  <th>Description</th>
                  <th>Status</th>
                  <th>Submitted</th>
                  <th>Admin Remarks</th>
                </tr>
              </thead>
              <tbody>
                {notifications.map((req, idx) => (
                  <tr key={req.id} className={req.status === 'PENDING' ? 'pending-request-row' : req.status === 'IN_PROGRESS' ? 'in-progress-request-row' : ''}>
                    <td>{idx + 1}</td>
                    <td><strong>{req.title}</strong></td>
                    <td style={{ maxWidth: '250px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{req.description}</td>
                    <td>
                      <span className={`status-badge ${getRequestStatusClass(req.status)}`}>
                        {req.status === 'IN_PROGRESS' ? 'IN PROGRESS' : req.status}
                      </span>
                    </td>
                    <td>{req.created_at ? new Date(req.created_at).toLocaleDateString() : '-'}</td>
                    <td style={{ maxWidth: '250px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {req.admin_remarks || '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Change Password Section */}
        <div className="table-container" style={{ marginTop: '1.5rem' }}>
          <div className="table-header">
            <h3>Account Settings</h3>
            <button
              className="btn btn-secondary btn-sm"
              style={{ color: 'var(--primary-color)', borderColor: 'var(--primary-color)' }}
              onClick={() => setShowChangePassword(!showChangePassword)}
            >
              {showChangePassword ? 'Cancel' : 'Change Password'}
            </button>
          </div>
          {showChangePassword && (
            <div style={{ padding: '1.5rem' }}>
              <form onSubmit={handleChangePassword}>
                <div className="form-group">
                  <label>Current Password <span className="required">*</span></label>
                  <input type="password" className="form-control" placeholder="Enter current password" value={passwordForm.current_password} onChange={(e) => setPasswordForm({...passwordForm, current_password: e.target.value})} required />
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label>New Password <span className="required">*</span></label>
                    <input type="password" className="form-control" placeholder="Min 6 characters" value={passwordForm.new_password} onChange={(e) => setPasswordForm({...passwordForm, new_password: e.target.value})} required />
                  </div>
                  <div className="form-group">
                    <label>Confirm New Password <span className="required">*</span></label>
                    <input type="password" className="form-control" placeholder="Re-enter new password" value={passwordForm.confirm_password} onChange={(e) => setPasswordForm({...passwordForm, confirm_password: e.target.value})} required />
                  </div>
                </div>
                <button type="submit" className="form-submit">Change Password</button>
              </form>
            </div>
          )}
        </div>
      </div>

      <footer className="footer">
        <p>&copy; {new Date().getFullYear()} Sri Padmavati Mahila Visvavidyalayam, Tirupati.</p>
      </footer>
    </>
  );
}

export default StudentDashboard;
