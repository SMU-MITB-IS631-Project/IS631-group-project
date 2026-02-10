import { useNavigate, useLocation } from 'react-router-dom';
import { loadUserProfile } from '../utils/dataAdapter';

const preProfileTabs = [
  { path: '/register', label: 'Profile', icon: ProfileIcon },
];

const postProfileTabs = [
  { path: '/recommend', label: 'Recommend', icon: RecommendIcon },
  { path: '/dashboard', label: 'Dashboard', icon: DashboardIcon },
];

export default function BottomNav() {
  const navigate = useNavigate();
  const location = useLocation();
  const hasProfile = !!loadUserProfile();

  const tabs = hasProfile ? postProfileTabs : preProfileTabs;

  return (
    <nav className="sticky bottom-0 left-0 right-0 bg-white border-t border-border z-50 shrink-0">
      <div className="flex">
        {tabs.map(tab => {
          const active = location.pathname === tab.path;
          return (
            <button
              key={tab.path}
              onClick={() => navigate(tab.path)}
              className={`flex-1 flex flex-col items-center py-2.5 gap-0.5 transition-colors ${
                active ? 'text-primary' : 'text-muted'
              }`}
            >
              <tab.icon active={active} />
              <span className="text-[11px] font-medium">{tab.label}</span>
            </button>
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
