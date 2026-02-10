import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { loadUserProfile } from '../utils/dataAdapter';

export default function Creating() {
  const navigate = useNavigate();

  useEffect(() => {
    if (!loadUserProfile()) {
      navigate('/register', { replace: true });
      return;
    }
    const timer = setTimeout(() => navigate('/dashboard', { replace: true }), 800);
    return () => clearTimeout(timer);
  }, [navigate]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[70vh] px-6 text-center">
      {/* Spinner */}
      <div className="w-10 h-10 border-[3px] border-border border-t-primary rounded-full animate-spin mb-6" />
      <h1 className="text-lg font-semibold text-text mb-1.5">Setting up your wallet…</h1>
      <p className="text-sm text-muted">Preparing your dashboard and recommendations</p>
    </div>
  );
}
