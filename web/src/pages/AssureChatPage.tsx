// web/src/pages/AssureChatPage.tsx
import { useState, useRef, useEffect } from 'react'
import { Send, Bot, User, BookOpen } from 'lucide-react'
import { sendChatMessage, type ChatSource } from '@/api/assistant'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: ChatSource[]
  isError?: boolean
}

export function AssureChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    { id: 'welcome', role: 'assistant', content: "Bonjour ! Je suis l'assistant PrediCare. Je peux vous aider à comprendre vos garanties, vos remboursements ou répondre à vos questions sur votre contrat." }
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // Remplace le scrollIntoView par un scrollTop classique
    const container = bottomRef.current?.parentElement
    if (container) {
      container.scrollTop = container.scrollHeight
    }
  }, [messages])

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const userMsg: Message = { id: crypto.randomUUID(), role: 'user', content: input.trim() }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setIsLoading(true)

    try {
      const response = await sendChatMessage(userMsg.content, 'conv-assure')
      const botMsg: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: response.response,
        sources: response.sources,
      }
      setMessages((prev) => [...prev, botMsg])
    } catch (error) {
      const errorMsg: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: "Désolé, je rencontre une difficulté technique. Veuillez réessayer plus tard.",
        isError: true,
      }
      setMessages((prev) => [...prev, errorMsg])
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="claim-page" style={{ height: 'calc(100vh - 160px)', display: 'flex', flexDirection: 'column' }}>
      <header className="page-heading" style={{ marginBottom: '1rem' }}>
        <div>
          <h1>Assistant PrediCare</h1>
          <p className="page-subtitle">Posez vos questions sur vos garanties et remboursements.</p>
        </div>
      </header>

      <section className="claim-section" style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden' }}>
        {/* Zone de messages */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {messages.map((msg) => (
            <div key={msg.id} style={{
              display: 'flex',
              gap: '12px',
              flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
              alignItems: 'flex-start'
            }}>
              <div style={{
                width: '36px', height: '36px', flexShrink: 0, borderRadius: '50%',
                display: 'grid', placeItems: 'center',
                background: msg.role === 'user' ? 'var(--green-light)' : 'var(--surface-soft)',
                color: msg.role === 'user' ? 'var(--green)' : 'var(--ink-muted)'
              }}>
                {msg.role === 'user' ? <User size={18} /> : <Bot size={18} />}
              </div>
              
              <div style={{ maxWidth: '80%' }}>
                <div style={{
                  padding: '12px 16px',
                  borderRadius: '12px',
                  borderTopRightRadius: msg.role === 'user' ? '2px' : '12px',
                  borderTopLeftRadius: msg.role === 'assistant' ? '2px' : '12px',
                  background: msg.isError ? 'var(--danger-soft)' : msg.role === 'user' ? 'var(--green)' : 'var(--surface-soft)',
                  color: msg.isError ? 'var(--danger-soft-foreground)' : msg.role === 'user' ? 'white' : 'var(--ink)',
                  fontSize: '13px',
                  lineHeight: 1.6,
                }}>
                  {msg.content}
                </div>
                
                {/* Sources RAG */}
                {msg.sources && msg.sources.length > 0 && (
                  <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <span style={{ fontSize: '10px', fontWeight: 600, color: 'var(--ink-muted)' }}>Sources :</span>
                    {msg.sources.map((src, i) => (
                      <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--ink-muted)' }}>
                        <BookOpen size={12} /> {src.document} — {src.section} (p.{src.page})
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          
          {isLoading && (
            <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
              <div style={{ width: '36px', height: '36px', borderRadius: '50%', background: 'var(--surface-soft)', display: 'grid', placeItems: 'center', color: 'var(--ink-muted)' }}>
                <Bot size={18} />
              </div>
              <div className="claim-hint" style={{ fontStyle: 'italic' }}>L'assistant réfléchit…</div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Zone de saisie */}
        <form onSubmit={handleSend} style={{ padding: '1rem', borderTop: '1px solid var(--line)', background: 'var(--surface)' }}>
          <div className="input-wrap" style={{ borderRadius: '24px', padding: '4px 4px 4px 16px' }}>
            <input
              type="text"
              placeholder="Posez votre question…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={isLoading}
              style={{ fontSize: '13px' }}
            />
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              style={{
                width: '36px', height: '36px', borderRadius: '50%',
                background: input.trim() ? 'var(--green)' : 'var(--line)',
                color: 'white', border: 0, display: 'grid', placeItems: 'center',
                cursor: input.trim() ? 'pointer' : 'not-allowed',
                transition: 'background 0.2s'
              }}
            >
              <Send size={16} />
            </button>
          </div>
        </form>
      </section>
    </div>
  )
}