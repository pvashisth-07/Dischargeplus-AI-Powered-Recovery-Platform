import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ClipboardList,
  Send,
  Eye,
  Sparkles,
  RefreshCw,
  Plus,
  Trash2,
  Sliders,
  AlignLeft,
  Camera,
  Mic,
  Hash,
  Heart,
  CheckSquare,
  HelpCircle,
  AlertCircle
} from 'lucide-react'
import Sidebar from '../../components/shared/Sidebar'
import api from '../../lib/api'

const AVAILABLE_TYPES = [
  { id: 'choice', label: 'Multiple Choice', icon: CheckSquare, desc: 'Select from customized options' },
  { id: 'boolean', label: 'Yes / No', icon: HelpCircle, desc: 'Binary confirmation' },
  { id: 'scale', label: 'Scale 0–10', icon: Sliders, desc: 'Rating slider with custom min/max labels' },
  { id: 'number', label: 'Numeric Reading', icon: Hash, desc: 'Value with unit (e.g., °F, mg/dL, bpm)' },
  { id: 'bp', label: 'Blood Pressure', icon: Heart, desc: 'Systolic & Diastolic mmHg' },
  { id: 'photo', label: 'Photo Upload', icon: Camera, desc: 'Wound or affected area picture' },
  { id: 'voice', label: 'Voice Note', icon: Mic, desc: 'Recorded audio symptom description' },
  { id: 'text', label: 'Open Text', icon: AlignLeft, desc: 'Free-form detailed patient response' },
]

export default function SendSurvey() {
  const [patients, setPatients] = useState([])
  const [selectedPatient, setSelectedPatient] = useState('')
  const [selectedPatientObj, setSelectedPatientObj] = useState(null)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [questions, setQuestions] = useState([])
  const [scheduleType, setScheduleType] = useState('one_time')
  const [intervalDays, setIntervalDays] = useState('')
  const [sending, setSending] = useState(false)
  const [preview, setPreview] = useState(false)
  const [success, setSuccess] = useState(false)
  const [loadingAI, setLoadingAI] = useState(false)
  const [aiMetadata, setAiMetadata] = useState(null)

  useEffect(() => {
    api.get('/doctor/patients')
      .then(res => setPatients(res.data || []))
      .catch(() => {})
  }, [])

  const generateAISurvey = async (patientId) => {
    if (!patientId) return
    setLoadingAI(true)
    try {
      const res = await api.post('/ml/generate-dynamic-survey', { patient_id: patientId })
      const data = res.data
      setTitle(data.title || 'Health Check Survey')
      setDescription(data.description || '')
      setAiMetadata({
        diagnosis: data.diagnosis,
        generatedBy: data.generated_by,
      })
      if (Array.isArray(data.questions) && data.questions.length > 0) {
        setQuestions(data.questions.map((q, idx) => ({
          id: q.id || `q_${Date.now()}_${idx}`,
          question_text: q.question_text || '',
          question_type: q.question_type || 'text',
          is_required: q.is_required !== false,
          metadata: q.metadata || {},
        })))
      }
    } catch (err) {
      console.warn('AI survey generation failed, using standard fallback:', err)
      // Fallback default questions if network error
      setTitle('Post-Discharge Health Check')
      setDescription('Please report your recovery symptoms to your care team.')
      setQuestions([
        {
          id: `q_${Date.now()}_1`,
          question_text: 'What is your current body temperature?',
          question_type: 'number',
          is_required: true,
          metadata: { unit: '°F' },
        },
        {
          id: `q_${Date.now()}_2`,
          question_text: 'Rate your overall pain level right now (0 = No pain, 10 = Severe).',
          question_type: 'scale',
          is_required: true,
          metadata: { min: 0, max: 10, min_label: 'No pain', max_label: 'Severe' },
        },
        {
          id: `q_${Date.now()}_3`,
          question_text: 'Are you taking your prescribed medications on schedule?',
          question_type: 'boolean',
          is_required: true,
          metadata: {},
        },
        {
          id: `q_${Date.now()}_4`,
          question_text: 'Describe any unusual symptoms, swelling, or changes since discharge.',
          question_type: 'text',
          is_required: false,
          metadata: {},
        },
      ])
    } finally {
      setLoadingAI(false)
    }
  }

  const handlePatientChange = (patientId) => {
    setSelectedPatient(patientId)
    const p = patients.find(pat => pat.id === patientId)
    setSelectedPatientObj(p || null)
    if (patientId) {
      generateAISurvey(patientId)
    } else {
      setTitle('')
      setDescription('')
      setQuestions([])
      setAiMetadata(null)
    }
  }

  const updateQuestion = (index, field, value) => {
    setQuestions(prev => {
      const next = [...prev]
      next[index] = { ...next[index], [field]: value }
      return next
    })
  }

  const updateQuestionMetadata = (index, metaField, value) => {
    setQuestions(prev => {
      const next = [...prev]
      const currentMeta = next[index].metadata || {}
      next[index] = {
        ...next[index],
        metadata: { ...currentMeta, [metaField]: value },
      }
      return next
    })
  }

  const handleTypeChange = (index, newType) => {
    setQuestions(prev => {
      const next = [...prev]
      const q = next[index]
      let newMeta = {}

      if (newType === 'choice') {
        newMeta = { options: ['Option 1', 'Option 2', 'Option 3'] }
      } else if (newType === 'scale') {
        newMeta = { min: 0, max: 10, min_label: 'None', max_label: 'Severe' }
      } else if (newType === 'number') {
        newMeta = { unit: 'reading' }
      }

      next[index] = {
        ...q,
        question_type: newType,
        metadata: newMeta,
      }
      return next
    })
  }

  const addOptionToChoice = (qIndex) => {
    setQuestions(prev => {
      const next = [...prev]
      const currentOptions = next[qIndex].metadata?.options || []
      next[qIndex] = {
        ...next[qIndex],
        metadata: {
          ...next[qIndex].metadata,
          options: [...currentOptions, `Option ${currentOptions.length + 1}`],
        },
      }
      return next
    })
  }

  const updateChoiceOption = (qIndex, optIndex, val) => {
    setQuestions(prev => {
      const next = [...prev]
      const currentOptions = [...(next[qIndex].metadata?.options || [])]
      currentOptions[optIndex] = val
      next[qIndex] = {
        ...next[qIndex],
        metadata: { ...next[qIndex].metadata, options: currentOptions },
      }
      return next
    })
  }

  const removeChoiceOption = (qIndex, optIndex) => {
    setQuestions(prev => {
      const next = [...prev]
      const currentOptions = (next[qIndex].metadata?.options || []).filter((_, i) => i !== optIndex)
      next[qIndex] = {
        ...next[qIndex],
        metadata: { ...next[qIndex].metadata, options: currentOptions },
      }
      return next
    })
  }

  const addQuestion = () => {
    setQuestions(prev => [
      ...prev,
      {
        id: `q_${Date.now()}_${prev.length + 1}`,
        question_text: '',
        question_type: 'text',
        is_required: true,
        metadata: {},
      },
    ])
  }

  const removeQuestion = (index) => {
    setQuestions(prev => prev.filter((_, i) => i !== index))
  }

  const handleSend = async () => {
    if (!selectedPatient) return alert('Please select a patient.')
    if (!title.trim()) return alert('Please enter a survey title.')
    if (questions.length === 0) return alert('Survey must have at least one question.')

    const emptyText = questions.some(q => !q.question_text.trim())
    if (emptyText) return alert('Please provide question text for all questions.')

    setSending(true)
    try {
      const formattedQuestions = questions.map((q) => ({
        question_text: q.question_text.trim(),
        question_type: q.question_type,
        is_required: q.is_required !== false,
        metadata: q.metadata || {},
      }))

      await api.post('/surveys/create', {
        patient_id: selectedPatient,
        title: title.trim(),
        description: description.trim(),
        questions: formattedQuestions,
        schedule_type: scheduleType,
        schedule_interval_days: scheduleType === 'recurring' && intervalDays ? parseInt(intervalDays) : null,
      })

      setSuccess(true)
      setTimeout(() => setSuccess(false), 4000)
      setTitle('')
      setDescription('')
      setQuestions([])
      setSelectedPatient('')
      setSelectedPatientObj(null)
      setAiMetadata(null)
    } catch (e) {
      alert(e.response?.data?.detail || 'Failed to dispatch survey.')
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="page-container">
      <Sidebar />
      <main className="main-content">
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <div className="page-header" style={{ marginBottom: 24 }}>
            <h1 className="page-title">Send Dynamic Survey</h1>
            <p className="page-subtitle">
              AI automatically crafts disease-tailored questions with custom response types. Review, tweak, and dispatch.
            </p>
          </div>

          {success && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              style={{
                background: 'rgba(16, 185, 129, 0.12)',
                border: '1px solid rgba(16, 185, 129, 0.3)',
                borderRadius: 12,
                padding: '14px 20px',
                marginBottom: 20,
                color: '#10B981',
                fontSize: 14,
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}
            >
              ✓ Dynamic survey successfully dispatched to patient!
            </motion.div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: 24 }}>
            {/* Left Column: Interactive Survey Builder */}
            <div>
              {/* Patient Selection Card */}
              <div className="glass-card" style={{ padding: 22, marginBottom: 20 }}>
                <label className="input-label" style={{ fontWeight: 600, fontSize: 13, marginBottom: 8, display: 'block' }}>
                  Select Target Patient
                </label>
                <select
                  className="input-field"
                  value={selectedPatient}
                  onChange={(e) => handlePatientChange(e.target.value)}
                  style={{ width: '100%', fontSize: 14 }}
                >
                  <option value="">-- Choose Patient to Auto-Generate Protocol --</option>
                  {patients.map(p => (
                    <option key={p.id} value={p.id}>
                      {p.full_name} • {p.diagnosis || 'General Post-Op'} (Discharged {p.discharge_date ? p.discharge_date.substring(0, 10) : 'Recent'})
                    </option>
                  ))}
                </select>
              </div>

              {/* AI Generation Status Banner */}
              {selectedPatient && (
                <div
                  style={{
                    background: 'linear-gradient(135deg, rgba(37, 99, 235, 0.08) 0%, rgba(16, 185, 129, 0.08) 100%)',
                    border: '1px solid rgba(37, 99, 235, 0.25)',
                    borderRadius: 14,
                    padding: '16px 20px',
                    marginBottom: 20,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div
                        style={{
                          width: 34,
                          height: 34,
                          borderRadius: 8,
                          background: 'rgba(37, 99, 235, 0.15)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        <Sparkles size={18} color="var(--accent)" />
                      </div>
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ fontWeight: 700, fontSize: 14, color: 'var(--text-primary)' }}>
                            Dynamic Survey AI Generator
                          </span>
                          <span
                            style={{
                              fontSize: 11,
                              background: 'rgba(37, 99, 235, 0.12)',
                              color: 'var(--accent)',
                              padding: '2px 8px',
                              borderRadius: 6,
                              fontWeight: 700,
                              textTransform: 'uppercase',
                              letterSpacing: '0.04em',
                            }}
                          >
                            Groq + ML
                          </span>
                        </div>
                        <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
                          Tailored specifically for{' '}
                          <strong>{aiMetadata?.diagnosis || selectedPatientObj?.diagnosis || 'patient profile'}</strong>
                        </p>
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() => generateAISurvey(selectedPatient)}
                      disabled={loadingAI}
                      style={{
                        background: 'var(--bg-card)',
                        border: '1px solid var(--accent)',
                        borderRadius: 8,
                        color: 'var(--accent)',
                        fontSize: 12,
                        fontWeight: 600,
                        padding: '6px 12px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6,
                        cursor: loadingAI ? 'not-allowed' : 'pointer',
                        transition: 'all 0.2s',
                      }}
                    >
                      <RefreshCw size={13} className={loadingAI ? 'spin' : ''} />
                      {loadingAI ? 'Synthesizing...' : 'Regenerate with AI'}
                    </button>
                  </div>

                  {loadingAI && (
                    <div style={{ marginTop: 12, fontSize: 12, color: 'var(--accent)', fontWeight: 500, display: 'flex', alignItems: 'center', gap: 8 }}>
                      <RefreshCw size={14} className="spin" />
                      Analyzing clinical recovery trajectory and formatting response widgets...
                    </div>
                  )}
                </div>
              )}

              {/* Survey Title & Description Card */}
              <div className="glass-card" style={{ padding: 22, marginBottom: 20 }}>
                <div style={{ marginBottom: 16 }}>
                  <label className="input-label" style={{ fontWeight: 600, fontSize: 13 }}>Survey Title</label>
                  <input
                    className="input-field"
                    placeholder="e.g. Veins Blockage Recovery Check-in"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    style={{ width: '100%', fontSize: 14 }}
                  />
                </div>

                <div>
                  <label className="input-label" style={{ fontWeight: 600, fontSize: 13 }}>Description / Patient Instructions</label>
                  <textarea
                    className="input-field"
                    rows={2}
                    placeholder="Instructions for the patient on answering these questions..."
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    style={{ width: '100%', fontSize: 13, resize: 'vertical' }}
                  />
                </div>
              </div>

              {/* Questions List & Question Cards */}
              <div style={{ marginBottom: 20 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                  <div>
                    <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>
                      Questions & Response Formats
                    </h3>
                    <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                      Edit questions, add new ones, or change the response type for any question below.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={addQuestion}
                    style={{
                      background: 'var(--accent-light)',
                      border: '1px solid var(--accent)',
                      color: 'var(--accent)',
                      padding: '6px 14px',
                      borderRadius: 8,
                      fontSize: 13,
                      fontWeight: 600,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                      cursor: 'pointer',
                    }}
                  >
                    <Plus size={15} /> Add Question
                  </button>
                </div>

                {questions.length === 0 ? (
                  <div
                    className="glass-card"
                    style={{
                      padding: 36,
                      textAlign: 'center',
                      color: 'var(--text-muted)',
                      borderStyle: 'dashed',
                    }}
                  >
                    <HelpCircle size={32} style={{ margin: '0 auto 10px', opacity: 0.5 }} />
                    <p style={{ fontSize: 14, fontWeight: 500 }}>No questions added yet.</p>
                    <p style={{ fontSize: 12, marginTop: 4 }}>
                      Select a patient above to auto-generate questions, or click "Add Question" to build manually.
                    </p>
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                    <AnimatePresence>
                      {questions.map((q, qIndex) => {
                        const currentTypeObj = AVAILABLE_TYPES.find(t => t.id === q.question_type) || AVAILABLE_TYPES[0]
                        const TypeIcon = currentTypeObj.icon

                        return (
                          <motion.div
                            key={q.id || qIndex}
                            initial={{ opacity: 0, y: 12 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, scale: 0.95 }}
                            className="glass-card"
                            style={{
                              padding: 20,
                              position: 'relative',
                              borderLeft: '4px solid var(--accent)',
                            }}
                          >
                            {/* Question Header & Controls */}
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <span
                                  style={{
                                    fontSize: 12,
                                    fontWeight: 700,
                                    background: 'var(--accent-light)',
                                    color: 'var(--accent)',
                                    padding: '2px 8px',
                                    borderRadius: 6,
                                  }}
                                >
                                  Q{qIndex + 1}
                                </span>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                  <TypeIcon size={14} color="var(--accent)" />
                                  <select
                                    value={q.question_type}
                                    onChange={(e) => handleTypeChange(qIndex, e.target.value)}
                                    style={{
                                      fontSize: 12,
                                      fontWeight: 600,
                                      padding: '3px 8px',
                                      borderRadius: 6,
                                      border: '1px solid var(--border)',
                                      background: 'var(--bg-primary)',
                                      color: 'var(--text-primary)',
                                      cursor: 'pointer',
                                    }}
                                  >
                                    {AVAILABLE_TYPES.map(t => (
                                      <option key={t.id} value={t.id}>
                                        {t.label}
                                      </option>
                                    ))}
                                  </select>
                                </div>
                              </div>

                              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-secondary)', cursor: 'pointer' }}>
                                  <input
                                    type="checkbox"
                                    checked={q.is_required !== false}
                                    onChange={(e) => updateQuestion(qIndex, 'is_required', e.target.checked)}
                                    style={{ accentColor: 'var(--accent)' }}
                                  />
                                  Required
                                </label>
                                <button
                                  type="button"
                                  onClick={() => removeQuestion(qIndex)}
                                  title="Delete question"
                                  style={{
                                    background: 'none',
                                    border: 'none',
                                    color: '#EF4444',
                                    cursor: 'pointer',
                                    padding: 4,
                                    borderRadius: 4,
                                    display: 'flex',
                                    alignItems: 'center',
                                  }}
                                >
                                  <Trash2 size={15} />
                                </button>
                              </div>
                            </div>

                            {/* Question Text Input */}
                            <div style={{ marginBottom: 12 }}>
                              <input
                                className="input-field"
                                value={q.question_text}
                                onChange={(e) => updateQuestion(qIndex, 'question_text', e.target.value)}
                                placeholder="Enter question for the patient..."
                                style={{ width: '100%', fontSize: 13, fontWeight: 500 }}
                              />
                            </div>

                            {/* Response Type Specific Configuration */}
                            {q.question_type === 'choice' && (
                              <div
                                style={{
                                  background: 'var(--bg-primary)',
                                  borderRadius: 8,
                                  padding: 12,
                                  marginTop: 8,
                                }}
                              >
                                <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', display: 'block', marginBottom: 8 }}>
                                  Choice Options:
                                </span>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                                  {(q.metadata?.options || []).map((opt, optIdx) => (
                                    <div key={optIdx} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                      <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>•</span>
                                      <input
                                        className="input-field"
                                        value={opt}
                                        onChange={(e) => updateChoiceOption(qIndex, optIdx, e.target.value)}
                                        style={{ fontSize: 12, padding: '4px 8px', flex: 1 }}
                                      />
                                      {(q.metadata?.options?.length || 0) > 1 && (
                                        <button
                                          type="button"
                                          onClick={() => removeChoiceOption(qIndex, optIdx)}
                                          style={{
                                            background: 'none',
                                            border: 'none',
                                            color: 'var(--text-muted)',
                                            cursor: 'pointer',
                                            padding: 2,
                                          }}
                                        >
                                          ✕
                                        </button>
                                      )}
                                    </div>
                                  ))}
                                  <button
                                    type="button"
                                    onClick={() => addOptionToChoice(qIndex)}
                                    style={{
                                      background: 'none',
                                      border: '1px dashed var(--accent)',
                                      borderRadius: 6,
                                      color: 'var(--accent)',
                                      fontSize: 11,
                                      fontWeight: 600,
                                      padding: '4px 8px',
                                      marginTop: 4,
                                      cursor: 'pointer',
                                      width: 'fit-content',
                                    }}
                                  >
                                    + Add Option
                                  </button>
                                </div>
                              </div>
                            )}

                            {q.question_type === 'scale' && (
                              <div
                                style={{
                                  background: 'var(--bg-primary)',
                                  borderRadius: 8,
                                  padding: 12,
                                  marginTop: 8,
                                  display: 'flex',
                                  gap: 12,
                                }}
                              >
                                <div style={{ flex: 1 }}>
                                  <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                                    Min Label (0)
                                  </label>
                                  <input
                                    className="input-field"
                                    value={q.metadata?.min_label || 'None'}
                                    onChange={(e) => updateQuestionMetadata(qIndex, 'min_label', e.target.value)}
                                    placeholder="e.g. No pain"
                                    style={{ fontSize: 12, padding: '4px 8px', width: '100%' }}
                                  />
                                </div>
                                <div style={{ flex: 1 }}>
                                  <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                                    Max Label (10)
                                  </label>
                                  <input
                                    className="input-field"
                                    value={q.metadata?.max_label || 'Severe'}
                                    onChange={(e) => updateQuestionMetadata(qIndex, 'max_label', e.target.value)}
                                    placeholder="e.g. Worst possible"
                                    style={{ fontSize: 12, padding: '4px 8px', width: '100%' }}
                                  />
                                </div>
                              </div>
                            )}

                            {q.question_type === 'number' && (
                              <div
                                style={{
                                  background: 'var(--bg-primary)',
                                  borderRadius: 8,
                                  padding: 12,
                                  marginTop: 8,
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: 10,
                                }}
                              >
                                <label style={{ fontSize: 11, color: 'var(--text-muted)' }}>Measurement Unit:</label>
                                <input
                                  className="input-field"
                                  value={q.metadata?.unit || ''}
                                  onChange={(e) => updateQuestionMetadata(qIndex, 'unit', e.target.value)}
                                  placeholder="e.g. °F, mg/dL, bpm, %, hours"
                                  style={{ fontSize: 12, padding: '4px 8px', width: 140 }}
                                />
                              </div>
                            )}

                            {q.question_type === 'bp' && (
                              <div style={{ background: 'var(--bg-primary)', borderRadius: 8, padding: 10, marginTop: 8, fontSize: 12, color: 'var(--text-muted)' }}>
                                Displays paired systolic & diastolic numeric inputs in mmHg.
                              </div>
                            )}

                            {q.question_type === 'boolean' && (
                              <div style={{ background: 'var(--bg-primary)', borderRadius: 8, padding: 10, marginTop: 8, fontSize: 12, color: 'var(--text-muted)' }}>
                                Displays interactive [Yes] / [No] binary buttons.
                              </div>
                            )}
                          </motion.div>
                        )
                      })}
                    </AnimatePresence>
                  </div>
                )}
              </div>

              {/* Schedule Settings */}
              <div className="glass-card" style={{ padding: 20, marginBottom: 20 }}>
                <div style={{ display: 'flex', gap: 16 }}>
                  <div style={{ flex: 1 }}>
                    <label className="input-label" style={{ fontWeight: 600, fontSize: 13 }}>Schedule Type</label>
                    <select
                      className="input-field"
                      value={scheduleType}
                      onChange={(e) => setScheduleType(e.target.value)}
                      style={{ width: '100%' }}
                    >
                      <option value="one_time">One-time check-in</option>
                      <option value="recurring">Recurring check-in</option>
                    </select>
                  </div>
                  {scheduleType === 'recurring' && (
                    <div style={{ flex: 1 }}>
                      <label className="input-label" style={{ fontWeight: 600, fontSize: 13 }}>Repeat Frequency (Days)</label>
                      <input
                        className="input-field"
                        type="number"
                        min="1"
                        placeholder="e.g. 1 (Daily), 3, or 7"
                        value={intervalDays}
                        onChange={(e) => setIntervalDays(e.target.value)}
                        style={{ width: '100%' }}
                      />
                    </div>
                  )}
                </div>
              </div>

              {/* Action Buttons */}
              <div style={{ display: 'flex', gap: 12 }}>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setPreview(!preview)}
                  style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '10px 18px' }}
                >
                  <Eye size={16} /> {preview ? 'Hide Preview' : 'Toggle Preview'}
                </button>
                <button
                  type="button"
                  className="btn-primary"
                  onClick={handleSend}
                  disabled={sending || questions.length === 0}
                  style={{
                    flex: 1,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 8,
                    fontSize: 15,
                  }}
                >
                  <Send size={16} /> {sending ? 'Dispatching to Patient...' : 'Send Survey to Patient'}
                </button>
              </div>
            </div>

            {/* Right Column: Live Patient Preview */}
            <div style={{ position: 'sticky', top: 20, height: 'fit-content' }}>
              <div className="glass-card" style={{ padding: 22 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <ClipboardList size={18} color="var(--accent)" />
                    <h3 style={{ fontSize: 15, fontWeight: 700, margin: 0 }}>Live Patient Preview</h3>
                  </div>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    {questions.length} questions
                  </span>
                </div>

                <div
                  style={{
                    background: 'var(--bg-primary)',
                    borderRadius: 12,
                    padding: 16,
                    border: '1px solid var(--border)',
                  }}
                >
                  <h4 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
                    {title || 'Untitled Health Survey'}
                  </h4>
                  {description && (
                    <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 14 }}>
                      {description}
                    </p>
                  )}

                  {questions.length === 0 ? (
                    <div style={{ padding: '24px 0', textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>
                      No questions to preview.
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 14, maxHeight: '65vh', overflowY: 'auto', paddingRight: 4 }}>
                      {questions.map((q, i) => (
                        <div
                          key={q.id || i}
                          style={{
                            padding: '12px',
                            background: 'var(--bg-card)',
                            borderRadius: 8,
                            border: '1px solid var(--border)',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent)' }}>
                              Q{i + 1} • {q.question_type.toUpperCase()}
                            </span>
                            {q.is_required !== false && (
                              <span style={{ fontSize: 10, color: '#EF4444' }}>*Required</span>
                            )}
                          </div>
                          <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>
                            {q.question_text || 'Untitled Question'}
                          </p>

                          {/* Preview widgets */}
                          {q.question_type === 'choice' && (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                              {(q.metadata?.options || ['Option 1', 'Option 2']).map((opt, oIdx) => (
                                <div key={oIdx} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-secondary)' }}>
                                  <input type="radio" disabled name={`preview_${i}`} style={{ accentColor: 'var(--accent)' }} />
                                  <span>{opt}</span>
                                </div>
                              ))}
                            </div>
                          )}

                          {q.question_type === 'boolean' && (
                            <div style={{ display: 'flex', gap: 8 }}>
                              <button type="button" disabled style={{ flex: 1, padding: '6px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--bg-primary)', fontSize: 12, color: 'var(--text-secondary)' }}>
                                Yes
                              </button>
                              <button type="button" disabled style={{ flex: 1, padding: '6px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--bg-primary)', fontSize: 12, color: 'var(--text-secondary)' }}>
                                No
                              </button>
                            </div>
                          )}

                          {q.question_type === 'scale' && (
                            <div>
                              <input type="range" disabled min={q.metadata?.min ?? 0} max={q.metadata?.max ?? 10} value={5} style={{ width: '100%', accentColor: 'var(--accent)' }} />
                              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-muted)' }}>
                                <span>{q.metadata?.min_label || '0 (None)'}</span>
                                <span>{q.metadata?.max_label || '10 (Severe)'}</span>
                              </div>
                            </div>
                          )}

                          {q.question_type === 'number' && (
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                              <input type="number" disabled placeholder="0.0" style={{ width: '100%', padding: '6px', borderRadius: 6, border: '1px solid var(--border)', fontSize: 12, background: 'var(--bg-primary)' }} />
                              {q.metadata?.unit && (
                                <span style={{ fontSize: 12, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                                  {q.metadata.unit}
                                </span>
                              )}
                            </div>
                          )}

                          {q.question_type === 'bp' && (
                            <div style={{ display: 'flex', gap: 6 }}>
                              <input disabled placeholder="Systolic (120)" style={{ flex: 1, padding: '6px', borderRadius: 6, border: '1px solid var(--border)', fontSize: 12, background: 'var(--bg-primary)' }} />
                              <input disabled placeholder="Diastolic (80)" style={{ flex: 1, padding: '6px', borderRadius: 6, border: '1px solid var(--border)', fontSize: 12, background: 'var(--bg-primary)' }} />
                            </div>
                          )}

                          {q.question_type === 'photo' && (
                            <div style={{ padding: '10px', border: '1px dashed var(--border)', borderRadius: 6, textAlign: 'center', fontSize: 11, color: 'var(--text-muted)' }}>
                              📷 Photo / Video upload prompt
                            </div>
                          )}

                          {q.question_type === 'voice' && (
                            <div style={{ padding: '8px', border: '1px solid var(--border)', borderRadius: 6, textAlign: 'center', fontSize: 11, color: 'var(--text-muted)' }}>
                              🎙 Voice recording widget
                            </div>
                          )}

                          {q.question_type === 'text' && (
                            <textarea disabled rows={2} placeholder="Patient enters detailed symptoms..." style={{ width: '100%', padding: '6px', borderRadius: 6, border: '1px solid var(--border)', fontSize: 12, background: 'var(--bg-primary)', resize: 'none' }} />
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      </main>
    </div>
  )
}
