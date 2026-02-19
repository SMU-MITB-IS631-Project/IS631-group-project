import { useNavigate, useLocation } from 'react-router-dom';
import { loadUserProfile } from '../utils/dataAdapter';

const preProfileTabs = [
  { path: '/register', label: 'Profile', icon: ProfileIcon },
];

const postProfileTabs = [
  { path: '/dashboard', label: 'Dashboard', icon: DashboardIcon },
  { path: '/recommend', label: 'Recommend', icon: RecommendIcon },
];

export default function BottomNav() {
  const navigate = useNavigate();
  const location = useLocation();
  const hasProfile = !!loadUserProfile();

  const tabs = hasProfile ? postProfileTabs : preProfileTabs;

  return (
    <nav className="sticky bottom-0 left-0 right-0 bg-gradient-to-b from-gray-50 to-gray-100 border-t-2 border-black z-50 shrink-0 relative overflow-hidden shadow-[0_-8px_24px_rgba(0,0,0,0.2),inset_0_2px_0_rgba(255,255,255,0.8),inset_0_-2px_0_rgba(0,0,0,0.1)]">
      {/* Glossy shine overlay - more prominent */}
      <div style={{background: 'linear-gradient(180deg, rgba(255,255,255,0.95) 0%, rgba(255,255,255,0.4) 40%, rgba(255,255,255,0) 100%)', opacity: 0.8}} className="absolute inset-0 pointer-events-none" />
      <div className="flex relative z-10">
        {tabs.map((tab, idx) => {
          const active = location.pathname === tab.path;
          return (
            <div key={tab.path} className="flex-1 flex flex-col items-center py-2.5">
              {idx > 0 && <div className="absolute left-1/2 top-1 bottom-1 w-0.5 bg-black/20" style={{height: '80%', top: '10%'}} />}
              <button
                onClick={() => navigate(tab.path)}
                className={`flex-1 w-full flex flex-col items-center justify-center gap-0.5 transition-colors ${
                  active ? 'text-primary' : 'text-muted'
                }`}
              >
                <tab.icon active={active} />
                <span className="text-[11px] font-medium">{tab.label}</span>
              </button>
            </div>
          );
        })}
      </div>
    </nav>
  );
}

function ProfileIcon({ active }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={active ? 2.2 : 1.8} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="8" r="4" />
      <path d="M4 20c0-4 4-6 8-6s8 2 8 6" />
    </svg>
  );
}

function RecommendIcon({ active }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={active ? 2.2 : 1.8} strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="14" rx="3" />
      <path d="M3 10h18" />
    </svg>
  );
}

function DashboardIcon({ active }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={active ? 2.2 : 1.8} strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </svg>
  );
}
