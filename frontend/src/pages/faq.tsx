import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { cn } from '@/utils/cn'

const ITEMS: Array<{ q: string; a: string }> = [
  {
    q: 'What is RIFT?',
    a: 'A research prototype for counterfactual decision intelligence: define a scenario, run candidate futures, stress them with declared perturbations, and verify with an independent Guardian gate. Engine v1.0.0.',
  },
  {
    q: 'Is RIFT clinically validated?',
    a: 'No. All clinical data here is synthetic or from open-access public datasets. Decision support only — never autonomous care, never a medical device.',
  },
  {
    q: 'Does RIFT prove quantum advantage?',
    a: 'No. The default path is exact classical enumeration with a QAOA statevector simulator alongside. The stated policy is "no quantum advantage demonstrated".',
  },
  {
    q: 'Why do some simulations show zero feasible policies?',
    a: 'Under strong perturbations no candidate satisfies every hard constraint. That is a real engine outcome, shown explicitly — adjust the initial state or inspect the Guardian checks.',
  },
  {
    q: 'Where is my data stored?',
    a: 'Run history, event log, and preferences live only in this browser (localStorage). Server-side persistence requires a configured Supabase project; without it the server answers 503 and nothing is stored remotely.',
  },
  {
    q: 'How do I reproduce a result?',
    a: 'Use identical inputs: the engine is deterministic for identical inputs and engine version (only wall-clock timings vary). Copy the exact request with “Copy as curl” on the Simulation page.',
  },
  {
    q: 'What do Guardian PASSED / FAILED mean?',
    a: 'PASSED means the result survived every declared perturbation check. FAILED withholds the result from display by policy — see the incident guidance on the Simulation page.',
  },
  {
    q: 'What license covers RIFT?',
    a: 'AGPL-3.0-or-later. See the Legal section for privacy, terms, and cookie policies.',
  },
]

export function Faq() {
  const [open, setOpen] = useState<number | null>(0)

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-secondary-900 dark:text-white">FAQ</h1>
        <p className="text-secondary-600 dark:text-secondary-400 mt-1">Honest answers — same claims as the documentation, nothing more.</p>
      </div>
      <Card>
        <div className="p-6 divide-y divide-secondary-100 dark:divide-secondary-800">
          {ITEMS.map((item, i) => {
            const expanded = open === i
            return (
              <div key={item.q} className="py-3 first:pt-0 last:pb-0">
                <button
                  onClick={() => setOpen(expanded ? null : i)}
                  aria-expanded={expanded}
                  className="flex w-full items-center justify-between gap-3 text-left"
                >
                  <span className="font-medium text-secondary-900 dark:text-white">{item.q}</span>
                  <ChevronDown className={cn('w-5 h-5 flex-shrink-0 text-secondary-500 transition-transform', expanded && 'rotate-180')} />
                </button>
                {expanded && (
                  <p className="text-sm text-secondary-600 dark:text-secondary-400 mt-2">{item.a}</p>
                )}
              </div>
            )
          })}
        </div>
      </Card>
      <p className="text-xs text-secondary-500">Last updated: 2026-09-26 · v1.0.0</p>
    </div>
  )
}
