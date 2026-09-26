import { useMemo, useState, useEffect, useRef, useCallback } from 'react'
import { Canvas, useFrame, extend } from '@react-three/fiber'
import { OrbitControls, Line } from '@react-three/drei'
import * as THREE from 'three'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

extend({ Line })

export interface TreeNode {
  id: string
  parent_id: string | null
  depth: number
  policy: Record<string, number>
  score: number
  valid: boolean
  label: string
  // Phase 7 additions
  state?: Record<string, number>
  intervention?: Record<string, number>
  perturbation?: Record<string, number>
  uncertainty?: number
  guardian_action?: 'ALLOW' | 'WARN' | 'WITHHOLD'
  computation_time_ms?: number
}

interface PlacedNode extends TreeNode {
  position: [number, number, number]
  color: string
  size: number
}

interface SimulationFrame {
  day: number
  nodes: TreeNode[]
  timestamp: number
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
      // Color by guardian action / validity
      let color = n.valid ? '#16a34a' : '#dc2626'
      if (n.guardian_action === 'WARN') color = '#eab308'
      if (n.guardian_action === 'WITHHOLD') color = '#ef4444'
      // Size by score (better score = larger)
      const size = 0.12 + 0.25 * (n.score / 100)
      placed.push({
        ...n,
        position: [depth * 4.5 - 4, Math.sin(angle) * group.length * 0.4, (i - (group.length - 1) / 2) * 1.1],
        color,
        size,
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

// Animated node component
function NodeMesh({
  node,
  selected,
  hovered,
  onClick,
  onHover,
}: {
  node: PlacedNode
  selected: boolean
  hovered: boolean
  onClick: () => void
  onHover: (on: boolean) => void
}) {
  const meshRef = useRef<THREE.Mesh>(null!)
  const [pulse, setPulse] = useState(0)

  useFrame(() => {
    if (meshRef.current) {
      meshRef.current.rotation.y += 0.005
      if (pulse > 0) {
        setPulse(p => Math.max(0, p - 0.02))
      }
    }
  })

  useEffect(() => {
    if (selected) setPulse(1)
  }, [selected])

  return (
    <mesh
      ref={meshRef}
      key={node.id}
      position={node.position}
      onClick={onClick}
      onPointerOver={() => onHover(true)}
      onPointerOut={() => onHover(false)}
      scale={selected ? 1.3 : hovered ? 1.15 : 1}
    >
      <sphereGeometry args={[node.size, 24, 24]} />
      <meshStandardMaterial
        color={node.color}
        roughness={0.3}
        metalness={0.1}
        emissive={selected ? node.color : hovered ? '#333' : '#000'}
        emissiveIntensity={pulse * 0.5}
      />
      {selected && (
        <mesh position={[0, 0, 0]} scale={1.5}>
          <sphereGeometry args={[node.size * 0.9, 16, 16]} />
          <meshBasicMaterial color={node.color} transparent opacity={0.15} wireframe />
        </mesh>
      )}
    </mesh>
  )
}

// Edge lines
function Edges({ edges, placed }: { edges: Array<[number, number]>; placed: PlacedNode[] }) {
  const positions = useMemo(() => {
    const arr = new Float32Array(edges.length * 6)
    edges.forEach(([a, b], i) => {
      const pa = placed[a].position
      const pb = placed[b].position
      arr.set(pa, i * 6)
      arr.set(pb, i * 6 + 3)
    })
    return arr
  }, [edges, placed])

  return (
    <lineSegments>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <lineBasicMaterial color="#64748b" transparent opacity={0.5} />
    </lineSegments>
  )
}

// Perturbation visualization
function PerturbationArrows({ nodes, placed }: { nodes: PlacedNode[]; placed: PlacedNode[] }) {
  const arrows = useMemo(() => {
    const result: Array<{ from: [number, number, number]; to: [number, number, number]; color: string }> = []
    for (const node of nodes) {
      if (node.perturbation && node.parent_id) {
        const parent = placed.find(p => p.id === node.parent_id)
        if (parent) {
          result.push({
            from: parent.position,
            to: node.position,
            color: '#eab308',
          })
        }
      }
    }
    return result
  }, [nodes, placed])

  return (
    <group>
      {arrows.map((arrow, i) => (
        <Line
          key={i}
          start={arrow.from}
          end={arrow.to}
          color={arrow.color}
          dashed
          dashSize={0.2}
          gapSize={0.1}
          lineWidth={2}
        />
      ))}
    </group>
  )
}

// Uncertainty halos
function UncertaintyHalos({ nodes }: { nodes: PlacedNode[] }) {
  return (
    <group>
      {nodes
        .filter(n => (n.uncertainty ?? 0) > 0.1)
        .map(n => (
          <mesh key={n.id} position={n.position}>
            <sphereGeometry args={[n.size + 0.08 + (n.uncertainty || 0) * 0.3, 16, 16]} />
            <meshBasicMaterial
              color="#eab308"
              transparent
              opacity={0.1 + (n.uncertainty || 0) * 0.2}
              side={THREE.DoubleSide}
            />
          </mesh>
        ))}
    </group>
  )
}

interface FutureTree3DProps {
  nodes: TreeNode[]
  frames?: SimulationFrame[]
  onNodeSelect?: (node: TreeNode | null) => void
  className?: string
}

export function FutureTree3D({
  nodes,
  frames,
  onNodeSelect,
  className = '',
}: FutureTree3DProps) {
  const [selected, setSelected] = useState<PlacedNode | null>(null)
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const [playing, setPlaying] = useState(false)
  const [currentFrame, setCurrentFrame] = useState(0)
  const [speed, setSpeed] = useState(1)
  const frameRef = useRef(frames)
  frameRef.current = frames

  const { placed, edges } = useMemo(() => layoutTree(nodes), [nodes])

  const handleClick = useCallback((node: PlacedNode) => {
    setSelected(node)
    onNodeSelect?.(node)
  }, [onNodeSelect])

  const handleHover = useCallback((id: string, on: boolean) => {
    if (on) setHoveredId(id)
    else if (hoveredId === id) setHoveredId(null)
  }, [hoveredId])

  // Playback controls
  useEffect(() => {
    if (!playing || !frames || frames.length === 0) return
    const interval = setInterval(() => {
      setCurrentFrame(f => (f + 1) % frames.length)
    }, 1000 / speed)
    return () => clearInterval(interval)
  }, [playing, frames, speed])

  const currentFrameData = frames?.[currentFrame]

  if (nodes.length === 0) {
    return (
      <div className={`space-y-3 ${className}`}>
        <p className="text-sm text-secondary-500">No future-tree nodes in this response.</p>
      </div>
    )
  }

  

  return (
    <div className={`space-y-3 ${className}`}>
      {/* Playback Controls */}
      {frames && frames.length > 1 && (
        <div className="flex flex-wrap items-center gap-3 p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50 text-sm">
          <Button
            variant={playing ? 'secondary' : 'outline'}
            size="sm"
            onClick={() => setPlaying(!playing)}
          >
            {playing ? 'Pause' : 'Play'}
          </Button>
          <Button variant="outline" size="sm" onClick={() => setCurrentFrame(0)}>Reset</Button>
          <Button variant="outline" size="sm" onClick={() => setCurrentFrame(f => Math.max(0, f - 1))} disabled={currentFrame === 0}>Step Back</Button>
          <Button variant="outline" size="sm" onClick={() => setCurrentFrame(f => Math.min((frames?.length || 1) - 1, f + 1))} disabled={currentFrame === (frames?.length || 1) - 1}>Step Forward</Button>
          <div className="flex items-center gap-2">
            <span className="text-secondary-500">Speed:</span>
            <select
              value={speed}
              onChange={e => setSpeed(Number(e.target.value))}
              className="text-xs px-2 py-1 rounded border border-secondary-300 dark:border-secondary-600 bg-white dark:bg-secondary-800"
            >
              <option value={0.5}>0.5x</option>
              <option value={1}>1x</option>
              <option value={2}>2x</option>
              <option value={4}>4x</option>
            </select>
          </div>
          <div className="flex-1 h-1.5 bg-secondary-200 dark:bg-secondary-700 rounded overflow-hidden">
            <div
              className="h-full bg-primary-600 transition-all"
              style={{ width: `${((currentFrame + 1) / (frames.length || 1)) * 100}%` }}
            />
          </div>
          <span className="text-xs text-secondary-500 font-mono">
            Frame {currentFrame + 1} / {frames.length} · Day {currentFrameData?.day ?? '—'}
          </span>
        </div>
      )}

      {/* 3D Canvas */}
      <div className="h-96 rounded-lg overflow-hidden border border-secondary-200 dark:border-secondary-700 bg-secondary-950 relative">
        <Canvas camera={{ position: [8, 6, 14], fov: 45 }} dpr={[1, 2]} onCreated={({ gl }) => { gl.setClearColor(0x0f172a, 1) }}>
          <fog color="#0f172a" near={10} far={50} />
          <ambientLight intensity={0.6} />
          <directionalLight position={[10, 15, 10]} intensity={1.5} castShadow />
          <directionalLight position={[-5, 10, -5]} intensity={0.5} />

          {/* Grid floor */}
          <gridHelper args={[40, 40, '#334155', '#1e293b']} position={[0, -2, 0]} />

          <Edges edges={edges} placed={placed} />
          <PerturbationArrows nodes={placed} placed={placed} />
          <UncertaintyHalos nodes={placed} />

          {placed.map(n => (
            <NodeMesh
              key={n.id}
              node={n}
              selected={selected?.id === n.id}
              hovered={hoveredId === n.id}
              onClick={() => handleClick(n)}
              onHover={on => handleHover(n.id, on)}
            />
          ))}

          <OrbitControls
            enableDamping
            enablePan
            enableZoom
            minDistance={5}
            maxDistance={50}
            makeDefault
          />
        </Canvas>

        {/* Legend overlay */}
        <div className="absolute bottom-3 left-3 right-3 flex flex-wrap gap-4 text-xs text-secondary-300 bg-secondary-950/90 backdrop-blur p-2 rounded border border-secondary-700">
          <span><span className="inline-block w-2 h-2 rounded-full bg-success-600 mr-1" />Feasible</span>
          <span><span className="inline-block w-2 h-2 rounded-full bg-error-600 mr-1" />Infeasible</span>
          <span><span className="inline-block w-2 h-2 rounded-full bg-warning-600 mr-1" />Guardian WARN</span>
          <span><span className="inline-block w-2 h-2 rounded-full bg-error-600 mr-1" />Guardian WITHHOLD</span>
          <span>Size ∝ score · Yellow halo = uncertainty · Yellow dashed lines = perturbations</span>
        </div>
      </div>

      {/* Node Detail Panel */}
      {selected && (
        <div className="p-4 rounded-lg bg-secondary-50 dark:bg-secondary-800/50 text-sm space-y-2 border border-secondary-200 dark:border-secondary-700">
          <div className="flex items-center justify-between">
            <p className="font-mono font-medium">{selected.id} · {selected.label} · depth {selected.depth}</p>
            <Badge variant={selected.valid ? 'success' : 'error'}>{selected.valid ? 'Valid' : 'Invalid'}</Badge>
          </div>
          <p className="font-mono text-xs">Policy: {JSON.stringify(selected.policy)}</p>
          <p className="font-mono text-xs">Score: {selected.score.toFixed(2)} · Uncertainty: {(selected.uncertainty ?? 0).toFixed(3)} · Guardian: {selected.guardian_action ?? '—'}</p>
          {selected.state && (
            <p className="font-mono text-xs">State: {JSON.stringify(selected.state)}</p>
          )}
          {selected.intervention && (
            <p className="font-mono text-xs">Intervention: {JSON.stringify(selected.intervention)}</p>
          )}
          {selected.perturbation && (
            <p className="font-mono text-xs text-warning-600 dark:text-warning-400">Perturbation: {JSON.stringify(selected.perturbation)}</p>
          )}
          {selected.computation_time_ms && (
            <p className="font-mono text-xs text-secondary-500">Computation: {selected.computation_time_ms} ms</p>
          )}
        </div>
      )}

      {/* Frame Comparison */}
      {frames && frames.length > 1 && (
        <div className="space-y-2">
          <h4 className="font-medium text-secondary-900 dark:text-white">Frame Comparison</h4>
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-2 max-h-40 overflow-x-auto">
            {frames.map((frame, i) => (
              <button
                key={i}
                className={`p-2 rounded text-xs font-mono text-center transition-colors ${
                  i === currentFrame
                    ? 'bg-primary-600 text-white'
                    : 'bg-secondary-100 dark:bg-secondary-800 hover:bg-secondary-200 dark:hover:bg-secondary-700'
                }`}
                onClick={() => { setPlaying(false); setCurrentFrame(i); }}
              >
                Day {frame.day} ({frame.nodes.length} nodes)
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}