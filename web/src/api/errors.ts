import type { ValidationIssue } from './types'

export class ApiError extends Error {
  readonly status: number
  readonly validationIssues: ValidationIssue[]

  constructor(message: string, status: number, validationIssues: ValidationIssue[] = []) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.validationIssues = validationIssues
  }
}
