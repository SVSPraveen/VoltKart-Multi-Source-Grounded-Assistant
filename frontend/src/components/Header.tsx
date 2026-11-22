import React from 'react';

interface HeaderProps {
  chatTitle: string;
  chatId: string;
  onNewChat?: () => void;
  onExportPdf: () => void;
  onToggleDrawer: () => void;
  isDrawerOpen: boolean;
  onOpenSummary: () => void;
  onToggleMobileSidebar?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  chatTitle,
  chatId,
  onNewChat,
  onExportPdf,
  onToggleDrawer,
  isDrawerOpen,
  onOpenSummary,
  onToggleMobileSidebar,
}) => {
  return (
    <header style={{
      height: '52px',
      borderBottom: '1px solid var(--border-subtle)',
      backgroundColor: 'var(--bg-paper)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 20px',
      userSelect: 'none',
      flexShrink: 0,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        {onToggleMobileSidebar && (
          <button
            className="header-menu-btn"
            onClick={onToggleMobileSidebar}
            title="Toggle Sidebar"
            aria-label="Toggle Navigation Sidebar"
            style={{
              background: 'none',
              border: '1px solid var(--border-subtle)',
              borderRadius: '4px',
              padding: '4px 8px',
              fontSize: '14px',
              cursor: 'pointer',
            }}
          >
            ☰
          </button>
        )}
        <h1 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
          {chatTitle || 'Conversation'}
        </h1>
        <span className="header-chat-id" data-testid="header-chat-id" style={{ fontSize: '11px', color: 'var(--text-dim)', padding: '2px 6px', background: 'var(--bg-surface)', borderRadius: '3px' }}>
          {chatId}
        </span>
      </div>


      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        {onNewChat && (
          <button
            onClick={onNewChat}
            title="Start a new conversation thread"
            aria-label="New Chat"
            style={{
              padding: '6px 11px',
              backgroundColor: 'var(--accent-volt)',
              border: '1px solid var(--border-strong)',
              borderRadius: '4px',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
              color: 'var(--text-primary)',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <span>+ New Chat</span>
          </button>
        )}

        <button
          onClick={onOpenSummary}
          title="Inspect Table Schemas and Document Families"
          aria-label="Open Ingestion Summary Card"
          style={{
            padding: '6px 10px',
            backgroundColor: 'transparent',
            border: '1px solid var(--border-subtle)',
            borderRadius: '4px',
            fontSize: '12px',
            cursor: 'pointer',
            color: 'var(--text-muted)',
          }}
        >
          Ingestion Card
        </button>

        <button
          onClick={onExportPdf}
          title="Export publication-grade PDF report (C7)"
          aria-label="Export Chat as PDF"
          style={{
            padding: '6px 12px',
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-strong)',
            borderRadius: '4px',
            fontSize: '12px',
            fontWeight: 600,
            cursor: 'pointer',
            color: 'var(--text-primary)',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <span>Export PDF</span>
          <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>₹</span>
        </button>

        <button
          onClick={onToggleDrawer}
          title="Toggle Evidence Drawer"
          aria-label="Toggle Evidence Drawer"
          style={{
            padding: '6px 10px',
            backgroundColor: isDrawerOpen ? 'var(--accent-volt-subtle)' : 'transparent',
            border: '1px solid var(--border-subtle)',
            borderRadius: '4px',
            fontSize: '12px',
            cursor: 'pointer',
            color: 'var(--text-primary)',
          }}
        >
          {isDrawerOpen ? 'Hide Evidence' : 'Show Evidence'}
        </button>
      </div>
    </header>
  );
};
