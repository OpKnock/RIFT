import { Suspense, lazy } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from '@/components/layout/layout'
import { LoadingScreen } from '@/components/ui/loading-screen'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { CookieConsentBanner } from '@/components/ui/cookie-consent'

// Lazy load pages for code splitting
const Dashboard = lazy(() => import('@/pages/dashboard').then(m => ({ default: m.Dashboard })))
const Scenarios = lazy(() => import('@/pages/scenarios').then(m => ({ default: m.Scenarios })))
const ScenarioBuilder = lazy(() => import('@/pages/scenario-builder').then(m => ({ default: m.ScenarioBuilder })))
const Simulation = lazy(() => import('@/pages/simulation').then(m => ({ default: m.Simulation })))
const Runs = lazy(() => import('@/pages/runs').then(m => ({ default: m.Runs })))
const RunDetail = lazy(() => import('@/pages/run-detail').then(m => ({ default: m.RunDetail })))
const Experiments = lazy(() => import('@/pages/experiments').then(m => ({ default: m.Experiments })))
const Evidence = lazy(() => import('@/pages/evidence').then(m => ({ default: m.Evidence })))
const Settings = lazy(() => import('@/pages/settings').then(m => ({ default: m.Settings })))
const Documentation = lazy(() => import('@/pages/documentation').then(m => ({ default: m.Documentation })))
const Legal = lazy(() => import('@/pages/legal').then(m => ({ default: m.Legal })))
const PrivacyPolicy = lazy(() => import('@/pages/privacy-policy').then(m => ({ default: m.PrivacyPolicy })))
const TermsOfService = lazy(() => import('@/pages/terms-of-service').then(m => ({ default: m.TermsOfService })))
const CookiePolicy = lazy(() => import('@/pages/cookie-policy').then(m => ({ default: m.CookiePolicy })))
const NotFound = lazy(() => import('@/pages/not-found').then(m => ({ default: m.NotFound })))

function App() {
  return (
    <ErrorBoundary>
      <Suspense fallback={<LoadingScreen />}>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="scenarios" element={<Scenarios />} />
            <Route path="scenarios/new" element={<ScenarioBuilder />} />
            <Route path="scenarios/:id" element={<ScenarioBuilder />} />
            <Route path="simulation" element={<Simulation />} />
            <Route path="simulation/:id" element={<Simulation />} />
            <Route path="runs" element={<Runs />} />
            <Route path="runs/:id" element={<RunDetail />} />
            <Route path="experiments" element={<Experiments />} />
            <Route path="evidence" element={<Evidence />} />
            <Route path="settings" element={<Settings />} />
            <Route path="docs" element={<Documentation />} />
            <Route path="legal" element={<Legal />} />
            <Route path="legal/privacy" element={<PrivacyPolicy />} />
            <Route path="legal/terms" element={<TermsOfService />} />
            <Route path="legal/cookies" element={<CookiePolicy />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </Suspense>
      <CookieConsentBanner />
    </ErrorBoundary>
  )
}

export default App