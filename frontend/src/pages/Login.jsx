import { useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import CardSurface from '../components/CardSurface';
import { loginUser } from '../utils/dataAdapter';

export default function Login() {
  const location = useLocation();
  const navigate = useNavigate();
  const initialUsername = useMemo(() => location.state?.username || '', [location.state]);
  const [username, setUsername] = useState(initialUsername);
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [requiresOtpVerification, setRequiresOtpVerification] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  async function handleLogin(e) {
    e.preventDefault();
    setError('');
    setRequiresOtpVerification(false);

    if (!username.trim()) {
      setError('Username is required');
      return;
    }

    if (!password.trim()) {
      setError('Password is required');
      return;
    }

    setIsLoading(true);

    try {
      // Call the backend login endpoint
      await loginUser(username, password);
      // Login successful, navigate to dashboard
      navigate('/dashboard');
    } catch (err) {
      console.error('Login error:', err);
      if (err.message.includes('User not found')) {
        setError('User not found. Please register first.');
      } else if (err.message.toLowerCase().includes('not confirmed')) {
        setError('Account not confirmed. Please complete OTP verification first.');
        setRequiresOtpVerification(true);
      } else if (err.message.toLowerCase().includes('invalid username or password')) {
        setError('Invalid username or password. Please try again.');
      } else {
        setError(err.message || 'Login failed. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="min-h-full flex flex-col items-center justify-center px-6 py-12 bg-gradient-to-br from-[#0f1419] via-[#1a1f2e] to-[#1f2942] relative">
      {/* Back button - fixed top-left */}
      <button
        type="button"
        onClick={() => navigate('/')}
        className="absolute top-6 left-6 text-white hover:text-white/80 inline-flex items-center gap-2 text-sm font-medium"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M19 12H5M12 19l-7-7 7-7"/>
        </svg>
        Back
      </button>

      {/* Logo */}
      <div className="mb-8 flex justify-center">
        <svg width="100" height="100" viewBox="0 0 80 80" fill="none" className="drop-shadow-lg">
          <rect x="10" y="20" width="60" height="40" rx="6" fill="#D4AF37" className="opacity-90"/>
          <rect x="10" y="20" width="60" height="8" fill="white" className="opacity-20"/>
          <rect x="18" y="32" width="14" height="12" rx="2" fill="#8B7355"/>
          <line x1="42" y1="38" x2="62" y2="38" stroke="white" strokeWidth="2" strokeLinecap="round" className="opacity-60"/>
          <line x1="42" y1="44" x2="55" y2="44" stroke="white" strokeWidth="2" strokeLinecap="round" className="opacity-60"/>
          <circle cx="20" cy="68" r="3" fill="#6B5B95"/>
          <circle cx="32" cy="68" r="3" fill="#6B5B95"/>
          <circle cx="48" cy="68" r="3" fill="#6B5B95" className="opacity-50"/>
          <circle cx="60" cy="68" r="3" fill="#6B5B95" className="opacity-50"/>
        </svg>
      </div>
      {/* Header */}
      <div className="text-center mb-8">
        <h1 className="text-2xl font-bold text-white mb-2">
          Welcome Back
        </h1>
        <p className="text-sm text-white/70">
          Login to continue tracking your spendings
        </p>
      </div>

      {/* Login Form */}
      <CardSurface className="w-full max-w-[320px]">
        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="text-xs font-medium text-muted mb-1 block">
              Username
            </label>
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
            <label className="text-xs font-medium text-muted mb-1 block">
              Password
            </label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="Enter your password"
                className="hide-password-reveal w-full h-11 px-3 pr-12 rounded-[14px] border-2 border-primary bg-card text-text outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all text-sm"
                disabled={isLoading}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-primary hover:text-primary-dark"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M17.94 17.94A10.94 10.94 0 0 1 12 20C7 20 2.73 16.11 1 12c.92-2.19 2.36-4.04 4.12-5.38"/>
                    <path d="M9.9 4.24A10.94 10.94 0 0 1 12 4c5 0 9.27 3.89 11 8a11.84 11.84 0 0 1-1.67 2.68"/>
                    <path d="M14.12 14.12A3 3 0 0 1 9.88 9.88"/>
                    <line x1="1" y1="1" x2="23" y2="23"/>
                  </svg>
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12z"/>
                    <circle cx="12" cy="12" r="3"/>
                  </svg>
                )}
              </button>
            </div>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              <p className="text-xs text-red-600">{error}</p>
              {requiresOtpVerification && (
                <button
                  type="button"
                  onClick={() => navigate('/verify-otp', { state: { username: username.trim() } })}
                  className="mt-1 text-xs text-primary hover:text-primary-dark font-medium underline"
                >
                  Go to Verify OTP
                </button>
              )}
            </div>
          )}

          <button
            type="submit"
            disabled={isLoading}
            className="w-full h-11 bg-primary hover:bg-primary-dark text-white font-semibold rounded-[14px] transition-all text-sm shadow-md hover:shadow-lg active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? 'Logging in...' : 'Login'}
          </button>

          <div className="pt-4 border-t border-border text-center">
            <p className="text-xs text-muted">
              Don't have an account?{' '}
              <button
                type="button"
                onClick={() => navigate('/register')}
                className="text-primary hover:text-primary-dark font-medium"
              >
                Register here
              </button>
            </p>
          </div>
        </form>
      </CardSurface>
    </div>
  );
}
