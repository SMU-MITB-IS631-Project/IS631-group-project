import { useNavigate } from 'react-router-dom';
import CardSurface from '../components/CardSurface';

export default function CardReward() {
  const navigate = useNavigate();

  return (
    <div className="px-4 pt-6 pb-10">
      <div className="mb-4 px-[6px] pt-2 flex items-center justify-between">
        <button
          type="button"
          onClick={() => navigate('/dashboard')}
          className="text-sm text-white/85 hover:text-white transition-colors"
        >
          ← Back
        </button>
        <h1 className="text-[20px] font-semibold tracking-tight text-white">Card Reward</h1>
        <span className="w-[42px]" />
      </div>

      <CardSurface className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wide">Card Reward</h2>
          <span className="text-xs text-muted">History</span>
        </div>
        <p className="text-xs text-muted">View your card reward history here.</p>
      </CardSurface>

      <CardSurface>
        <p className="text-sm text-muted text-center py-6">No reward records yet.</p>
      </CardSurface>
    </div>
  );
}
