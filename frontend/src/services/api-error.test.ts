import { describe, expect, it } from 'vitest'
import { AxiosError, AxiosHeaders } from 'axios'
import { apiErrorMessage } from './api'

function axiosError(status: number, data: unknown): AxiosError {
  return new AxiosError('Request failed', 'ERR_BAD_REQUEST', undefined, undefined, {
    status,
    statusText: 'error',
    headers: {},
    config: { headers: new AxiosHeaders() },
    data,
  })
}

describe('apiErrorMessage', () => {
  it('prefers server detail with error code', () => {
    expect(apiErrorMessage(axiosError(400, { error: 'invalid_request', detail: 'bad seed' }), 'fallback'))
      .toBe('invalid_request: bad seed')
  })

  it('falls back to error code alone', () => {
    expect(apiErrorMessage(axiosError(404, { error: 'not_found' }), 'fallback')).toBe('not_found')
  })

  it('reports bare HTTP status when no body', () => {
    expect(apiErrorMessage(axiosError(500, null), 'fallback')).toBe('Server responded 500')
  })

  it('returns the fallback for non-axios errors', () => {
    expect(apiErrorMessage(new Error('boom'), 'fallback')).toBe('fallback')
    expect(apiErrorMessage('string-error', 'fallback')).toBe('fallback')
  })
})
