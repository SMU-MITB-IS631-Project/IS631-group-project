export default function AppShell({ children }) {
  return (
    <div className="min-h-screen flex items-start justify-center bg-[#E8E2DA] py-[4vh]">
      <div className="relative w-[390px] max-w-[100vw] h-[min(812px,92vh)] rounded-[2rem] border border-[#D5CFC7] shadow-[0_12px_48px_rgba(0,0,0,0.12)] overflow-hidden flex flex-col bg-gradient-to-br from-[#0f1419] via-[#1a1f2e] to-[#1f2942]">
        {/* Background pattern — inside the frame */}
        <div
          className="pointer-events-none absolute inset-0 z-0 opacity-10"
          style={{
            backgroundImage:
              'url("data:image/svg+xml,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20width%3D%27240%27%20height%3D%27240%27%20viewBox%3D%270%200%20240%20240%27%20fill%3D%27none%27%20stroke%3D%27%235B556B%27%20stroke-width%3D%271.2%27%20stroke-linecap%3D%27round%27%20stroke-linejoin%3D%27round%27%3E%0A%20%20%3Ccircle%20cx%3D%2734%27%20cy%3D%2740%27%20r%3D%2712%27/%3E%0A%20%20%3Ccircle%20cx%3D%2734%27%20cy%3D%2740%27%20r%3D%276%27/%3E%0A%20%20%3Cg%20transform%3D%27rotate%28-6%20170%2036%29%27%3E%0A%20%20%20%20%3Crect%20x%3D%27138%27%20y%3D%2718%27%20width%3D%2764%27%20height%3D%2736%27%20rx%3D%275%27/%3E%0A%20%20%20%20%3Cline%20x1%3D%27146%27%20y1%3D%2736%27%20x2%3D%27194%27%20y2%3D%2736%27/%3E%0A%20%20%3C/g%3E%0A%20%20%3Cg%20transform%3D%27rotate%284%2039%20150%29%27%3E%0A%20%20%20%20%3Crect%20x%3D%2718%27%20y%3D%27120%27%20width%3D%2742%27%20height%3D%2760%27%20rx%3D%273%27/%3E%0A%20%20%20%20%3Cline%20x1%3D%2724%27%20y1%3D%27136%27%20x2%3D%2752%27%20y2%3D%27136%27/%3E%0A%20%20%20%20%3Cline%20x1%3D%2724%27%20y1%3D%27148%27%20x2%3D%2752%27%20y2%3D%27148%27/%3E%0A%20%20%20%20%3Cline%20x1%3D%2724%27%20y1%3D%27160%27%20x2%3D%2744%27%20y2%3D%27160%27/%3E%0A%20%20%3C/g%3E%0A%20%20%3Cg%20transform%3D%27rotate%283%20130%20126%29%27%3E%0A%20%20%20%20%3Cpolyline%20points%3D%2796%2C140%20118%2C118%20140%2C130%20162%2C108%27/%3E%0A%20%20%20%20%3Cpolyline%20points%3D%27162%2C108%20158%2C112%20154%2C106%27/%3E%0A%20%20%3C/g%3E%0A%20%20%3Cg%20transform%3D%27rotate%28-2%20188%20176%29%27%3E%0A%20%20%20%20%3Crect%20x%3D%27172%27%20y%3D%27162%27%20width%3D%278%27%20height%3D%2718%27/%3E%0A%20%20%20%20%3Crect%20x%3D%27186%27%20y%3D%27154%27%20width%3D%278%27%20height%3D%2726%27/%3E%0A%20%20%20%20%3Crect%20x%3D%27200%27%20y%3D%27146%27%20width%3D%278%27%20height%3D%2734%27/%3E%0A%20%20%3C/g%3E%0A%20%20%3Cg%20transform%3D%27rotate%286%2092%20200%29%27%3E%0A%20%20%20%20%3Crect%20x%3D%2774%27%20y%3D%27188%27%20width%3D%2736%27%20height%3D%2722%27%20rx%3D%273%27/%3E%0A%20%20%20%20%3Cline%20x1%3D%2782%27%20y1%3D%27199%27%20x2%3D%27102%27%20y2%3D%27199%27/%3E%0A%20%20%3C/g%3E%0A%3C/svg%3E")',
            backgroundSize: '240px 240px',
            maskImage:
              'linear-gradient(to bottom, transparent 0%, rgba(0,0,0,0.92) 10%, rgba(0,0,0,1) 20%)',
            WebkitMaskImage:
              'linear-gradient(to bottom, transparent 0%, rgba(0,0,0,0.92) 10%, rgba(0,0,0,1) 20%)',
          }}
        />

        {/* Scrollable content area */}
        <div className="relative z-10 flex-1 overflow-y-auto overflow-x-hidden no-scrollbar">
          {children}
        </div>
      </div>
    </div>
  );
}
