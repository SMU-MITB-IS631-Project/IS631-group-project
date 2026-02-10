export default function CardSurface({ children, className = '' }) {
  return (
    <div className={`bg-card rounded-[18px] shadow-[0_8px_24px_rgba(0,0,0,0.08)] p-4 ${className}`}>
      {children}
    </div>
  );
}
