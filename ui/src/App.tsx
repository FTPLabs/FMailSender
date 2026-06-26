import { Routes, Route, Navigate } from 'react-router-dom'
  import Layout from './components/Layout'
  import Dashboard   from './pages/Dashboard'
  import Accounts    from './pages/Accounts'
  import Recipients  from './pages/Recipients'
  import Compose     from './pages/Compose'
  import Sending     from './pages/Sending'
  import Inbox       from './pages/Inbox'

  export default function App() {
    return (
      <Layout>
        <Routes>
          <Route path="/"           element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard"  element={<Dashboard />} />
          <Route path="/accounts"   element={<Accounts />} />
          <Route path="/recipients" element={<Recipients />} />
          <Route path="/compose"    element={<Compose />} />
          <Route path="/sending"    element={<Sending />} />
          <Route path="/inbox"      element={<Inbox />} />
          <Route path="*"           element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Layout>
    )
  }
  