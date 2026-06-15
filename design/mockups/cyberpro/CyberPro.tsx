import React, { useEffect, useState } from 'react';
import './_group.css';

const IconGrid = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="7" height="7" />
    <rect x="14" y="3" width="7" height="7" />
    <rect x="14" y="14" width="7" height="7" />
    <rect x="3" y="14" width="7" height="7" />
  </svg>
);

const IconUser = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </svg>
);

const IconPen = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 20h9" />
    <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
  </svg>
);

const IconList = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="8" y1="6" x2="21" y2="6" />
    <line x1="8" y1="12" x2="21" y2="12" />
    <line x1="8" y1="18" x2="21" y2="18" />
    <line x1="3" y1="6" x2="3.01" y2="6" />
    <line x1="3" y1="12" x2="3.01" y2="12" />
    <line x1="3" y1="18" x2="3.01" y2="18" />
  </svg>
);

const IconSend = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="22" y1="2" x2="11" y2="13" />
    <polygon points="22 2 15 22 11 13 2 9 22 2" />
  </svg>
);

const IconBarChart = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="20" x2="12" y2="10" />
    <line x1="18" y1="20" x2="18" y2="4" />
    <line x1="6" y1="20" x2="6" y2="16" />
  </svg>
);

const IconInbox = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="22 12 16 12 14 15 10 15 8 12 2 12" />
    <path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
  </svg>
);

const IconSearch = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="11" cy="11" r="8" />
    <line x1="21" y1="21" x2="16.65" y2="16.65" />
  </svg>
);

const IconBell = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
    <path d="M13.73 21a2 2 0 0 1-3.46 0" />
  </svg>
);

const AnimatedCounter = ({ end, duration = 1200, isFloat = false, prefix = '', suffix = '' }: { end: number, duration?: number, isFloat?: boolean, prefix?: string, suffix?: string }) => {
  const [count, setCount] = useState(0);

  useEffect(() => {
    let startTimestamp: number | null = null;
    const step = (timestamp: number) => {
      if (!startTimestamp) startTimestamp = timestamp;
      const progress = Math.min((timestamp - startTimestamp) / duration, 1);
      // easeOutExpo
      const easeProgress = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
      setCount(easeProgress * end);
      if (progress < 1) {
        window.requestAnimationFrame(step);
      }
    };
    window.requestAnimationFrame(step);
  }, [end, duration]);

  const display = isFloat ? count.toFixed(1) : Math.floor(count).toLocaleString('en-US');
  
  return <span className="font-mono text-2xl font-semibold tracking-tight">{prefix}{display}{suffix}</span>;
};

export function CyberPro() {
  return (
    <div className="fmail-cyberpro-wrapper">
      <div className="bg-orb bg-orb-1" />
      <div className="bg-orb bg-orb-2" />
      <div className="bg-orb bg-orb-3" />
      <div className="aurora-band" />
      <div className="dot-grid" />

      {/* Sidebar */}
      <aside className="w-[220px] shrink-0 border-r border-[#8B5CF6]/10 bg-[#040410]/80 backdrop-blur-xl z-10 flex flex-col relative h-full">
        {/* Top */}
        <div className="h-16 flex items-center px-4 gap-3 border-b border-[#8B5CF6]/10">
          <svg width="28" height="28" viewBox="0 0 52 52" xmlns="http://www.w3.org/2000/svg" className="shrink-0">
            <defs>
              <linearGradient id="logoGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#7C3AED"/>
                <stop offset="100%" stopColor="#06B6D4"/>
              </linearGradient>
            </defs>
            <rect width="52" height="52" rx="14" fill="url(#logoGrad)" opacity="0.18"/>
            <rect x="2" y="2" width="48" height="48" rx="12" fill="none" stroke="url(#logoGrad)" strokeWidth="2"/>
            <rect x="10" y="16" width="32" height="20" rx="3" fill="none" stroke="#8B5CF6" strokeWidth="1.8"/>
            <path d="M10 18 L26 28 L42 18" stroke="#06B6D4" strokeWidth="1.8" fill="none" strokeLinecap="round"/>
          </svg>
          <div className="flex flex-col">
            <span className="text-sm font-semibold text-white leading-tight tracking-wide">FMail Sender Pro</span>
            <span className="text-[10px] text-[#8B5CF6] font-mono leading-none mt-0.5">v3.1.0</span>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 py-4 flex flex-col gap-1 px-2">
          {[
            { label: 'Дашборд', icon: <IconGrid />, active: true },
            { label: 'Аккаунты', icon: <IconUser /> },
            { label: 'Создать письмо', icon: <IconPen /> },
            { label: 'Получатели', icon: <IconList /> },
            { label: 'Рассылка', icon: <IconSend /> },
            { label: 'Аналитика', icon: <IconBarChart /> },
            { label: 'Входящие', icon: <IconInbox />, badge: '3' },
          ].map((item, i) => (
            <button key={i} className={`sidebar-item flex items-center justify-between px-3 py-2.5 rounded text-sm w-full text-left group
              ${item.active ? 'active text-white' : 'text-[#6666AA]'}`}>
              <div className="flex items-center gap-3">
                <span className={item.active ? 'text-[#8B5CF6]' : 'text-[#6666AA] group-hover:text-white transition-colors'}>
                  {item.icon}
                </span>
                <span className="heading text-[13px]" style={{ fontWeight: 600 }}>{item.label}</span>
              </div>
              {item.badge && (
                <span className="bg-[#8B5CF6]/20 text-[#8B5CF6] border border-[#8B5CF6]/30 text-[10px] font-mono px-1.5 py-0.5 rounded-full flex items-center justify-center min-w-[20px]">
                  {item.badge}
                </span>
              )}
            </button>
          ))}
        </nav>

        {/* Bottom */}
        <div className="p-4 border-t border-[#8B5CF6]/10">
          <div className="bg-[#8B5CF6]/5 border border-[#8B5CF6]/20 rounded-md p-3 flex items-center gap-3">
            <div className="license-pulse" />
            <span className="text-xs font-mono text-[#8B5CF6]">PRO • 127 дней</span>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 z-10 h-full overflow-y-auto">
        {/* Header */}
        <header className="h-16 border-b border-[#8B5CF6]/10 bg-[#040410]/60 backdrop-blur-md flex items-center justify-between px-8 sticky top-0 z-20">
          <h1 className="heading text-[22px] text-gradient">Дашборд</h1>
          
          <div className="flex items-center gap-3">
            <button className="text-[#6666AA] hover:text-white transition-colors relative p-2 rounded-lg hover:bg-white/5">
              <IconBell />
              <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 bg-[#EF4444] border border-[#040410] rounded-full"></span>
            </button>
          </div>
        </header>

        {/* Dashboard body */}
        <div className="p-8 max-w-[1200px] mx-auto w-full flex flex-col gap-6">
          
          {/* KPIs */}
          <div className="grid grid-cols-4 gap-4">
            {[
              { label: 'Отправлено', val: 12847, color: 'cyan', colorHex: '#06B6D4', badge: '+14%', badgeColor: 'green' },
              { label: 'Доставлено', val: 92.9, isFloat: true, suffix: '%', color: 'violet', colorHex: '#8B5CF6', badge: '+1.1%', badgeColor: 'green' },
              { label: 'Открытий', val: 35.3, isFloat: true, suffix: '%', color: 'yellow', colorHex: '#F59E0B', badge: '+3.7%', badgeColor: 'green' },
              { label: 'Ошибок', val: 904, color: 'red', colorHex: '#EF4444', badge: '7.1%', badgeColor: 'red' },
            ].map((kpi, i) => (
              <div key={i} className="kpi-card p-5 flex flex-col justify-between h-[120px]" style={{ animationDelay: `${i * 0.1}s` }}>
                <div className="flex justify-between items-start">
                  <span className="text-xs font-medium text-[#6666AA] uppercase tracking-wider">{kpi.label}</span>
                  <div className="p-1 rounded bg-[#ffffff]/5">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={kpi.colorHex} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
                    </svg>
                  </div>
                </div>
                
                <div className="flex items-end justify-between mt-2">
                  <div className="flex items-baseline gap-2">
                    <AnimatedCounter end={kpi.val} isFloat={kpi.isFloat} suffix={kpi.suffix} />
                  </div>
                  <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded bg-${kpi.badgeColor}-500/10 text-${kpi.badgeColor}-400 border border-${kpi.badgeColor}-500/20`}>
                    {kpi.badge}
                  </span>
                </div>

                <div className="absolute bottom-0 left-0 w-full h-6 opacity-40">
                  <svg width="100%" height="100%" preserveAspectRatio="none" viewBox="0 0 100 24">
                    <polyline points="0,24 15,18 30,22 45,12 60,16 75,6 85,10 100,2" fill="none" stroke={kpi.colorHex} strokeWidth="1.5" strokeOpacity="0.5" />
                  </svg>
                </div>
              </div>
            ))}
          </div>

          {/* Activity Chart */}
          <div className="kpi-card p-6 flex flex-col gap-6" style={{ animationDelay: '0.4s' }}>
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-white">Активность за 24 часа</h2>
              <div className="flex bg-[#25254A]/30 rounded-md p-1 border border-[#8B5CF6]/20">
                <button className="px-3 py-1 text-xs font-medium rounded text-[#6666AA] hover:text-white transition-colors">12Ч</button>
                <button className="px-3 py-1 text-xs font-medium rounded bg-[#8B5CF6]/20 text-white shadow-[0_0_10px_rgba(139,92,246,0.3)]">24Ч</button>
                <button className="px-3 py-1 text-xs font-medium rounded text-[#6666AA] hover:text-white transition-colors">7Д</button>
              </div>
            </div>

            <div className="relative h-[200px] w-full mt-2 group">
              {/* Tooltip trigger area for effect */}
              <div className="absolute top-[30px] right-[130px] opacity-0 group-hover:opacity-100 transition-opacity z-30 pointer-events-none">
                <div className="bg-[#040410]/90 border border-[#8B5CF6]/40 backdrop-blur-md px-3 py-2 rounded-md shadow-[0_0_20px_rgba(139,92,246,0.2)] flex flex-col gap-1 relative -translate-y-full -translate-x-1/2">
                  <span className="text-[10px] text-[#6666AA] font-mono">18:00</span>
                  <span className="text-xs text-white font-medium">3,240 <span className="text-[#8B5CF6]">отправлено</span></span>
                  <div className="absolute bottom-[-5px] left-1/2 -translate-x-1/2 w-2 h-2 bg-[#040410] border-b border-r border-[#8B5CF6]/40 rotate-45"></div>
                </div>
              </div>

              {/* Grid Lines */}
              <div className="absolute inset-0 flex flex-col justify-between pointer-events-none">
                {[0, 1, 2, 3].map((i) => (
                  <div key={i} className="w-full border-t border-dashed border-[#ffffff]/5"></div>
                ))}
              </div>
              
              {/* Y Axis */}
              <div className="absolute right-0 inset-y-0 flex flex-col justify-between items-end text-[10px] text-[#6666AA] font-mono pb-6 pointer-events-none translate-x-2">
                <span>10k</span>
                <span>5k</span>
                <span>0</span>
              </div>

              {/* X Axis */}
              <div className="absolute bottom-0 inset-x-0 flex justify-between text-[10px] text-[#6666AA] font-mono translate-y-6">
                <span>00:00</span>
                <span>06:00</span>
                <span>12:00</span>
                <span>18:00</span>
                <span>24:00</span>
              </div>

              {/* SVG Chart */}
              <svg viewBox="0 0 640 200" className="w-full h-full overflow-visible" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="fillViolet" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="rgba(139,92,246,0.3)" />
                    <stop offset="100%" stopColor="rgba(139,92,246,0)" />
                  </linearGradient>
                  <linearGradient id="fillCyan" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="rgba(6,182,212,0.2)" />
                    <stop offset="100%" stopColor="rgba(6,182,212,0)" />
                  </linearGradient>
                </defs>

                {/* Sent Series (Violet) */}
                <path 
                  d="M0,180 C100,180 150,80 240,110 C330,140 400,40 480,50 C560,60 600,130 640,150 L640,200 L0,200 Z" 
                  fill="url(#fillViolet)" 
                  className="opacity-0"
                  style={{ animation: 'fadeInUp 1s ease-out 0.5s forwards' }}
                />
                <path 
                  d="M0,180 C100,180 150,80 240,110 C330,140 400,40 480,50 C560,60 600,130 640,150" 
                  fill="none" 
                  stroke="#8B5CF6" 
                  strokeWidth="2" 
                  className="chart-path-violet"
                />

                {/* Delivered Series (Cyan) */}
                <path 
                  d="M0,190 C120,190 160,110 240,130 C320,150 420,60 480,70 C540,80 600,150 640,160 L640,200 L0,200 Z" 
                  fill="url(#fillCyan)" 
                  className="opacity-0"
                  style={{ animation: 'fadeInUp 1s ease-out 0.7s forwards' }}
                />
                <path 
                  d="M0,190 C120,190 160,110 240,130 C320,150 420,60 480,70 C540,80 600,150 640,160" 
                  fill="none" 
                  stroke="#06B6D4" 
                  strokeWidth="2" 
                  strokeDasharray="4 4"
                  className="chart-path-cyan"
                />

                {/* Active Dot */}
                <g transform="translate(480, 50)" className="chart-dot-active" style={{ opacity: 0, animation: 'fadeInUp 0.3s ease forwards 1.5s, dotPulse 1.5s infinite 1.8s' }}>
                  <circle r="6" fill="rgba(139,92,246,0.4)" />
                  <circle r="3" fill="#8B5CF6" />
                </g>
              </svg>
            </div>
          </div>

          {/* Bottom Panels */}
          <div className="grid grid-cols-2 gap-6 pb-8">
            
            {/* Panel 1: SMTP Accounts */}
            <div className="kpi-card p-6 flex flex-col gap-4" style={{ animationDelay: '0.5s' }}>
              <h3 className="font-semibold text-white">SMTP Аккаунты</h3>
              <div className="flex flex-col gap-3">
                {[
                  { email: 'mail@gmail.com', status: 'Активен', statusColor: 'green', val: 4320, limit: 5000 },
                  { email: 'info@yandex.ru', status: 'Активен', statusColor: 'green', val: 3891, limit: 5000 },
                  { email: 'support@mail.ru', status: 'Ошибка', statusColor: 'red', val: 0, limit: 5000 },
                ].map((acc, i) => (
                  <div key={i} className="bg-[#25254A]/20 border border-[#8B5CF6]/10 rounded-lg p-3 flex flex-col gap-2">
                    <div className="flex justify-between items-center">
                      <span className="text-sm font-medium">{acc.email}</span>
                      <div className="flex items-center gap-1.5">
                        {acc.statusColor === 'green' ? (
                          <span className="w-1.5 h-1.5 rounded-full bg-[#10B981] animate-pulse"></span>
                        ) : (
                          <span className="w-1.5 h-1.5 rounded-full bg-[#EF4444]"></span>
                        )}
                        <span className={`text-[10px] font-mono ${acc.statusColor === 'green' ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                          {acc.status}
                        </span>
                      </div>
                    </div>
                    <div className="flex justify-between items-center text-[10px] font-mono text-[#6666AA]">
                      <span>{acc.val.toLocaleString('en-US')} / {acc.limit.toLocaleString('en-US')} сегодня</span>
                    </div>
                    <div className="w-full h-1 bg-[#040410] rounded-full overflow-hidden">
                      <div 
                        className={`h-full ${acc.statusColor === 'green' ? 'bg-[#06B6D4]' : 'bg-[#EF4444]'}`} 
                        style={{ width: `${(acc.val / acc.limit) * 100}%` }}
                      ></div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Panel 2: Recent Campaigns */}
            <div className="kpi-card p-6 flex flex-col gap-4" style={{ animationDelay: '0.6s' }}>
              <h3 className="font-semibold text-white">Последние кампании</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="text-[10px] font-mono text-[#6666AA] uppercase tracking-wider border-b border-[#8B5CF6]/10">
                      <th className="pb-2 font-medium">Кампания</th>
                      <th className="pb-2 font-medium text-right">Получатели</th>
                      <th className="pb-2 font-medium text-right">Откр.</th>
                      <th className="pb-2 font-medium text-right">Статус</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      { name: 'Летняя акция 2026', rec: '12,847', open: '35.3%', status: 'Завершена', sColor: 'green' },
                      { name: 'B2B рассылка', rec: '5,200', open: '41.2%', status: 'Активна', sColor: 'violet' },
                      { name: 'Тест сегмента', rec: '800', open: '28.1%', status: 'Пауза', sColor: 'yellow' },
                    ].map((camp, i) => (
                      <tr key={i} className="border-b border-[#8B5CF6]/5 last:border-0 hover:bg-[#25254A]/10 transition-colors">
                        <td className="py-3 font-medium text-white">{camp.name}</td>
                        <td className="py-3 text-right font-mono text-[#6666AA]">{camp.rec}</td>
                        <td className="py-3 text-right font-mono text-[#6666AA]">{camp.open}</td>
                        <td className="py-3 text-right">
                          <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono border bg-${camp.sColor}-500/10 border-${camp.sColor}-500/20 text-${camp.sColor}-400`}>
                            {camp.sColor === 'violet' && <span className="w-1.5 h-1.5 rounded-full bg-[#8B5CF6] animate-pulse"></span>}
                            {camp.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

          </div>
        </div>
      </main>
    </div>
  );
}
