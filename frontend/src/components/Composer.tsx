import React, { useRef, useState } from 'react';

interface ComposerProps {
  onSendMessage: (content: string, webEnabled: boolean) => void;
  onUploadFiles: (files: FileList) => void;
  isSending: boolean;
}

export const Composer: React.FC<ComposerProps> = ({
  onSendMessage,
  onUploadFiles,
  isSending,
}) => {
  const [input, setInput] = useState('');
  const [webEnabled, setWebEnabled] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim() || isSending) return;
    onSendMessage(input.trim(), webEnabled);
    setInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div style={{
      borderTop: '1px solid var(--border-subtle)',
      backgroundColor: 'var(--bg-paper)',
      padding: '14px 20px',
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
      flexShrink: 0,
    }}>
      <form onSubmit={handleSubmit} style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
        maxWidth: '800px',
        width: '100%',
        margin: '0 auto',
      }}>
        {/* Input box */}
        <div style={{
          position: 'relative',
          border: '1px solid var(--border-strong)',
          borderRadius: '6px',
          backgroundColor: '#FFFFFF',
          padding: '8px 12px',
          boxShadow: '0 1px 2px rgba(0,0,0,0.02)',
        }}>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question grounded in your tables and documents..."
            rows={2}
            disabled={isSending}
            style={{
              width: '100%',
              border: 'none',
              outline: 'none',
              resize: 'none',
              fontSize: '13.5px',
              fontFamily: 'inherit',
              lineHeight: 1.4,
              color: 'var(--text-primary)',
              backgroundColor: 'transparent',
            }}
          />
        </div>

        {/* Toolbar: Attach, Web Search Toggle, Send button */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            {/* Hidden file input */}
            <input
              type="file"
              ref={fileInputRef}
              multiple
              accept=".csv,.pdf,.docx,.txt,.md"
              style={{ display: 'none' }}
              onChange={(e) => {
                if (e.target.files && e.target.files.length > 0) {
                  onUploadFiles(e.target.files);
                  e.target.value = '';
                }
              }}
            />

            {/* Attach button */}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              title="Attach CSV tables or PDF/DOCX/TXT/MD documents"
              style={{
                background: 'none',
                border: '1px solid var(--border-subtle)',
                borderRadius: '4px',
                padding: '5px 10px',
                fontSize: '12px',
                cursor: 'pointer',
                color: 'var(--text-muted)',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              <span>📎</span>
              <span>Upload Files</span>
            </button>

            {/* Web Search Toggle */}
            <label style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '12px',
              cursor: 'pointer',
              userSelect: 'none',
              color: 'var(--text-muted)',
            }}>
              <input
                type="checkbox"
                checked={webEnabled}
                onChange={(e) => setWebEnabled(e.target.checked)}
                style={{ cursor: 'pointer' }}
              />
              <span>Web Search</span>
              <span style={{
                fontSize: '10px',
                padding: '1px 4px',
                borderRadius: '3px',
                backgroundColor: webEnabled ? 'var(--accent-volt)' : 'var(--bg-surface)',
                fontWeight: 600,
                color: 'var(--text-primary)',
              }}>
                {webEnabled ? 'ON' : 'OFF'}
              </span>
            </label>
          </div>

          {/* Send button */}
          <button
            type="submit"
            disabled={!input.trim() || isSending}
            style={{
              padding: '6px 16px',
              backgroundColor: !input.trim() || isSending ? 'var(--bg-surface)' : 'var(--accent-volt)',
              border: '1px solid var(--border-strong)',
              borderRadius: '4px',
              fontSize: '13px',
              fontWeight: 600,
              cursor: !input.trim() || isSending ? 'not-allowed' : 'pointer',
              color: !input.trim() || isSending ? 'var(--text-dim)' : 'var(--text-primary)',
            }}
          >
            {isSending ? 'Answering...' : 'Send'}
          </button>
        </div>
      </form>
    </div>
  );
};
