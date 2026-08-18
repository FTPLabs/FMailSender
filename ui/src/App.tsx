import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { StatusProvider } from './contexts/StatusContext'
import { I18nProvider } from './i18n'
import StartupOverlay from './components/StartupOverlay'
import AppTour from './components/AppTour'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Accounts from './pages/Accounts'
import Proxies from './pages/Proxies'
import Recipients from './pages/Recipients'
import Compose from './pages/Compose'
import Sending from './pages/Sending'
import Inbox from './pages/Inbox'
import Guide from './pages/Guide'
import Settings from './pages/Settings'
import NocturneBackground from './components/NocturneBackground'

function DesktopPreferenceBridge() {
  useEffect(() => {
    const bridge = (window as Window & { fmailApp?: { setCloseWarningEnabled?: (enabled: boolean) => Promise<boolean> } }).fmailApp
    void bridge?.setCloseWarningEnabled?.(localStorage.getItem('fmail-close-warning') !== '0')
  }, [])
  return null
}

export default function App() {
  return <I18nProvider><StatusProvider>
    <NocturneBackground />
    <DesktopPreferenceBridge />
    <StartupOverlay />
    <AppTour />
    <Layout><Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/accounts" element={<Accounts />} />
      <Route path="/proxies" element={<Proxies />} />
      <Route path="/recipients" element={<Recipients />} />
      <Route path="/compose" element={<Compose />} />
      <Route path="/sending" element={<Sending />} />
      <Route path="/inbox" element={<Inbox />} />
      <Route path="/guide" element={<Guide />} />
      <Route path="/settings" element={<Settings />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes></Layout>
  </StatusProvider></I18nProvider>
}
