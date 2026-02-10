import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import AppShell from './components/AppShell';
import BottomNav from './components/BottomNav';
import Register from './pages/Register';
import Recommend from './pages/Recommend';
import Dashboard from './pages/Dashboard';
import Creating from './pages/Creating';
import { loadUserProfile } from './utils/dataAdapter';

function DefaultRedirect() {
  const profile = loadUserProfile();
  return <Navigate to={profile ? '/dashboard' : '/register'} replace />;
}

function RequireProfile({ children }) {
  const profile = loadUserProfile();
  if (!profile) return <Navigate to="/register" replace />;
  return children;
}

function AppContent() {
  const location = useLocation();
  const hideNav = location.pathname === '/creating';

  return (
    <div className="flex flex-col min-h-full">
      <div className="flex-1">
        <Routes>
          <Route path="/" element={<DefaultRedirect />} />
          <Route path="/register" element={<Register />} />
          <Route path="/creating" element={<Creating />} />
          <Route path="/recommend" element={<RequireProfile><Recommend /></RequireProfile>} />
          <Route path="/dashboard" element={<RequireProfile><Dashboard /></RequireProfile>} />
        </Routes>
      </div>
      {!hideNav && <BottomNav />}
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <AppContent />
      </AppShell>
    </BrowserRouter>
  );
}
