import React from 'react';
import { ChatMessage, Citation } from '../types';

interface MessageThreadProps {
  messages: ChatMessage[];
  streamingStatus: string | null;
  onSelectCitation: (citation: Citation) => void;
}

export const MessageThread: React.FC<MessageThreadProps> = ({
  messages,
  streamingStatus,
  onSelectCitation,
}) => {
  return (
    <div style={{
      flex: 1,
      overflowY: 'auto',
      padding: '24px 20px',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
    }}>
      <div style={{ width: '100%', maxWidth: '800px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {messages.length === 0 ? (
          <div style={{
            textAlign: 'center',
            padding: '60px 20px',
            color: 'var(--text-muted)',
          }}>
            <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
              Multi-Source Grounded Assistant
            </h2>
            <p style={{ fontSize: '13px', maxWidth: '460px', margin: '0 auto', lineHeight: 1.6 }}>
              Ask questions grounded strictly in your uploaded tables and dated documents. Every claim is cited with verified queries and verbatim text quotes.
            </p>
          </div>
        ) : (
          messages.map((msg) => {
            const isUser = msg.role === 'user';
            return (
              <div
                key={msg.message_id}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: isUser ? 'flex-end' : 'flex-start',
                  width: '100%',
                }}
              >
                {/* Role and metadata header */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  marginBottom: '4px',
                  fontSize: '11px',
                  color: 'var(--text-muted)',
                }}>
                  <span style={{ fontWeight: 600, color: isUser ? 'var(--text-primary)' : 'var(--text-primary)' }}>
                    {isUser ? 'You' : 'Assistant'}
                  </span>
                  <span>•</span>
                  <span>{msg.created_at || 'Just now'}</span>
                  {msg.web_enabled !== undefined && (
                    <span style={{
                      fontSize: '10px',
                      padding: '1px 5px',
                      borderRadius: '3px',
                      backgroundColor: msg.web_enabled ? 'var(--accent-volt-subtle)' : 'var(--bg-surface)',
                      border: '1px solid var(--border-subtle)',
                    }}>
                      {msg.web_enabled ? 'Web ON' : 'Web OFF'}
                    </span>
                  )}
                </div>

                {/* Message Bubble Card */}
                <div style={{
                  maxWidth: '100%',
                  backgroundColor: isUser ? 'var(--bg-surface)' : 'var(--bg-paper)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: isUser ? '8px 8px 2px 8px' : '8px 8px 8px 2px',
                  padding: '14px 18px',
                  boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
                }}>
                  {/* Quiet Interpreted As line */}
                  {msg.interpreted_as && (
                    <div style={{
                      fontSize: '11px',
                      fontStyle: 'italic',
                      color: 'var(--text-muted)',
                      marginBottom: '8px',
                      paddingBottom: '6px',
                      borderBottom: '1px dashed var(--border-subtle)',
                    }}>
                      Interpreted as: {msg.interpreted_as}
                    </div>
                  )}

                  {/* Message prose with preserved line breaks and tabular numerals */}
                  <div
                    className="tabular-nums"
                    style={{
                      fontSize: '13.5px',
                      lineHeight: 1.6,
                      color: 'var(--text-primary)',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}
                  >
                    {msg.content}
                  </div>

                  {/* Inline citation badges */}
                  {msg.citations && msg.citations.length > 0 && (
                    <div style={{
                      marginTop: '12px',
                      paddingTop: '8px',
                      borderTop: '1px solid var(--border-subtle)',
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: '6px',
                    }}>
                      <span style={{ fontSize: '11px', color: 'var(--text-dim)', alignSelf: 'center', marginRight: '4px' }}>
                        Sources:
                      </span>
                      {msg.citations.map((c, cIdx) => (
                        <button
                          key={cIdx}
                          onClick={() => onSelectCitation(c)}
                          style={{
                            padding: '3px 8px',
                            backgroundColor: 'var(--bg-surface)',
                            border: '1px solid var(--border-strong)',
                            borderRadius: '4px',
                            fontSize: '11px',
                            fontWeight: 500,
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                          }}
                        >
                          <span style={{
                            width: '6px',
                            height: '6px',
                            borderRadius: '50%',
                            backgroundColor: c.type === 'table' ? '#3B82F6' : 'var(--color-success)',
                          }} />
                          <span>
                            {c.type === 'table' ? `Table [${cIdx + 1}]` : `Doc [${cIdx + 1}]`}
                          </span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}

        {/* Live Streaming Status Bar */}
        {streamingStatus && (
          <div style={{
            alignSelf: 'flex-start',
            padding: '10px 14px',
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '6px',
            fontSize: '12px',
            color: 'var(--text-muted)',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}>
            <span style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: 'var(--accent-volt-dark)',
              display: 'inline-block',
            }} />
            <span>{streamingStatus}</span>
          </div>
        )}
      </div>
    </div>
  );
};
