import { useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import CardSurface from '../components/CardSurface';
import { confirmRegistrationOtp } from '../utils/dataAdapter';

export default function VerifyOtp() {
  const location = useLocation();
  const navigate = useNavigate();

  const initialUsername = useMemo(() => location.state?.username || '', [location.state]);

  const [username, setUsername] = useState(initialUsername);
  const [otpCode, setOtpCode] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  async function handleVerify(e) {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (!username.trim()) {
      setError('Username is required');
      return;
    }

    if (!otpCode.trim()) {
      setError('OTP code is required');
      return;
    }

    setIsLoading(true);
    try {
      await confirmRegistrationOtp(username, otpCode);
      setSuccess('OTP verified. Your account is now confirmed.');
      setTimeout(() => navigate('/login', { state: { username: username.trim() } }), 900);
    } catch (err) {
      setError(err.message || 'OTP verification failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="min-h-full flex flex-col items-center justify-center px-6 py-12 bg-gradient-to-br from-[#0f1419] via-[#1a1f2e] to-[#1f2942] relative">
      <button
        type="button"
        onClick={() => navigate('/register')}
        className="absolute top-6 left-6 text-white hover:text-white/80 inline-flex items-center gap-2 text-sm font-medium"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M19 12H5M12 19l-7-7 7-7"/>
        </svg>
        Back
      </button>

      <div className="text-center mb-8">
        <h1 className="text-2xl font-bold text-white mb-2">Verify OTP</h1>
        <p className="text-sm text-white/70">Enter the verification code sent to your email.</p>
      </div>

      <CardSurface className="w-full max-w-[320px]">
        <form onSubmit={handleVerify} className="space-y-4">
          <div>
            <label className="text-xs font-medium text-muted mb-1 block">Username</label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="Enter your username"
              className="w-full h-11 px-3 rounded-[14px] border-2 border-primary bg-card text-text outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all text-sm"
              disabled={isLoading}
            />
          </div>

          <div>
            <label className="text-xs font-medium text-muted mb-1 block">OTP Code</label>
            <input
              type="text"
              value={otpCode}
              onChange={e => setOtpCode(e.target.value)}
              placeholder="e.g. 123456"
              className="w-full h-11 px-3 rounded-[14px] border-2 border-primary bg-card text-text outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all text-sm"
              disabled={isLoading}
            />
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              <p className="text-xs text-red-600">{error}</p>
            </div>
          )}

          {success && (
            <div className="bg-green-50 border border-green-200 rounded-lg px-3 py-2">
              <p className="text-xs text-green-700">{success}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={isLoading}
            className="w-full h-11 bg-primary hover:bg-primary-dark text-white font-semibold rounded-[14px] transition-all text-sm shadow-md hover:shadow-lg active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? 'Verifying...' : 'Verify OTP'}
          </button>

          <div className="pt-4 border-t border-border text-center">
            <p className="text-xs text-muted">
              Already verified?{' '}
              <button
                type="button"
                onClick={() => navigate('/login')}
                className="text-primary hover:text-primary-dark font-medium"
              >
                Go to login
              </button>
            </p>
          </div>
        </form>
      </CardSurface>
    </div>
  );
}
