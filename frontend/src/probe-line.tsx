import { Line } from '@react-three/drei'

export function Probe() {
  return (
    <Line
      start={[0, 0, 0]}
      end={[1, 1, 1]}
      color="red"
      lineWidth={2}
    />
  )
}
