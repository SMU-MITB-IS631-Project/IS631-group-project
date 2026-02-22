export default function CardSurface({ children, className = '' }) {
  return (
    <div className={`relative bg-card rounded-[18px] shadow-[0_10px_32px_rgba(0,0,0,0.12),0_0_0_1px_rgba(255,255,255,0.5)] p-4 overflow-hidden ${className}`}>
      {/* Glossy shine overlay */}
      <div 
        className="absolute inset-0 rounded-[18px] pointer-events-none"
        style={{
          background: 'linear-gradient(135deg, rgba(255,255,255,0.4) 0%, rgba(255,255,255,0) 50%)',
          opacity: 0.6,
        }}
      />
      {/* Content */}
      <div className="relative z-10">
        {children}
      </div>
    </div>
  );
}
