import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Send,
  CheckCircle,
  Thermometer,
  Droplets,
  Heart,
  Activity,
  Camera,
  Mic,
  FileText,
  Sliders,
  CheckSquare,
  HelpCircle,
  Hash,
  ArrowLeft
} from 'lucide-react'
import Sidebar from '../../components/shared/Sidebar'
import api from '../../lib/api'

const LEGACY_LABELS = {
  fever: 'What is your current body temperature (°F)?',
  spo2: 'What is your current oxygen saturation reading (SpO2 %)?',
  bp: 'What is your current blood pressure (systolic / diastolic)?',
  sugar: 'What is your current blood glucose level (mg/dL)?',
  pain: 'Rate your current pain level (0 = No pain, 10 = Severe)',
  photo: 'Please upload a photo of your wound or affected area',
  voice: 'Record a voice note describing your symptoms or feelings',
  custom_text: 'Please describe your symptoms or recovery updates',
}

export default function Survey() {
  const [searchParams] = useSearchParams()
  const surveyId = searchParams.get('id')
  const [surveys, setSurveys] = useState([])
  const [activeSurvey, setActiveSurvey] = useState(null)
  const [answers, setAnswers] = useState({})
  const [submitting, setSubmitting] = useState(false)
  const [feedback, setFeedback] = useState(null)
  const [recording, setRecording] = useState(false)
  const [mediaRecorder, setMediaRecorder] = useState(null)

  useEffect(() => {
    api.get('/patient/surveys/pending')
      .then(res => {
        setSurveys(res.data || [])
        if (surveyId) {
          const s = res.data.find(item => item.id === surveyId)
          if (s) setActiveSurvey(s)
        }
      })
      .catch(() => {})
  }, [surveyId])

  const setAnswer = (questionId, field, value) => {
    setAnswers(prev => ({
      ...prev,
      [questionId]: {
        ...prev[questionId],
        [field]: value,
      },
    }))
  }

  const getQuestionsList = (survey) => {
    if (!survey) return []
    if (Array.isArray(survey.survey_questions) && survey.survey_questions.length > 0) {
      return [...survey.survey_questions].sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0))
    }
    return (survey.question_types || []).map((type, idx) => ({
      id: type,
      question_type: type,
      question_text: LEGACY_LABELS[type] || `Please provide your ${type}`,
      is_required: !['photo', 'voice', 'custom_text'].includes(type),
      metadata: {},
      display_order: idx,
    }))
  }

  const handleSubmit = async () => {
    if (!activeSurvey) return
    const questionsList = getQuestionsList(activeSurvey)

    // Check required fields
    for (const q of questionsList) {
      if (q.is_required !== false) {
        const ans = answers[q.id]
        const hasVal = ans && (
          ans.answer_value !== null && ans.answer_value !== undefined && ans.answer_value !== '' ||
          ans.answer_numeric !== null && ans.answer_numeric !== undefined ||
          ans.file_url !== null && ans.file_url !== undefined
        )
        if (!hasVal) {
          return alert(`Please answer: "${q.question_text}"`)
        }
      }
    }

    setSubmitting(true)
    try {
      const answerList = questionsList.map(q => ({
        question_id: q.id.length > 20 ? q.id : null, // send UUID if database question
        question_type: q.question_type,
        question_text: q.question_text,
        answer_value: answers[q.id]?.answer_value ?? null,
        answer_numeric: answers[q.id]?.answer_numeric !== undefined ? answers[q.id].answer_numeric : null,
        file_url: answers[q.id]?.file_url ?? null,
      }))

      const res = await api.post(`/surveys/${activeSurvey.id}/respond`, { answers: answerList })
      setFeedback(res.data)
      setSurveys(prev => prev.filter(s => s.id !== activeSurvey.id))
    } catch (e) {
      alert(e.response?.data?.detail || 'Failed to submit survey')
    } finally {
      setSubmitting(false)
    }
  }

  const renderInput = (q) => {
    const type = q.question_type
    const meta = q.metadata || {}
    const currentAns = answers[q.id] || {}

    switch (type) {
      case 'choice':
        const options = meta.options || ['Option 1', 'Option 2']
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 10 }}>
            {options.map((opt, oIdx) => {
              const isSelected = currentAns.answer_value === opt
              return (
                <button
                  key={oIdx}
                  type="button"
                  onClick={() => setAnswer(q.id, 'answer_value', opt)}
                  style={{
                    padding: '12px 16px',
                    borderRadius: 10,
                    textAlign: 'left',
                    background: isSelected ? 'var(--accent-light)' : 'var(--bg-primary)',
                    border: `1.5px solid ${isSelected ? 'var(--accent)' : 'var(--border)'}`,
                    color: isSelected ? 'var(--accent)' : 'var(--text-primary)',
                    fontWeight: isSelected ? 600 : 500,
                    fontSize: 13,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    transition: 'all 0.2s',
                  }}
                >
                  <div
                    style={{
                      width: 16,
                      height: 16,
                      borderRadius: '50%',
                      border: `2px solid ${isSelected ? 'var(--accent)' : 'var(--border)'}`,
                      background: isSelected ? 'var(--accent)' : 'transparent',
                    }}
                  />
                  <span>{opt}</span>
                </button>
              )
            })}
          </div>
        )

      case 'boolean':
        const isYes = currentAns.answer_value === 'Yes'
        const isNo = currentAns.answer_value === 'No'
        return (
          <div style={{ display: 'flex', gap: 12, marginTop: 10 }}>
            <button
              type="button"
              onClick={() => setAnswer(q.id, 'answer_value', 'Yes')}
              style={{
                flex: 1,
                padding: '12px',
                borderRadius: 10,
                border: `1.5px solid ${isYes ? '#10B981' : 'var(--border)'}`,
                background: isYes ? 'rgba(16, 185, 129, 0.12)' : 'var(--bg-primary)',
                color: isYes ? '#10B981' : 'var(--text-secondary)',
                fontWeight: 600,
                fontSize: 14,
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
            >
              ✓ Yes
            </button>
            <button
              type="button"
              onClick={() => setAnswer(q.id, 'answer_value', 'No')}
              style={{
                flex: 1,
                padding: '12px',
                borderRadius: 10,
                border: `1.5px solid ${isNo ? '#EF4444' : 'var(--border)'}`,
                background: isNo ? 'rgba(239, 68, 68, 0.12)' : 'var(--bg-primary)',
                color: isNo ? '#EF4444' : 'var(--text-secondary)',
                fontWeight: 600,
                fontSize: 14,
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
            >
              ✕ No
            </button>
          </div>
        )

      case 'scale':
      case 'pain':
        const minVal = meta.min ?? 0
        const maxVal = meta.max ?? 10
        const currentVal = currentAns.answer_numeric !== undefined && currentAns.answer_numeric !== null
          ? currentAns.answer_numeric
          : minVal

        return (
          <div style={{ marginTop: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
              <span style={{ fontSize: 13, color: 'var(--text-secondary)', fontWeight: 500 }}>
                Selected Rating:
              </span>
              <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--accent)' }}>
                {currentVal} / {maxVal}
              </span>
            </div>
            <input
              type="range"
              min={minVal}
              max={maxVal}
              value={currentVal}
              onChange={(e) => setAnswer(q.id, 'answer_numeric', parseInt(e.target.value))}
              style={{ width: '100%', accentColor: 'var(--accent)', cursor: 'pointer' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
              <span>{meta.min_label || `${minVal} (None)`}</span>
              <span>{meta.max_label || `${maxVal} (Severe)`}</span>
            </div>
          </div>
        )

      case 'number':
      case 'fever':
      case 'spo2':
      case 'sugar':
        return (
          <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 10 }}>
            <input
              className="input-field"
              type="number"
              step="any"
              placeholder={type === 'fever' ? '98.6' : type === 'spo2' ? '98' : type === 'sugar' ? '110' : '0'}
              value={currentAns.answer_numeric !== undefined && currentAns.answer_numeric !== null ? currentAns.answer_numeric : ''}
              onChange={(e) => setAnswer(q.id, 'answer_numeric', e.target.value === '' ? null : parseFloat(e.target.value))}
              style={{ flex: 1, fontSize: 14 }}
            />
            {(meta.unit || type === 'fever' ? (meta.unit || '°F') : type === 'spo2' ? '%' : type === 'sugar' ? 'mg/dL' : meta.unit) && (
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
                {meta.unit || (type === 'fever' ? '°F' : type === 'spo2' ? '%' : 'mg/dL')}
              </span>
            )}
          </div>
        )

      case 'bp':
        return (
          <div style={{ marginTop: 10, display: 'flex', gap: 10 }}>
            <div style={{ flex: 1 }}>
              <input
                className="input-field"
                type="number"
                placeholder="Systolic (e.g. 120)"
                value={currentAns.answer_numeric !== undefined && currentAns.answer_numeric !== null ? currentAns.answer_numeric : ''}
                onChange={(e) => setAnswer(q.id, 'answer_numeric', e.target.value === '' ? null : parseFloat(e.target.value))}
                style={{ width: '100%', fontSize: 13 }}
              />
              <span style={{ fontSize: 10, color: 'var(--text-muted)', display: 'block', marginTop: 2 }}>Systolic mmHg</span>
            </div>
            <div style={{ flex: 1 }}>
              <input
                className="input-field"
                type="number"
                placeholder="Diastolic (e.g. 80)"
                value={currentAns.answer_value || ''}
                onChange={(e) => setAnswer(q.id, 'answer_value', e.target.value)}
                style={{ width: '100%', fontSize: 13 }}
              />
              <span style={{ fontSize: 10, color: 'var(--text-muted)', display: 'block', marginTop: 2 }}>Diastolic mmHg</span>
            </div>
          </div>
        )

      case 'photo':
        return (
          <div style={{ marginTop: 10 }}>
            {!currentAns.file_url ? (
              <input
                type="file"
                accept="image/*,video/*"
                capture="environment"
                className="input-field"
                style={{ width: '100%', fontSize: 13 }}
                onChange={(e) => {
                  const file = e.target.files[0]
                  if (file) {
                    if (file.type.startsWith('image/')) {
                      const reader = new FileReader()
                      reader.onload = (event) => {
                        const img = new Image()
                        img.onload = () => {
                          const canvas = document.createElement('canvas')
                          const MAX_WIDTH = 800
                          let width = img.width
                          let height = img.height
                          if (width > MAX_WIDTH) {
                            height = Math.round((height * MAX_WIDTH) / width)
                            width = MAX_WIDTH
                          }
                          canvas.width = width
                          canvas.height = height
                          const ctx = canvas.getContext('2d')
                          ctx.drawImage(img, 0, 0, width, height)
                          const compressedDataUrl = canvas.toDataURL('image/jpeg', 0.7)
                          setAnswer(q.id, 'file_url', compressedDataUrl)
                          setAnswer(q.id, 'answer_value', file.name)
                        }
                        img.src = event.target.result
                      }
                      reader.readAsDataURL(file)
                    } else {
                      const reader = new FileReader()
                      reader.onloadend = () => {
                        setAnswer(q.id, 'file_url', reader.result)
                        setAnswer(q.id, 'answer_value', file.name)
                      }
                      reader.readAsDataURL(file)
                    }
                  }
                }}
              />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 8 }}>
                {currentAns.file_url.startsWith('data:video/') ? (
                  <video src={currentAns.file_url} controls style={{ width: '100%', borderRadius: 8, maxHeight: 200, background: '#000' }} />
                ) : (
                  <img src={currentAns.file_url} alt="Preview" style={{ width: '100%', borderRadius: 8, maxHeight: 200, objectFit: 'cover' }} />
                )}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{currentAns.answer_value}</span>
                  <button
                    type="button"
                    className="btn-secondary"
                    style={{ padding: '4px 10px', fontSize: 12 }}
                    onClick={() => {
                      setAnswer(q.id, 'file_url', null)
                      setAnswer(q.id, 'answer_value', null)
                    }}
                  >
                    Remove
                  </button>
                </div>
              </div>
            )}
          </div>
        )

      case 'voice':
        const startRecording = async () => {
          try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
            const recorder = new MediaRecorder(stream)
            const chunks = []
            recorder.ondataavailable = e => chunks.push(e.data)
            recorder.onstop = () => {
              const blob = new Blob(chunks, { type: 'audio/webm' })
              const reader = new FileReader()
              reader.onloadend = () => {
                setAnswer(q.id, 'file_url', reader.result)
                setAnswer(q.id, 'answer_value', 'Voice Note Recorded')
              }
              reader.readAsDataURL(blob)
            }
            recorder.start()
            setMediaRecorder(recorder)
            setRecording(true)
          } catch (err) {
            alert('Microphone access was denied or not supported on this device.')
          }
        }
        const stopRecording = () => {
          mediaRecorder?.stop()
          setRecording(false)
          mediaRecorder?.stream.getTracks().forEach(t => t.stop())
        }
        return (
          <div style={{ marginTop: 10 }}>
            {!currentAns.file_url ? (
              <button
                type="button"
                className="btn-secondary"
                style={{
                  width: '100%',
                  background: recording ? '#EF4444' : 'var(--bg-primary)',
                  color: recording ? 'white' : 'var(--text-primary)',
                  border: '1px solid var(--border)',
                  padding: '10px',
                  borderRadius: 8,
                  fontWeight: 600,
                  fontSize: 13,
                  cursor: 'pointer',
                }}
                onClick={recording ? stopRecording : startRecording}
              >
                {recording ? '⏹ Stop Recording Voice Note' : '🎙 Record Voice Note'}
              </button>
            ) : (
              <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                <audio src={currentAns.file_url} controls style={{ flex: 1, height: 40 }} />
                <button
                  type="button"
                  className="btn-secondary"
                  style={{ padding: '6px 12px', fontSize: 12 }}
                  onClick={() => setAnswer(q.id, 'file_url', null)}
                >
                  Reset
                </button>
              </div>
            )}
          </div>
        )

      case 'text':
      case 'custom_text':
      default:
        return (
          <div style={{ marginTop: 10 }}>
            <textarea
              className="input-field"
              rows={3}
              placeholder="Enter your detailed response or symptom notes..."
              value={currentAns.answer_value || ''}
              onChange={(e) => setAnswer(q.id, 'answer_value', e.target.value)}
              style={{ width: '100%', fontSize: 13, resize: 'vertical' }}
            />
          </div>
        )
    }
  }

  const activeQuestions = activeSurvey ? getQuestionsList(activeSurvey) : []

  return (
    <div className="page-container">
      <Sidebar />
      <main className="main-content">
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <div className="page-header" style={{ marginBottom: 24 }}>
            <h1 className="page-title">Health Check Survey</h1>
            <p className="page-subtitle">
              {activeSurvey ? activeSurvey.title : 'Complete your assigned medical surveys to keep your care team informed.'}
            </p>
          </div>

          {feedback ? (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="glass-card"
              style={{ padding: 36, maxWidth: 620, margin: '0 auto', textAlign: 'center' }}
            >
              <CheckCircle size={52} color="#10B981" style={{ margin: '0 auto 16px' }} />
              <h2 style={{ fontSize: 22, fontWeight: 700, marginBottom: 8, color: 'var(--text-primary)' }}>
                Survey Submitted Successfully!
              </h2>
              <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 20 }}>
                Your responses have been processed by your medical care team and ML risk algorithms.
              </p>

              {feedback.risk_score && (
                <div
                  style={{
                    background: 'var(--bg-primary)',
                    borderRadius: 12,
                    padding: '14px 20px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    marginBottom: 16,
                  }}
                >
                  <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>
                    Evaluated Recovery Status:
                  </span>
                  <span
                    style={{
                      padding: '4px 14px',
                      borderRadius: 20,
                      fontSize: 12,
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      background:
                        feedback.risk_score.risk_level === 'high'
                          ? 'rgba(239, 68, 68, 0.15)'
                          : feedback.risk_score.risk_level === 'medium'
                          ? 'rgba(245, 158, 11, 0.15)'
                          : 'rgba(16, 185, 129, 0.15)',
                      color:
                        feedback.risk_score.risk_level === 'high'
                          ? '#EF4444'
                          : feedback.risk_score.risk_level === 'medium'
                          ? '#F59E0B'
                          : '#10B981',
                    }}
                  >
                    {feedback.risk_score.risk_level} Risk (Score: {feedback.risk_score.score ?? 0})
                  </span>
                </div>
              )}

              {feedback.ai_feedback && (
                <div
                  style={{
                    background: 'linear-gradient(135deg, rgba(37, 99, 235, 0.06) 0%, rgba(16, 185, 129, 0.06) 100%)',
                    border: '1px solid rgba(37, 99, 235, 0.18)',
                    borderRadius: 12,
                    padding: 20,
                    textAlign: 'left',
                    lineHeight: 1.65,
                    marginBottom: 24,
                  }}
                >
                  <p style={{ fontSize: 13, color: 'var(--accent)', fontWeight: 700, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                    💬 AI Clinical Feedback & Instructions
                  </p>
                  <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
                    {feedback.ai_feedback}
                  </p>
                </div>
              )}

              <button
                className="btn-primary"
                style={{ width: '100%', padding: '12px' }}
                onClick={() => {
                  setFeedback(null)
                  setActiveSurvey(null)
                  setAnswers({})
                }}
              >
                Done / Back to Surveys
              </button>
            </motion.div>
          ) : activeSurvey ? (
            <div className="glass-card" style={{ padding: 28, maxWidth: 680, margin: '0 auto' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20, borderBottom: '1px solid var(--border)', paddingBottom: 16 }}>
                <div>
                  <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)' }}>
                    {activeSurvey.title}
                  </h2>
                  {activeSurvey.description && (
                    <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
                      {activeSurvey.description}
                    </p>
                  )}
                </div>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setActiveSurvey(null)}
                  style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', fontSize: 12 }}
                >
                  <ArrowLeft size={14} /> Back
                </button>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                {activeQuestions.map((q, idx) => (
                  <div
                    key={q.id || idx}
                    style={{
                      background: 'var(--bg-card-light)',
                      border: '1px solid var(--border)',
                      borderRadius: 12,
                      padding: 18,
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
                      <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent)', textTransform: 'uppercase' }}>
                        Question {idx + 1}
                      </span>
                      {q.is_required !== false && (
                        <span style={{ fontSize: 11, color: '#EF4444', fontWeight: 600 }}>*Required</span>
                      )}
                    </div>
                    <label style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', display: 'block', lineHeight: 1.4 }}>
                      {q.question_text}
                    </label>

                    {renderInput(q)}
                  </div>
                ))}
              </div>

              <button
                className="btn-primary"
                onClick={handleSubmit}
                disabled={submitting || activeQuestions.length === 0}
                style={{
                  width: '100%',
                  marginTop: 24,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                  padding: '12px',
                  fontSize: 15,
                }}
              >
                <Send size={16} /> {submitting ? 'Submitting Answers...' : 'Submit Survey Answers'}
              </button>
            </div>
          ) : (
            <div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 16 }}>
                {surveys.map(s => {
                  const count = s.survey_questions?.length || s.question_types?.length || 0
                  return (
                    <motion.div
                      key={s.id}
                      whileHover={{ y: -2 }}
                      className="glass-card glass-card-hover"
                      style={{ padding: 22, cursor: 'pointer', borderLeft: '4px solid var(--accent)' }}
                      onClick={() => setActiveSurvey(s)}
                    >
                      <h4 style={{ fontSize: 16, fontWeight: 700, marginBottom: 6, color: 'var(--text-primary)' }}>
                        {s.title}
                      </h4>
                      {s.description && (
                        <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 12, lineHeight: 1.4 }}>
                          {s.description}
                        </p>
                      )}
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 12, paddingTop: 10, borderTop: '1px solid var(--border)' }}>
                        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                          {count} {count === 1 ? 'question' : 'questions'}
                        </span>
                        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent)' }}>
                          Start Survey →
                        </span>
                      </div>
                    </motion.div>
                  )
                })}
              </div>

              {surveys.length === 0 && (
                <div className="glass-card" style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)' }}>
                  <CheckCircle size={36} color="#10B981" style={{ margin: '0 auto 12px' }} />
                  <p style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>You are all caught up!</p>
                  <p style={{ fontSize: 13, marginTop: 4 }}>No pending health surveys assigned at this time.</p>
                </div>
              )}
            </div>
          )}
        </motion.div>
      </main>
    </div>
  )
}
