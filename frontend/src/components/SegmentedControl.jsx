export default function SegmentedControl({ options, value, onChange }) {
  return (
    <div className="flex bg-[#EDE8E1] rounded-[14px] p-1">
      {options.map(opt => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={`flex-1 py-2.5 text-sm font-medium rounded-[12px] transition-all ${
            value === opt.value
              ? 'bg-white text-text shadow-sm'
              : 'text-muted hover:text-text'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
