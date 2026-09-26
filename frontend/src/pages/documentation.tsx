import { Link } from 'react-router-dom'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

const DOCS = [
  { title: 'Architecture', path: 'docs/architecture.md', desc: 'Module boundaries, principles, endpoint plan.' },
  { title: 'API contract', path: 'docs/api.md', desc: 'Full REST API reference.' },
  { title: 'Patient twin', path: 'docs/patient-twin.md', desc: 'Twin pipeline, Guardian registry, hygiene rules.' },
  { title: 'Evidence sheet', path: 'docs/evidence-sheet.md', desc: 'Frozen synthetic evidence and limitations.' },
  { title: 'Security', path: 'docs/security.md', desc: 'Auth modes and residual risks.' },
  { title: 'Deployment', path: 'docs/deployment.md', desc: 'Local, Docker, and production edge checklist.' },
  { title: 'Release checklist', path: 'docs/release-checklist.md', desc: 'Evidence-gated release requirements.' },
]

export function Documentation() {
  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-secondary-900 dark:text-white">Documentation</h1>
        <p className="text-secondary-600 dark:text-secondary-400 mt-1">Index of the real documents shipped in this repository. No duplicated or rewritten claims here.</p>
      </div>
      <div>
        <Link to="/faq"><Button variant="outline">Frequently asked questions</Button></Link>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {DOCS.map((d) => (
          <Card key={d.path}>
            <div className="p-6">
              <h2 className="font-semibold text-secondary-900 dark:text-white">{d.title}</h2>
              <p className="text-sm text-secondary-500 mt-1">{d.desc}</p>
              <p className="font-mono text-xs text-secondary-500 mt-3">{d.path}</p>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}
