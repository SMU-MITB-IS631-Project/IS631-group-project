import { useNavigate } from 'react-router-dom';
import CardSurface from '../components/CardSurface';

export default function Landing() {
  const navigate = useNavigate();

  return (
    <div className="min-h-full flex flex-col items-center justify-center px-6 py-12 bg-gradient-to-br from-[#0f1419] via-[#1a1f2e] to-[#1f2942]">
      {/* Logo & Branding */}
      <div className="text-center mb-12">
        <div className="mb-6 flex justify-center">
          {/* Simple Card Icon Logo */}
          <svg 
            width="110" 
            height="110" 
            viewBox="0 0 80 80" 
            fill="none" 
            className="drop-shadow-lg"
          >
            {/* Card background */}
            <rect 
              x="10" 
              y="20" 
              width="60" 
              height="40" 
              rx="6" 
              fill="#D4AF37" 
              className="opacity-90"
            />
            {/* Card shine effect */}
            <rect 
              x="10" 
              y="20" 
              width="60" 
              height="8" 
              fill="white" 
              className="opacity-20"
            />
            {/* Chip */}
            <rect 
              x="18" 
              y="32" 
              width="14" 
              height="12" 
              rx="2" 
              fill="#8B7355"
            />
            {/* Card lines */}
            <line x1="42" y1="38" x2="62" y2="38" stroke="white" strokeWidth="2" strokeLinecap="round" className="opacity-60" />
            <line x1="42" y1="44" x2="55" y2="44" stroke="white" strokeWidth="2" strokeLinecap="round" className="opacity-60" />
            {/* Tracking dots */}
            <circle cx="20" cy="68" r="3" fill="#6B5B95" />
            <circle cx="32" cy="68" r="3" fill="#6B5B95" />
            <circle cx="48" cy="68" r="3" fill="#6B5B95" className="opacity-50" />
            <circle cx="60" cy="68" r="3" fill="#6B5B95" className="opacity-50" />
          </svg>
        </div>
        
        <h1 className="text-3xl font-bold text-white mb-2 tracking-tight">
          CardTracker
        </h1>
        <p className="text-sm text-white/70 max-w-[260px] mx-auto leading-relaxed">
          Track your card spending and get smart recommendations
        </p>
      </div>

      {/* Action Buttons */}
      <CardSurface className="w-full max-w-[320px]">
        <div className="space-y-3">
          <button
            type="button"
            onClick={() => navigate('/login')}
            className="w-full h-12 bg-primary hover:bg-primary-dark text-white font-semibold rounded-[14px] transition-all text-sm shadow-md hover:shadow-lg active:scale-[0.98]"
          >
            Login
          </button>
          
          <button
            type="button"
            onClick={() => navigate('/register')}
            className="w-full h-12 border-2 border-primary text-primary hover:bg-primary hover:text-white font-semibold rounded-[14px] transition-all text-sm active:scale-[0.98]"
          >
            Create Account
          </button>
        </div>
        
        <div className="mt-6 pt-4 border-t border-border">
          <p className="text-xs text-gray-400 text-center">
            New user? Create an account to get started
          </p>
        </div>
      </CardSurface>

      {/* Footer */}
      <div className="mt-12 text-center">
        <p className="text-xs text-white/60 opacity-60">
          © 2026 CardTracker
        </p>
      </div>
    </div>
  );
}
