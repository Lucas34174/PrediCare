// web/src/api/assistant.ts
import { request } from './request'

export interface ChatSource {
  document: string
  section: string
  page: number
}

export interface ChatResponse {
  response: string
  sources: ChatSource[]
  provenance_cache_semantique: boolean
}

export function sendChatMessage(message: string, conversationId?: string): Promise<ChatResponse> {
  return request<ChatResponse>('/assistant/chat', {
    method: 'POST',
    body: JSON.stringify({ 
      message, 
      conversation_id: conversationId 
    }),
  })
}