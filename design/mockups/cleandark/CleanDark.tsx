import React from 'react';
import './_group.css';

export function CleanDark() {
  return (
    <div className="fmail-cleandark flex h-[820px] w-[1280px] max-w-full overflow-hidden text-sm" style={{ backgroundColor: '#09090F', color: '#EDEDF5' }}>
      
      {/* Sidebar */}
      <aside className="w-[240px] flex-shrink-0 flex flex-col border-r relative z-10" style={{ backgroundColor: '#0F0F1A', borderColor: 'rgba(255,255,255,0.05)' }}>
        <div className="h-16 flex items-center px-5 border-b" style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
          <svg width="32" height="32" viewBox="0 0 52 52" xmlns="http://www.w3.org/2000/svg" className="flex-shrink-0">
            <defs>
              <linearGradient id="logoG" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#7C3AED"/>
                <stop offset="100%" stopColor="#06B6D4"/>
              </linearGradient>
            </defs>
            <rect width="52" height="52" rx="14" fill="url(#logoG)" fillOpacity="0.18"/>
            <rect x="2" y="2" width="48" height="48" rx="12" fill="none" stroke="url(#logoG)" strokeWidth="2"/>
            <rect x="10" y="16" width="32" height="20" rx="3" fill="none" stroke="#8B5CF6" strokeWidth="1.8"/>
            <path d="M10 18 L26 28 L42 18" stroke="#06B6D4" strokeWidth="1.8" fill="none" strokeLinecap="round"/>
          </svg>
          <span className="ml-3 font-semibold tracking-wide" style={{ color: '#EDEDF5' }}>FMail Sender</span>
          <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded-full" style={{ backgroundColor: 'rgba(255,255,255,0.05)', color: '#8080A0' }}>3.1.0</span>
        </div>

        <nav className="flex-1 py-4 px-3 space-y-0.5 overflow-y-auto">
          <NavItem icon={<DashboardIcon />} label="Дашборд" active />
          <NavItem icon={<AccountsIcon />} label="Аккаунты" />
          <NavItem icon={<ComposeIcon />} label="Создать письмо" />
          <NavItem icon={<RecipientsIcon />} label="Получатели" />
          <NavItem icon={<SendingIcon />} label="Рассылка" />
          <NavItem icon={<AnalyticsIcon />} label="Аналитика" />
          <NavItem icon={<InboxIcon />} label="Входящие" badge="3" />
        </nav>

        <div className="p-4 border-t" style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
          <div className="flex items-center space-x-3 px-2">
            <div className="w-2 h-2 rounded-full relative status-dot-pulse" style={{ backgroundColor: '#7C3AED' }}></div>
            <div>
              <div className="text-xs font-bold" style={{ color: '#EDEDF5' }}>PRO</div>
              <div className="text-[11px]" style={{ color: '#8080A0' }}>127 дней</div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 bg-[#09090F] relative overflow-hidden">
        <div className="cd-aurora" />
        {/* Header */}
        <header className="h-16 px-8 flex items-center justify-between border-b" style={{ backgroundColor: '#09090F', borderColor: 'rgba(255,255,255,0.05)' }}>
          <div>
            <h1 className="syne text-[22px]" style={{ color: '#EDEDF5' }}>Дашборд</h1>
            <p className="text-[13px]" style={{ color: '#8080A0' }}>Статистика за последние 24 часа</p>
          </div>

          <div className="flex items-center space-x-4">
            <div className="px-3 py-1.5 rounded-md text-[13px] border" style={{ backgroundColor: '#0F0F1A', borderColor: 'rgba(255,255,255,0.05)', color: '#EDEDF5' }}>
              15 июн. 2026
            </div>
            <button className="relative w-8 h-8 rounded-md flex items-center justify-center border transition-colors hover:bg-white/5" style={{ backgroundColor: '#0F0F1A', borderColor: 'rgba(255,255,255,0.05)', color: '#8080A0' }}>
              <BellIcon />
              <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full" style={{ backgroundColor: '#7C3AED' }}></span>
            </button>
          </div>
        </header>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-8 space-y-6">
          
          {/* KPI Cards */}
          <div className="grid grid-cols-4 gap-4">
            <KpiCard 
              title="Отправлено" 
              value="12,847" 
              trend="+14%" 
              trendUp={true} 
              icon={<SendIcon className="w-4 h-4" style={{ color: '#7C3AED' }} />} 
              iconBg="rgba(139,92,246,0.08)"
              delay="0s"
            />
            <KpiCard 
              title="Доставлено" 
              value="92.9%" 
              trend="+1.1%" 
              trendUp={true} 
              icon={<CheckCircleIcon className="w-4 h-4" style={{ color: '#10B981' }} />} 
              iconBg="rgba(16,185,129,0.08)"
              delay="0.1s"
            />
            <KpiCard 
              title="Открытий" 
              value="35.3%" 
              trend="+3.7%" 
              trendUp={true} 
              icon={<EyeIcon className="w-4 h-4" style={{ color: '#06B6D4' }} />} 
              iconBg="rgba(6,182,212,0.08)"
              delay="0.2s"
            />
            <KpiCard 
              title="Ошибок" 
              value="904" 
              trend="−2.4%" 
              trendUp={false} 
              icon={<XCircleIcon className="w-4 h-4" style={{ color: '#EF4444' }} />} 
              iconBg="rgba(239,68,68,0.08)"
              delay="0.3s"
              goodTrend={true} // Going down is good for errors
            />
          </div>

          {/* Chart Section */}
          <div className="rounded-xl border relative chart-appear overflow-hidden" style={{ backgroundColor: '#141421', borderColor: 'rgba(255,255,255,0.08)' }}>
            <div className="card-top-gradient"></div>
            
            <div className="p-6 pb-2 flex items-center justify-between">
              <div className="flex items-center space-x-6">
                <h2 className="syne text-[16px]" style={{ color: '#EDEDF5' }}>Активность рассылок</h2>
                <div className="flex items-center space-x-4 text-[12px]">
                  <div className="flex items-center"><div className="w-2 h-2 rounded-full mr-2" style={{ backgroundColor: '#8B5CF6' }}></div><span style={{ color: '#8080A0' }}>Отправлено</span></div>
                  <div className="flex items-center"><div className="w-2 h-2 rounded-full mr-2" style={{ backgroundColor: '#06B6D4' }}></div><span style={{ color: '#8080A0' }}>Доставлено</span></div>
                </div>
              </div>
              
              <div className="flex rounded-md p-1 border text-[12px] font-medium" style={{ backgroundColor: '#0F0F1A', borderColor: 'rgba(255,255,255,0.05)' }}>
                <button className="px-3 py-1 rounded shadow-sm" style={{ backgroundColor: 'rgba(255,255,255,0.05)', color: '#EDEDF5' }}>24Ч</button>
                <button className="px-3 py-1 rounded hover:bg-white/5 transition-colors" style={{ color: '#8080A0' }}>7Д</button>
                <button className="px-3 py-1 rounded hover:bg-white/5 transition-colors" style={{ color: '#8080A0' }}>30Д</button>
              </div>
            </div>

            <div className="h-[280px] w-full relative p-4 pl-0">
              
              {/* Tooltip */}
              <div className="absolute top-[30px] left-[390px] z-20 pointer-events-none">
                <div className="rounded-lg border px-3 py-2 shadow-xl backdrop-blur-md whitespace-nowrap" style={{ backgroundColor: 'rgba(20, 20, 33, 0.85)', borderColor: 'rgba(255,255,255,0.1)' }}>
                  <div className="text-[12px] font-medium mb-1" style={{ color: '#EDEDF5' }}>12:00</div>
                  <div className="text-[12px] space-y-0.5">
                    <div className="flex items-center justify-between gap-4"><span style={{ color: '#8B5CF6' }}>Отправлено</span><span className="fmail-table-nums" style={{ color: '#EDEDF5' }}>1,580</span></div>
                    <div className="flex items-center justify-between gap-4"><span style={{ color: '#06B6D4' }}>Доставлено</span><span className="fmail-table-nums" style={{ color: '#EDEDF5' }}>1,470</span></div>
                  </div>
                </div>
                {/* Dashed line to X axis */}
                <div className="absolute left-[36px] top-[100%] bottom-[-140px] w-px border-l border-dashed" style={{ borderColor: 'rgba(255,255,255,0.15)' }}></div>
                {/* Dot on line */}
                <div className="absolute left-[33px] top-[10px] w-2 h-2 rounded-full border-2" style={{ backgroundColor: '#09090F', borderColor: '#8B5CF6' }}></div>
              </div>

              <svg viewBox="0 0 900 220" preserveAspectRatio="none" className="w-full h-full">
                <defs>
                  <linearGradient id="violetGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#8B5CF6" stopOpacity="0.3" />
                    <stop offset="100%" stopColor="#8B5CF6" stopOpacity="0" />
                  </linearGradient>
                  <linearGradient id="cyanGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#06B6D4" stopOpacity="0.15" />
                    <stop offset="100%" stopColor="#06B6D4" stopOpacity="0" />
                  </linearGradient>
                </defs>

                {/* Grid Lines */}
                <line x1="60" y1="20" x2="900" y2="20" stroke="rgba(255,255,255,0.04)" strokeWidth="1" strokeDasharray="4 4" />
                <line x1="60" y1="100" x2="900" y2="100" stroke="rgba(255,255,255,0.04)" strokeWidth="1" strokeDasharray="4 4" />
                <line x1="60" y1="180" x2="900" y2="180" stroke="rgba(255,255,255,0.04)" strokeWidth="1" strokeDasharray="4 4" />

                {/* Y Axis Labels */}
                <g fill="#454565" className="text-[11px] fmail-table-nums" textAnchor="end">
                  <text x="50" y="24">1,600</text>
                  <text x="50" y="104">800</text>
                  <text x="50" y="184">0</text>
                </g>

                {/* X Axis Labels */}
                <g fill="#8080A0" className="text-[11px] fmail-table-nums" textAnchor="middle">
                  <text x="60" y="210">00:00</text>
                  <text x="200" y="210">04:00</text>
                  <text x="340" y="210">08:00</text>
                  <text x="480" y="210">12:00</text>
                  <text x="620" y="210">16:00</text>
                  <text x="760" y="210">20:00</text>
                  <text x="900" y="210">24:00</text>
                </g>

                {/* Delivered (Cyan) - Back series */}
                <path 
                  d="M 60 170 C 130 175, 160 160, 200 120 C 270 40, 310 100, 340 50 C 400 -20, 440 20, 480 30 C 530 40, 580 80, 620 60 C 670 40, 710 110, 760 130 C 820 160, 860 140, 900 150 L 900 180 L 60 180 Z" 
                  fill="url(#cyanGradient)" 
                  className="chart-area"
                />
                <path 
                  d="M 60 170 C 130 175, 160 160, 200 120 C 270 40, 310 100, 340 50 C 400 -20, 440 20, 480 30 C 530 40, 580 80, 620 60 C 670 40, 710 110, 760 130 C 820 160, 860 140, 900 150" 
                  fill="none" 
                  stroke="#06B6D4" 
                  strokeWidth="1.5" 
                  strokeDasharray="6 3"
                />

                {/* Sent (Violet) - Front series */}
                <path 
                  d="M 60 165 C 130 170, 160 150, 200 110 C 270 30, 310 90, 340 40 C 400 -30, 440 10, 480 20 C 530 30, 580 70, 620 50 C 670 30, 710 100, 760 120 C 820 150, 860 130, 900 140 L 900 180 L 60 180 Z" 
                  fill="url(#violetGradient)" 
                  className="chart-area"
                />
                <path 
                  d="M 60 165 C 130 170, 160 150, 200 110 C 270 30, 310 90, 340 40 C 400 -30, 440 10, 480 20 C 530 30, 580 70, 620 50 C 670 30, 710 100, 760 120 C 820 150, 860 130, 900 140" 
                  fill="none" 
                  stroke="#8B5CF6" 
                  strokeWidth="2" 
                  className="chart-line"
                />
                
                {/* Last data point pulse dot */}
                <circle cx="900" cy="140" r="4" fill="#09090F" stroke="#8B5CF6" strokeWidth="2" className="last-dot-pulse" style={{ opacity: 0, animation: 'fadeInUp 0.1s ease 1.8s forwards, pulseLastDot 2s infinite ease-in-out' }} />
              </svg>
            </div>
          </div>

          {/* Bottom Row */}
          <div className="grid grid-cols-2 gap-6 pb-6">
            
            {/* SMTP Accounts */}
            <div className="rounded-xl border relative overflow-hidden" style={{ backgroundColor: '#141421', borderColor: 'rgba(255,255,255,0.08)' }}>
              <div className="p-5 border-b flex justify-between items-center" style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
                <h3 className="font-semibold text-[14px]" style={{ color: '#EDEDF5' }}>SMTP Аккаунты</h3>
              </div>
              <table className="w-full text-[13px]">
                <thead style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                  <tr>
                    <th className="font-medium text-left px-5 py-3" style={{ color: '#8080A0' }}>Аккаунт</th>
                    <th className="font-medium text-left px-5 py-3" style={{ color: '#8080A0' }}>Статус</th>
                    <th className="font-medium text-right px-5 py-3" style={{ color: '#8080A0' }}>Сегодня</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="hover:bg-white/[0.02] transition-colors border-b" style={{ borderColor: 'rgba(255,255,255,0.02)' }}>
                    <td className="px-5 py-3.5 font-medium" style={{ color: '#EDEDF5' }}>mail@gmail.com</td>
                    <td className="px-5 py-3.5">
                      <div className="flex items-center space-x-2">
                        <div className="w-1.5 h-1.5 rounded-full relative status-dot-pulse" style={{ backgroundColor: '#10B981' }}></div>
                        <span style={{ color: '#EDEDF5' }}>Активен</span>
                      </div>
                    </td>
                    <td className="px-5 py-3.5 text-right fmail-table-nums" style={{ color: '#8080A0' }}>4,320</td>
                  </tr>
                  <tr className="hover:bg-white/[0.02] transition-colors border-b" style={{ borderColor: 'rgba(255,255,255,0.02)' }}>
                    <td className="px-5 py-3.5 font-medium" style={{ color: '#EDEDF5' }}>info@yandex.ru</td>
                    <td className="px-5 py-3.5">
                      <div className="flex items-center space-x-2">
                        <div className="w-1.5 h-1.5 rounded-full relative status-dot-pulse" style={{ backgroundColor: '#10B981' }}></div>
                        <span style={{ color: '#EDEDF5' }}>Активен</span>
                      </div>
                    </td>
                    <td className="px-5 py-3.5 text-right fmail-table-nums" style={{ color: '#8080A0' }}>3,891</td>
                  </tr>
                  <tr className="hover:bg-white/[0.02] transition-colors">
                    <td className="px-5 py-3.5 font-medium" style={{ color: '#EDEDF5' }}>support@mail.ru</td>
                    <td className="px-5 py-3.5">
                      <div className="flex items-center space-x-2">
                        <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: '#EF4444' }}></div>
                        <span style={{ color: '#EDEDF5' }}>Ошибка</span>
                      </div>
                    </td>
                    <td className="px-5 py-3.5 text-right fmail-table-nums" style={{ color: '#454565' }}>—</td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Recent Campaigns */}
            <div className="rounded-xl border relative overflow-hidden" style={{ backgroundColor: '#141421', borderColor: 'rgba(255,255,255,0.08)' }}>
              <div className="p-5 border-b flex justify-between items-center" style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
                <h3 className="font-semibold text-[14px]" style={{ color: '#EDEDF5' }}>Последние кампании</h3>
              </div>
              <table className="w-full text-[13px]">
                <thead style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                  <tr>
                    <th className="font-medium text-left px-5 py-3" style={{ color: '#8080A0' }}>Кампания</th>
                    <th className="font-medium text-right px-5 py-3" style={{ color: '#8080A0' }}>Получатели</th>
                    <th className="font-medium text-right px-5 py-3" style={{ color: '#8080A0' }}>Откр.</th>
                    <th className="font-medium text-right px-5 py-3" style={{ color: '#8080A0' }}>Статус</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="hover:bg-white/[0.02] transition-colors border-b" style={{ borderColor: 'rgba(255,255,255,0.02)' }}>
                    <td className="px-5 py-3.5 font-medium" style={{ color: '#EDEDF5' }}>Летняя акция 2026</td>
                    <td className="px-5 py-3.5 text-right fmail-table-nums" style={{ color: '#8080A0' }}>12,847</td>
                    <td className="px-5 py-3.5 text-right fmail-table-nums" style={{ color: '#8080A0' }}>35.3%</td>
                    <td className="px-5 py-3.5 text-right">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium" style={{ backgroundColor: 'rgba(16,185,129,0.1)', color: '#10B981' }}>
                        Завершена
                      </span>
                    </td>
                  </tr>
                  <tr className="hover:bg-white/[0.02] transition-colors border-b" style={{ borderColor: 'rgba(255,255,255,0.02)' }}>
                    <td className="px-5 py-3.5 font-medium" style={{ color: '#EDEDF5' }}>B2B рассылка</td>
                    <td className="px-5 py-3.5 text-right fmail-table-nums" style={{ color: '#8080A0' }}>5,200</td>
                    <td className="px-5 py-3.5 text-right fmail-table-nums" style={{ color: '#8080A0' }}>41.2%</td>
                    <td className="px-5 py-3.5 text-right">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium border" style={{ backgroundColor: 'rgba(139,92,246,0.1)', color: '#8B5CF6', borderColor: 'rgba(139,92,246,0.2)' }}>
                        <div className="w-1.5 h-1.5 rounded-full mr-1.5 relative status-dot-pulse" style={{ backgroundColor: '#8B5CF6' }}></div>
                        Активна
                      </span>
                    </td>
                  </tr>
                  <tr className="hover:bg-white/[0.02] transition-colors">
                    <td className="px-5 py-3.5 font-medium" style={{ color: '#EDEDF5' }}>Тест сегмента</td>
                    <td className="px-5 py-3.5 text-right fmail-table-nums" style={{ color: '#8080A0' }}>800</td>
                    <td className="px-5 py-3.5 text-right fmail-table-nums" style={{ color: '#8080A0' }}>28.1%</td>
                    <td className="px-5 py-3.5 text-right">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium" style={{ backgroundColor: 'rgba(255,255,255,0.05)', color: '#8080A0' }}>
                        Пауза
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

          </div>
        </div>
      </main>
    </div>
  );
}

// Subcomponents

function NavItem({ icon, label, active, badge }: { icon: React.ReactNode, label: string, active?: boolean, badge?: string }) {
  return (
    <div 
      className="flex items-center px-3 py-2 rounded-md cursor-pointer transition-colors relative group"
      style={{ 
        backgroundColor: active ? 'rgba(139, 92, 246, 0.07)' : 'transparent',
      }}
    >
      {active && (
        <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[2px] h-5 rounded-r" style={{ backgroundColor: '#7C3AED' }}></div>
      )}
      {!active && (
        <div className="absolute inset-0 rounded-md bg-white opacity-0 group-hover:opacity-5 transition-opacity pointer-events-none"></div>
      )}
      <div className="w-5 h-5 flex items-center justify-center mr-3" style={{ color: active ? '#EDEDF5' : '#8080A0' }}>
        {icon}
      </div>
      <span className="syne text-[13px]" style={{ color: active ? '#EDEDF5' : '#8080A0' }}>{label}</span>
      {badge && (
        <span className="ml-auto px-1.5 py-0.5 rounded text-[10px] font-semibold fmail-table-nums" style={{ backgroundColor: '#7C3AED', color: '#ffffff' }}>
          {badge}
        </span>
      )}
    </div>
  );
}

function KpiCard({ title, value, trend, trendUp, icon, iconBg, delay, goodTrend }: { 
  title: string, value: string, trend: string, trendUp: boolean, icon: React.ReactNode, iconBg: string, delay: string, goodTrend?: boolean 
}) {
  const isPositive = goodTrend !== undefined ? goodTrend : trendUp;
  
  return (
    <div 
      className="p-5 rounded-xl border relative overflow-hidden flex flex-col justify-between opacity-0 animate-fade-in-up"
      style={{ 
        backgroundColor: '#141421', 
        borderColor: 'rgba(255,255,255,0.08)',
        animationDelay: delay
      }}
    >
      <div className="card-top-gradient opacity-40"></div>
      
      <div className="flex justify-between items-start mb-4">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg" style={{ backgroundColor: iconBg }}>
          {icon}
        </div>
      </div>
      
      <div>
        <div className="text-[28px] font-semibold tracking-tight fmail-table-nums animate-count-up" style={{ color: '#EDEDF5' }}>
          {value}
        </div>
        <div className="text-[13px] mt-1 mb-4" style={{ color: '#8080A0' }}>{title}</div>
        
        <div className="flex items-center space-x-2">
          <span 
            className="px-1.5 py-0.5 rounded-full text-[11px] font-semibold fmail-table-nums flex items-center" 
            style={{ 
              backgroundColor: isPositive ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)', 
              color: isPositive ? '#10B981' : '#EF4444' 
            }}
          >
            {trendUp ? '↑' : '↓'} {trend.replace(/[↑↓]/g, '')}
          </span>
          <span className="text-[12px]" style={{ color: '#454565' }}>vs вчера</span>
        </div>
      </div>
    </div>
  );
}

// Icons 

const DashboardIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="7" height="7" rx="1.5" />
    <rect x="14" y="3" width="7" height="7" rx="1.5" />
    <rect x="14" y="14" width="7" height="7" rx="1.5" />
    <rect x="3" y="14" width="7" height="7" rx="1.5" />
  </svg>
);

const AccountsIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
  </svg>
);

const ComposeIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 20h9" />
    <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
  </svg>
);

const RecipientsIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="8" y1="6" x2="21" y2="6" />
    <line x1="8" y1="12" x2="21" y2="12" />
    <line x1="8" y1="18" x2="21" y2="18" />
    <line x1="3" y1="6" x2="3.01" y2="6" />
    <line x1="3" y1="12" x2="3.01" y2="12" />
    <line x1="3" y1="18" x2="3.01" y2="18" />
  </svg>
);

const SendingIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="22" y1="2" x2="11" y2="13" />
    <polygon points="22 2 15 22 11 13 2 9 22 2" />
  </svg>
);

const AnalyticsIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="20" x2="18" y2="10" />
    <line x1="12" y1="20" x2="12" y2="4" />
    <line x1="6" y1="20" x2="6" y2="14" />
  </svg>
);

const InboxIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="22 12 16 12 14 15 10 15 8 12 2 12" />
    <path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
  </svg>
);

const BellIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
    <path d="M13.73 21a2 2 0 0 1-3.46 0" />
  </svg>
);

const SendIcon = ({ className, style }: { className?: string, style?: React.CSSProperties }) => (
  <svg className={className} style={style} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="22" y1="2" x2="11" y2="13" />
    <polygon points="22 2 15 22 11 13 2 9 22 2" />
  </svg>
);

const CheckCircleIcon = ({ className, style }: { className?: string, style?: React.CSSProperties }) => (
  <svg className={className} style={style} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
    <polyline points="22 4 12 14.01 9 11.01" />
  </svg>
);

const EyeIcon = ({ className, style }: { className?: string, style?: React.CSSProperties }) => (
  <svg className={className} style={style} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
    <circle cx="12" cy="12" r="3" />
  </svg>
);

const XCircleIcon = ({ className, style }: { className?: string, style?: React.CSSProperties }) => (
  <svg className={className} style={style} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <line x1="15" y1="9" x2="9" y2="15" />
    <line x1="9" y1="9" x2="15" y2="15" />
  </svg>
);
