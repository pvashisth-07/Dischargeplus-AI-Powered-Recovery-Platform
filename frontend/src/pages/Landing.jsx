import { Link } from 'react-router-dom'
import { Activity, ArrowRight } from 'lucide-react'
import './Landing.css'

export default function Landing() {
  return (
    <div className="landing-page">
      <div className="landing-hero-overlay" />
      <div className="landing-content">
        <div className="landing-logo-group">
          <div className="landing-logo-icon">
            <Activity size={32} />
          </div>
          <h1 className="landing-brand">Discharge<span>+</span></h1>
        </div>
        <p className="landing-tagline">Recovery Redefined</p>
        
        <p className="landing-description">
          An intelligent post-discharge care platform designed to reduce readmissions, 
          empower patients, and streamline clinical workflows through continuous AI-powered monitoring.
        </p>

        <div className="landing-login-options">
          <Link to="/login" className="landing-btn-solid">
            Hospital Admin Login <ArrowRight size={18} style={{ marginLeft: 4 }} />
          </Link>
          
          <div className="landing-secondary-logins">
            <Link to="/doctor-login" className="landing-btn-outline">
              Doctor Portal
            </Link>
            <Link to="/patient-login" className="landing-btn-outline">
              Patient Portal
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
