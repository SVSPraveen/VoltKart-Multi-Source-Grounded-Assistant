import React from 'react';
import { ChatSession, FileRecord } from '../types';

interface SidebarProps {
  chats: ChatSession[];
  activeChatId: string;
  onSelectChat: (chatId: string) => void;
  onNewChat: () => void;
  onDeleteChat: (chatId: string) => void;
  files: FileRecord[];
  onOpenSummary: () => void;
  isOpen?: boolean;
  onCloseMobile?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  chats,
  activeChatId,
  onSelectChat,
  onNewChat,
  onDeleteChat,
  files,
  onOpenSummary,
  isOpen = false,
  onCloseMobile,
}) => {
  // Group files by version family
  const groupedFiles: Record<string, FileRecord[]> = {};
  files.forEach((f) => {
    const fam = f.version_family || 'Other Documents';
    if (!groupedFiles[fam]) groupedFiles[fam] = [];
    groupedFiles[fam].push(f);
  });

  return (
    <>
      {isOpen && onCloseMobile && (
        <div
          onClick={onCloseMobile}
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0,0,0,0.3)',
            zIndex: 99,
          }}
        />
      )}
      <aside
        className={`sidebar-container ${isOpen ? 'open' : ''}`}
        style={{
          width: '260px',
          minWidth: '260px',
          height: '100vh',
          backgroundColor: 'var(--bg-surface)',
          borderRight: '1px solid var(--border-subtle)',
          display: 'flex',
          flexDirection: 'column',
          userSelect: 'none',
          overflow: 'hidden',
        }}
      >

      {/* Workspace Brand / Header */}
      <div style={{
        padding: '16px',
        borderBottom: '1px solid var(--border-subtle)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: '13px', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
            Multi-Source
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Grounded Assistant</div>
        </div>
        <button
          onClick={onNewChat}
          title="Start New Conversation"
          aria-label="Create new conversation"
          style={{
            padding: '6px 10px',
            backgroundColor: 'var(--accent-volt)',
            border: '1px solid var(--border-strong)',
            borderRadius: '4px',
            fontSize: '12px',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          + New
        </button>
      </div>

      {/* Conversations Section */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 8px' }}>
        <div style={{
          fontSize: '11px',
          fontWeight: 600,
          color: 'var(--text-muted)',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          padding: '4px 8px',
          marginBottom: '4px',
        }}>
          Conversations ({chats.length})
        </div>

        {chats.length === 0 ? (
          <div style={{ fontSize: '12px', color: 'var(--text-dim)', padding: '8px' }}>
            No conversations yet.
          </div>
        ) : (
          chats.map((c) => {
            const isActive = c.chat_id === activeChatId;
            return (
              <div
                key={c.chat_id}
                data-chat-id={c.chat_id}
                onClick={() => onSelectChat(c.chat_id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '8px 10px',
                  borderRadius: '4px',
                  marginBottom: '2px',
                  cursor: 'pointer',
                  backgroundColor: isActive ? 'var(--bg-paper)' : 'transparent',
                  border: isActive ? '1px solid var(--border-subtle)' : '1px solid transparent',
                  fontWeight: isActive ? 600 : 400,
                }}
              >
                <div style={{
                  fontSize: '12.5px',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  flex: 1,
                  marginRight: '8px',
                }}>
                  {c.title || c.chat_id}
                </div>
                {chats.length > 1 && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteChat(c.chat_id);
                    }}
                    title="Delete Chat"
                    aria-label={`Delete conversation ${c.title || c.chat_id}`}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--text-dim)',
                      cursor: 'pointer',
                      fontSize: '12px',
                      padding: '2px 4px',
                    }}
                  >
                    ✕
                  </button>
                )}
              </div>
            );
          })
        )}

        {/* Versioned Document & Table Library */}
        <div style={{
          fontSize: '11px',
          fontWeight: 600,
          color: 'var(--text-muted)',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          padding: '16px 8px 4px 8px',
        }}>
          Files Library ({files.length})
        </div>

        {Object.keys(groupedFiles).length === 0 ? (
          <div style={{ fontSize: '12px', color: 'var(--text-dim)', padding: '8px' }}>
            No files ingested yet.
          </div>
        ) : (
          Object.entries(groupedFiles).map(([family, fList]) => (
            <div key={family} style={{ marginBottom: '8px', padding: '0 4px' }}>
              <div style={{
                fontSize: '12px',
                fontWeight: 600,
                color: 'var(--text-primary)',
                padding: '4px 6px',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{family}</span>
                <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{fList.length} v</span>
              </div>
              {fList.map((f) => (
                <div
                  key={f.sha256}
                  style={{
                    fontSize: '11px',
                    color: 'var(--text-muted)',
                    padding: '2px 6px 2px 14px',
                    display: 'flex',
                    justifyContent: 'space-between',
                  }}
                >
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '140px' }}>
                    {f.file_name}
                  </span>
                  <span style={{ fontSize: '10px', color: 'var(--text-dim)' }}>{f.doc_date || 'undated'}</span>
                </div>
              ))}
            </div>
          ))
        )}
      </div>

      {/* Ingestion status trigger button */}
      <div style={{ padding: '12px', borderTop: '1px solid var(--border-subtle)' }}>
        <button
          onClick={onOpenSummary}
          aria-label="View Ingestion Schema Card"
          style={{
            width: '100%',
            padding: '8px',
            backgroundColor: 'var(--bg-paper)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '4px',
            fontSize: '11.5px',
            fontWeight: 500,
            cursor: 'pointer',
            textAlign: 'center',
          }}
        >
          View Ingestion Schema
        </button>
      </div>
    </aside>
    </>
  );
};
