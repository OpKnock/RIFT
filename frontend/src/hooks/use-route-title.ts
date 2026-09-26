import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

const TITLES: Array<[RegExp, string]> = [
  [/^\/dashboard$/, 'Dashboard · RIFT'],
  [/^\/scenarios\/new$/, 'New Scenario · RIFT'],
  [/^\/scenarios\//, 'Edit Scenario · RIFT'],
  [/^\/scenarios$/, 'Scenarios · RIFT'],
  [/^\/simulation/, 'Simulation · RIFT'],
  [/^\/runs\//, 'Run Detail · RIFT'],
  [/^\/runs$/, 'Operations · RIFT'],
  [/^\/experiments$/, 'Experiments · RIFT'],
  [/^\/evidence$/, 'Evidence · RIFT'],
  [/^\/settings$/, 'Settings · RIFT'],
  [/^\/docs$/, 'Documentation · RIFT'],
  [/^\/faq$/, 'FAQ · RIFT'],
  [/^\/legal\/privacy$/, 'Privacy Policy · RIFT'],
  [/^\/legal\/terms$/, 'Terms of Service · RIFT'],
  [/^\/legal\/cookies$/, 'Cookie Policy · RIFT'],
  [/^\/legal$/, 'Legal · RIFT'],
]

export function useRouteTitle(): void {
  const location = useLocation()

  useEffect(() => {
    const match = TITLES.find(([re]) => re.test(location.pathname))
    document.title = match ? match[1] : 'RIFT - Counterfactual Decision Intelligence'
  }, [location.pathname])
}
