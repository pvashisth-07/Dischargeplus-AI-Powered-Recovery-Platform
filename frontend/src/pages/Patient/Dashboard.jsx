import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { ClipboardList, Pill, MessageSquare, Activity, Flame, BellRing } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import Sidebar from '../../components/shared/Sidebar'
import ProgressRing from '../../components/charts/ProgressRing'
import RiskBadge from '../../components/shared/RiskBadge'
import api from '../../lib/api'

export default function PatientDashboard() {
  const [profile, setProfile] = useState(null)
  const [surveys, setSurveys] = useState([])
  const [meds, setMeds] = useState([])
  const [adherence, setAdherence] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    // 1. Fetch core clinical dashboard info immediately
    Promise.all([
      api.get('/patient/me'),
      api.get('/patient/surveys/pending'),
      api.get('/patient/medications'),
    ])
      .then(([p, s, m]) => {
        setProfile(p.data)
        setSurveys(s.data || [])
        setMeds(m.data || [])
        setLoading(false)
      })
      .catch((e) => {
        console.error(e)
        setLoading(false)
      })

    // 2. Fetch ML adherence forecast non-blocking in background
    api.get('/ml/adherence/me')
      .then((adh) => setAdherence(adh?.data || null))
      .catch(() => {})
  }, [])

  const daysSinceDischarge = profile?.discharge_date
    ? Math.max(0, Math.floor((Date.now() - new Date(profile.discharge_date)) / 86400000))
    : 0
  const totalDays = profile?.expected_recovery_days || 30

  return (
    <div className="page-container">
      <Sidebar />
      <main className="main-content">
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <div className="page-header">
            <h1 className="page-title">Welcome, {profile?.full_name?.split(' ')[0] || 'Patient'} 👋</h1>
            <p className="page-subtitle">Your recovery dashboard</p>
          </div>

          {/* Medication Adherence Reminder Nudge & Streak */}
          {adherence?.nudge && (
            <motion.div
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              style={{
                background: adherence.adherence_risk === 'high' ? 'rgba(255, 71, 87, 0.12)' : (adherence.adherence_risk === 'medium' ? 'rgba(255, 165, 2, 0.12)' : 'rgba(0, 212, 170, 0.1)'),
                border: `1px solid ${adherence.adherence_risk === 'high' ? 'rgba(255, 71, 87, 0.3)' : (adherence.adherence_risk === 'medium' ? 'rgba(255, 165, 2, 0.3)' : 'rgba(0, 212, 170, 0.25)')}`,
                borderRadius: 12,
                padding: '12px 18px',
                marginBottom: 20,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: 12,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                {adherence.adherence_risk === 'high' || adherence.adherence_risk === 'medium' ? (
                  <BellRing size={18} color={adherence.adherence_risk === 'high' ? '#FF4757' : '#FFA502'} />
                ) : (
                  <Flame size={18} color="#FF6B6B" />
                )}
                <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>
                  {adherence.nudge}
                </span>
              </div>
              <button
                onClick={() => navigate('/patient/medications')}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--accent)',
                  fontWeight: 600,
                  fontSize: 13,
                  cursor: 'pointer',
                  textDecoration: 'underline'
                }}
              >
                Log Doses →
              </button>
            </motion.div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: 20, marginBottom: 24 }}>
            {/* Recovery Progress */}
            <div className="glass-card" style={{ padding: 24, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: 'var(--text-secondary)' }}>Recovery Progress</h3>
              <ProgressRing current={daysSinceDischarge} total={totalDays} size={140} />
              <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 12 }}>
                {totalDays - daysSinceDischarge > 0 ? `${totalDays - daysSinceDischarge} days remaining` : 'Recovery period complete!'}
              </p>
              {profile?.latest_risk && (
                <div style={{ marginTop: 12 }}>
                  <RiskBadge level={profile.latest_risk.risk_level} />
                </div>
              )}
            </div>

            {/* Quick Actions */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              {/* Pending Surveys */}
              <div className="glass-card glass-card-hover" style={{ padding: 20, cursor: 'pointer' }} onClick={() => navigate('/patient/survey')}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                  <div style={{ width: 40, height: 40, borderRadius: 10, background: 'rgba(0,212,170,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <ClipboardList size={20} color="var(--accent)" />
                  </div>
                  <h3 style={{ fontSize: 15, fontWeight: 600 }}>Pending Surveys</h3>
                </div>
                <p style={{ fontSize: 28, fontWeight: 700 }}>{surveys.length}</p>
                <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                  {surveys.length > 0 ? 'Complete your health surveys' : 'All caught up!'}
                </p>
              </div>

              {/* Medications */}
              <div className="glass-card glass-card-hover" style={{ padding: 20, cursor: 'pointer' }} onClick={() => navigate('/patient/medications')}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                  <div style={{ width: 40, height: 40, borderRadius: 10, background: 'rgba(162,155,254,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Pill size={20} color="#A29BFE" />
                  </div>
                  <h3 style={{ fontSize: 15, fontWeight: 600 }}>Medications</h3>
                </div>
                <p style={{ fontSize: 28, fontWeight: 700 }}>{meds.length}</p>
                <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>Active medications</p>
              </div>

              {/* Chat */}
              <div className="glass-card glass-card-hover" style={{ padding: 20, cursor: 'pointer' }} onClick={() => navigate('/patient/chat')}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                  <div style={{ width: 40, height: 40, borderRadius: 10, background: 'rgba(0,180,216,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <MessageSquare size={20} color="#00B4D8" />
                  </div>
                  <h3 style={{ fontSize: 15, fontWeight: 600 }}>Chat with Doctor</h3>
                </div>
                <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                  {profile?.doctors?.[0]?.full_name || 'Your assigned doctor'}
                </p>
              </div>

              {/* Report Analyzer */}
              <div className="glass-card glass-card-hover" style={{ padding: 20, cursor: 'pointer' }} onClick={() => navigate('/patient/reports')}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                  <div style={{ width: 40, height: 40, borderRadius: 10, background: 'rgba(255,165,2,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Activity size={20} color="#FFA502" />
                  </div>
                  <h3 style={{ fontSize: 15, fontWeight: 600 }}>Report Analyzer</h3>
                </div>
                <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>Upload & analyze medical reports</p>
              </div>
            </div>
          </div>

          {/* Pending Survey Cards */}
          {surveys.length > 0 && (
            <div>
              <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>Pending Surveys</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 }}>
                {surveys.map((s) => {
                  const dueDate = s.due_date ? new Date(s.due_date) : null
                  const daysLeft = dueDate ? Math.ceil((dueDate - Date.now()) / 86400000) : null
                  return (
                    <div key={s.id} className="glass-card glass-card-hover" style={{ padding: 20, cursor: 'pointer' }} onClick={() => navigate(`/patient/survey?id=${s.id}`)}>
                      <h4 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>{s.title}</h4>
                      <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>{s.question_types?.length || 0} questions</p>
                      {daysLeft !== null && (
                        <span style={{
                          fontSize: 11, padding: '3px 8px', borderRadius: 20, fontWeight: 600,
                          background: daysLeft <= 1 ? 'rgba(255,71,87,0.15)' : 'rgba(0,212,170,0.15)',
                          color: daysLeft <= 1 ? '#FF4757' : 'var(--accent)',
                        }}>
                          {daysLeft > 0 ? `${daysLeft} days left` : 'Due today'}
                        </span>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </motion.div>
      </main>
    </div>
  )
}
