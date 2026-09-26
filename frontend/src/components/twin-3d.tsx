import { useMemo, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'

export interface TreeNode {
  id: string
  parent_id: string | null
  depth: number
  policy: Record<string, number>
  score: number
  valid: boolean
  label: string
}

interface PlacedNode extends TreeNode {
  position: [number, number, number]
}

function layoutTree(nodes: TreeNode[]): { placed: PlacedNode[]; edges: Array<[number, number]> } {
  const byDepth = new Map<number, TreeNode[]>()
  for (const n of nodes) {
    const list = byDepth.get(n.depth) || []
    list.push(n)
    byDepth.set(n.depth, list)
  }
  const indexById = new Map<string, number>()
  const placed: PlacedNode[] = []
  let cursor = 0
  for (const depth of [...byDepth.keys()].sort((a, b) => a - b)) {
    const group = byDepth.get(depth) || []
    group.forEach((n, i) => {
      const angle = group.length > 1 ? (i / (group.length - 1) - 0.5) * Math.PI : 0
      placed.push({
        ...n,
        position: [depth * 4 - 4, Math.sin(angle) * group.length * 0.35, (i - (group.length - 1) / 2) * 0.9],
      })
      indexById.set(n.id, cursor)
      cursor += 1
    })
  }
  const edges: Array<[number, number]> = []
  for (const n of placed) {
    if (n.parent_id && indexById.has(n.parent_id)) {
      edges.push([indexById.get(n.parent_id) as number, indexById.get(n.id) as number])
    }
  }
  return { placed, edges }
}

export function FutureTree3D({ nodes }: { nodes: TreeNode[] }) {
  const [selected, setSelected] = useState<PlacedNode | null>(null)
  const { placed, edges } = useMemo(() => layoutTree(nodes), [nodes])
  const positions = useMemo(() => {
    const arr = new Float32Array(edges.length * 6)
    edges.forEach(([a, b], i) => {
      const pa = placed[a].position
      const pb = placed[b].position
      arr.set(pa, i * 6)
      arr.set(pb, i * 6 + 3)
    })
    return arr
  }, [placed, edges])

  if (nodes.length === 0) {
    return <p className="text-sm text-secondary-500">No future-tree nodes in this response.</p>
  }

  const scores = placed.map((p) => p.score)
  const lo = Math.min(...scores)
  const hi = Math.max(...scores)
  const span = hi - lo || 1

  return (
    <div className="space-y-3">
      <div className="h-80 rounded-lg overflow-hidden border border-secondary-200 dark:border-secondary-700 bg-secondary-950">
        <Canvas camera={{ position: [6, 4, 10], fov: 50 }} dpr={[1, 2]}>
          <ambientLight intensity={0.7} />
          <directionalLight position={[5, 8, 5]} intensity={1.2} />
          <lineSegments>
            <bufferGeometry>
              <bufferAttribute attach="attributes-position" args={[positions, 3]} />
            </bufferGeometry>
            <lineBasicMaterial color="#64748b" transparent opacity={0.6} />
          </lineSegments>
          {placed.map((n) => {
            const r = 0.16 + 0.22 * (1 - (n.score - lo) / span)
            return (
              <mesh key={n.id} position={n.position} onClick={() => setSelected(n)}>
                <sphereGeometry args={[r, 20, 20]} />
                <meshStandardMaterial color={n.valid ? '#16a34a' : '#dc2626'} roughness={0.4} />
              </mesh>
            )
          })}
          <OrbitControls enableDamping={false} makeDefault />
        </Canvas>
      </div>
      <div className="flex flex-wrap gap-4 text-xs text-secondary-500">
        <span><span className="inline-block w-2 h-2 rounded-full bg-success-600 mr-1" />valid future</span>
        <span><span className="inline-block w-2 h-2 rounded-full bg-error-600 mr-1" />invalid future</span>
        <span>size grows as score improves · drag to orbit, scroll to zoom, click a node</span>
      </div>
      {selected && (
        <div className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50 text-sm space-y-1">
          <p className="font-mono font-medium">{selected.id} · {selected.label} · depth {selected.depth}</p>
          <p className="font-mono">policy {JSON.stringify(selected.policy)}</p>
          <p className="font-mono">score {selected.score.toFixed(2)} · valid {selected.valid ? 'yes' : 'no'}</p>
        </div>
      )}
    </div>
  )
}
