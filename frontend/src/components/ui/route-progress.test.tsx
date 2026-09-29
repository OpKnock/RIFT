// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { RouteProgress } from './route-progress'

describe('RouteProgress', () => {
  it('renders a slim progressbar without fullscreen takeover', () => {
    const { container } = render(<RouteProgress />)
    const bar = screen.getByRole('progressbar', { name: 'Loading page' })
    expect(bar).toBeTruthy()
    expect(bar.className).toContain('h-1')
    // Must not render the branded fullscreen screen.
    expect(container.textContent).not.toContain('Loading RIFT')
  })
})
