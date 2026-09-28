// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AuthRequired } from './auth-required'

describe('AuthRequired', () => {
  it('explains the 401 and links to token settings', () => {
    render(
      <MemoryRouter>
        <AuthRequired resource="incidents and decisions" />
      </MemoryRouter>,
    )
    expect(screen.getByText('Authentication required')).toBeTruthy()
    expect(screen.getByText(/incidents and decisions/)).toBeTruthy()
    const link = screen.getByRole('link', { name: /api token settings/i })
    expect(link.getAttribute('href')).toBe('/settings?tab=api')
  })
})
