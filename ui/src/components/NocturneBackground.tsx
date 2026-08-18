import { useEffect, useState } from 'react'

export default function NocturneBackground() {
  const [enabled, setEnabled] = useState(() => localStorage.getItem('fmail-animated-bg') !== '0')
  useEffect(() => {
    const onChange = (event: Event) => setEnabled(Boolean((event as CustomEvent<boolean>).detail))
    window.addEventListener('fmail:background', onChange)
    return () => window.removeEventListener('fmail:background', onChange)
  }, [])
  if (!enabled) return null
  return <div className="nocturne-ambient" aria-hidden="true"><span className="ambient-orb orb-a"/><span className="ambient-orb orb-b"/><span className="ambient-grid"/><span className="ambient-sigil"/></div>
}
