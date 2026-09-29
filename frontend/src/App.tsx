import { Suspense, lazy, useEffect, useState } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from '@/components/layout/layout'
import { LoadingScreen } from '@/components/ui/loading-screen'
import { RouteProgress } from '@/components/ui/route-progress'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { CookieConsentBanner } from '@/components/ui/cookie-consent'
import { preloadAllRoutes, onIdle } from '@/utils/route-preload'

// Lazy load pages for code splitting. Named loaders (not inline) so the
// idle preloader below can warm every chunk after first paint.
const loadDashboard = () => import('@/pages/dashboard').then(m => ({ default: m.Dashboard }))
const loadScenarios = () => import('@/pages/scenarios').then(m => ({ default: m.Scenarios }))
const loadScenarioBuilder = () => import('@/pages/scenario-builder').then(m => ({ default: m.ScenarioBuilder }))
const loadSimulation = () => import('@/pages/simulation').then(m => ({ default: m.Simulation }))
const loadRuns = () => import('@/pages/runs').then(m => ({ default: m.Runs }))
const loadRunDetail = () => import('@/pages/run-detail').then(m => ({ default: m.RunDetail }))
const loadExperiments = () => import('@/pages/experiments').then(m => ({ default: m.Experiments }))
const loadEvidence = () => import('@/pages/evidence').then(m => ({ default: m.Evidence }))
const loadIncidents = () => import('@/pages/incidents').then(m => ({ default: m.Incidents }))
const loadExplainability = () => import('@/pages/explainability').then(m => ({ default: m.Explainability }))
const loadSettings = () => import('@/pages/settings').then(m => ({ default: m.Settings }))
const loadDocumentation = () => import('@/pages/documentation').then(m => ({ default: m.Documentation }))
const loadFaq = () => import('@/pages/faq').then(m => ({ default: m.Faq }))
const loadLegal = () => import('@/pages/legal').then(m => ({ default: m.Legal }))
const loadPrivacyPolicy = () => import('@/pages/privacy-policy').then(m => ({ default: m.PrivacyPolicy }))
const loadTermsOfService = () => import('@/pages/terms-of-service').then(m => ({ default: m.TermsOfService }))
const loadCookiePolicy = () => import('@/pages/cookie-policy').then(m => ({ default: m.CookiePolicy }))
const loadNotFound = () => import('@/pages/not-found').then(m => ({ default: m.NotFound }))

const Dashboard = lazy(loadDashboard)
const Scenarios = lazy(loadScenarios)
const ScenarioBuilder = lazy(loadScenarioBuilder)
const Simulation = lazy(loadSimulation)
const Runs = lazy(loadRuns)
const RunDetail = lazy(loadRunDetail)
const Experiments = lazy(loadExperiments)
const Evidence = lazy(loadEvidence)
const Incidents = lazy(loadIncidents)
const Explainability = lazy(loadExplainability)
const Settings = lazy(loadSettings)
const Documentation = lazy(loadDocumentation)
const Faq = lazy(loadFaq)
const Legal = lazy(loadLegal)
const PrivacyPolicy = lazy(loadPrivacyPolicy)
const TermsOfService = lazy(loadTermsOfService)
const CookiePolicy = lazy(loadCookiePolicy)
const NotFound = lazy(loadNotFound)

const routeLoaders = [
  loadDashboard, loadScenarios, loadScenarioBuilder, loadSimulation,
  loadRuns, loadRunDetail, loadExperiments, loadEvidence, loadIncidents,
  loadExplainability, loadSettings, loadDocumentation, loadFaq, loadLegal,
  loadPrivacyPolicy, loadTermsOfService, loadCookiePolicy, loadNotFound,
]

function App() {
  // Branded takeover only until boot. After idle-preload warms every
  // chunk, navigations resolve instantly; any residual suspense shows a
  // slim top progress bar instead of the fullscreen screen.
  const [booted, setBooted] = useState(false)
  useEffect(() => {
    return onIdle(() => {
      void preloadAllRoutes(routeLoaders).then(() => setBooted(true))
    })
  }, [])

  return (
    <ErrorBoundary>
      <Suspense fallback={booted ? <RouteProgress /> : <LoadingScreen />}>
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
            <Route path="incidents" element={<Incidents />} />
            <Route path="explainability" element={<Explainability />} />
            <Route path="settings" element={<Settings />} />
            <Route path="docs" element={<Documentation />} />
            <Route path="faq" element={<Faq />} />
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
