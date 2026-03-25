import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import useStore from './store/useStore'

// Auth
import AdminLogin from './pages/Auth/AdminLogin'
import AdminRegister from './pages/Auth/AdminRegister'
import DoctorLogin from './pages/Auth/DoctorLogin'
import PatientLogin from './pages/Auth/PatientLogin'

// Admin
import AdminDashboard from './pages/Admin/Dashboard'
import Doctors from './pages/Admin/Doctors'
import Patients from './pages/Admin/Patients'
import Assignments from './pages/Admin/Assignments'
import Analytics from './pages/Admin/Analytics'

// Doctor
import DoctorDashboard from './pages/Doctor/Dashboard'
import PatientDetail from './pages/Doctor/PatientDetail'
import SendSurvey from './pages/Doctor/SendSurvey'
import DoctorChat from './pages/Doctor/Chat'
import DoctorCallRoom from './pages/Doctor/CallRoom'

// Patient
import PatientDashboard from './pages/Patient/Dashboard'
import Survey from './pages/Patient/Survey'
import ReportAnalyzer from './pages/Patient/ReportAnalyzer'
import Medications from './pages/Patient/Medications'
import PatientChat from './pages/Patient/Chat'
import PatientCallRoom from './pages/Patient/CallRoom'

function ProtectedRoute({ children, allowedRoles }) {
  const { isAuthenticated, user } = useStore()
  if (!isAuthenticated) return <Navigate to="/login" replace />
  if (allowedRoles && !allowedRoles.includes(user?.role)) {
    const role = user?.role || 'admin'
    return <Navigate to={`/${role}/dashboard`} replace />
  }
  return children
}

function App() {
  return (
    <BrowserRouter>
      <AnimatePresence mode="wait">
        <Routes>
          {/* Public */}
          <Route path="/login" element={<AdminLogin />} />
          <Route path="/register" element={<AdminRegister />} />
          <Route path="/doctor-login" element={<DoctorLogin />} />
          <Route path="/patient-login" element={<PatientLogin />} />

          {/* Admin */}
          <Route path="/admin/dashboard" element={<ProtectedRoute allowedRoles={['admin']}><AdminDashboard /></ProtectedRoute>} />
          <Route path="/admin/doctors" element={<ProtectedRoute allowedRoles={['admin']}><Doctors /></ProtectedRoute>} />
          <Route path="/admin/patients" element={<ProtectedRoute allowedRoles={['admin']}><Patients /></ProtectedRoute>} />
          <Route path="/admin/assignments" element={<ProtectedRoute allowedRoles={['admin']}><Assignments /></ProtectedRoute>} />
          <Route path="/admin/analytics" element={<ProtectedRoute allowedRoles={['admin']}><Analytics /></ProtectedRoute>} />

          {/* Doctor */}
          <Route path="/doctor/dashboard" element={<ProtectedRoute allowedRoles={['doctor']}><DoctorDashboard /></ProtectedRoute>} />
          <Route path="/doctor/patient/:id" element={<ProtectedRoute allowedRoles={['doctor']}><PatientDetail /></ProtectedRoute>} />
          <Route path="/doctor/send-survey" element={<ProtectedRoute allowedRoles={['doctor']}><SendSurvey /></ProtectedRoute>} />
          <Route path="/doctor/chat" element={<ProtectedRoute allowedRoles={['doctor']}><DoctorChat /></ProtectedRoute>} />
          <Route path="/doctor/call" element={<ProtectedRoute allowedRoles={['doctor']}><DoctorCallRoom /></ProtectedRoute>} />

          {/* Patient */}
          <Route path="/patient/dashboard" element={<ProtectedRoute allowedRoles={['patient']}><PatientDashboard /></ProtectedRoute>} />
          <Route path="/patient/survey" element={<ProtectedRoute allowedRoles={['patient']}><Survey /></ProtectedRoute>} />
          <Route path="/patient/reports" element={<ProtectedRoute allowedRoles={['patient']}><ReportAnalyzer /></ProtectedRoute>} />
          <Route path="/patient/medications" element={<ProtectedRoute allowedRoles={['patient']}><Medications /></ProtectedRoute>} />
          <Route path="/patient/chat" element={<ProtectedRoute allowedRoles={['patient']}><PatientChat /></ProtectedRoute>} />
          <Route path="/patient/call" element={<ProtectedRoute allowedRoles={['patient']}><PatientCallRoom /></ProtectedRoute>} />

          {/* Default */}
          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </AnimatePresence>
    </BrowserRouter>
  )
}

export default App
