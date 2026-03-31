import { ApiError } from '@fba/api-sdk'

export function isMembershipAccessError(error: unknown): error is ApiError {
  if (!(error instanceof ApiError) || error.code !== 403) {
    return false
  }

  const message = String(error.msg || error.message || '')
  return message.includes('会员') || message.includes('权益')
}
