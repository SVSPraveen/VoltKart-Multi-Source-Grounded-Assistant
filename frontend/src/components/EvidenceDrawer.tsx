import React, { useState } from 'react';
import { Citation, DocumentCitation, TableCitation } from '../types';

interface EvidenceDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  activeCitation: Citation | null;
  allCitations: Citation[];
}

export const EvidenceDrawer: React.FC<EvidenceDrawerProps> = ({
  isOpen,
  onClose,
  activeCitation,
  allCitations,
}) => {
  const [copied, setCopied] = useState(false);
  const [selectedIdx, setSelectedIdx] = useState<number>(0);

  if (!isOpen) return null;

  // Selected citation or first available citation
  const currentCitation: Citation | null =
    activeCitation || (allCitations.length > 0 ? allCitations[selectedIdx] : null);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isTable = currentCitation?.type === 'table';
  const tableCit = isTable ? (currentCitation as TableCitation) : null;
  const docCit = !isTable && currentCitation ? (currentCitation as DocumentCitation) : null;

  return (
    <aside
      className="evidence-drawer-container"
      style={{
        width: '380px',
        minWidth: '380px',
        height: '100vh',
        backgroundColor: 'var(--bg-surface)',
        borderLeft: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        zIndex: 50,
      }}
    >
      {/* Drawer Header */}
      <div style={{
        padding: '14px 16px',
        borderBottom: '1px solid var(--border-subtle)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        backgroundColor: 'var(--bg-paper)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{
            fontSize: '11px',
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            backgroundColor: 'var(--accent-volt)',
            padding: '2px 6px',
            borderRadius: '3px',
          }}>
            Evidence
          </span>
          <span style={{ fontSize: '13px', fontWeight: 600 }}>Inspection Drawer</span>
        </div>
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            fontSize: '14px',
            cursor: 'pointer',
            color: 'var(--text-muted)',
            padding: '4px',
          }}
        >
          ✕
        </button>
      </div>

      {/* Citation Selector Tabs if multiple citations */}
      {allCitations.length > 1 && (
        <div style={{
          display: 'flex',
          borderBottom: '1px solid var(--border-subtle)',
          backgroundColor: 'var(--bg-paper)',
          overflowX: 'auto',
        }}>
          {allCitations.map((c, idx) => (
            <button
              key={idx}
              onClick={() => setSelectedIdx(idx)}
              style={{
                flex: 1,
                padding: '8px 12px',
                fontSize: '11.5px',
                border: 'none',
                borderBottom: (selectedIdx === idx && !activeCitation) || activeCitation === c
                  ? '2px solid var(--accent-volt-dark)'
                  : '2px solid transparent',
                backgroundColor: 'transparent',
                fontWeight: 600,
                cursor: 'pointer',
                color: 'var(--text-primary)',
                whiteSpace: 'nowrap',
              }}
            >
              {c.type === 'table' ? `Table [${idx + 1}]` : `Doc [${idx + 1}]`}
            </button>
          ))}
        </div>
      )}

      {/* Main Evidence Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px' }}>
        {!currentCitation ? (
          <div style={{ color: 'var(--text-muted)', fontSize: '13px', textAlign: 'center', marginTop: '40px' }}>
            Click any inline citation badge in the thread to inspect machine-verified evidence.
          </div>
        ) : isTable && tableCit ? (
          <div>
            {/* Table Proof Header */}
            <div style={{ marginBottom: '12px' }}>
              <div style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
                Tables Accessed
              </div>
              <div style={{ fontSize: '13px', fontWeight: 600, marginTop: '2px' }}>
                {tableCit.tables?.join(', ') || 'DuckDB Table'}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '2px' }}>
                {tableCit.row_count || tableCit.result_rows?.length || 0} rows matched
              </div>
            </div>

            {/* Executed SQL Box */}
            <div style={{ marginBottom: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)' }}>Executed SQL (Sandboxed)</span>
                <button
                  onClick={() => handleCopy(tableCit.sql)}
                  style={{
                    fontSize: '11px',
                    padding: '2px 8px',
                    backgroundColor: 'var(--bg-paper)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: '3px',
                    cursor: 'pointer',
                  }}
                >
                  {copied ? 'Copied!' : 'Copy'}
                </button>
              </div>
              <pre style={{
                backgroundColor: '#1E293B',
                color: '#F8FAFC',
                padding: '10px',
                borderRadius: '4px',
                fontSize: '11px',
                lineHeight: 1.4,
                overflowX: 'auto',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all',
              }}>
                {tableCit.sql}
              </pre>
            </div>

            {/* Result Rows Preview Table */}
            {tableCit.result_rows && tableCit.result_rows.length > 0 && (
              <div>
                <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px' }}>
                  Result Rows Preview ({tableCit.result_rows.length} rows)
                </div>
                <div style={{ overflowX: 'auto', border: '1px solid var(--border-subtle)', borderRadius: '4px' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11.5px' }} className="tabular-nums">
                    <thead>
                      <tr style={{ backgroundColor: 'var(--bg-paper)', borderBottom: '1px solid var(--border-subtle)' }}>
                        {Object.keys(tableCit.result_rows[0]).map((col) => (
                          <th key={col} style={{ padding: '6px 8px', textAlign: 'left', fontWeight: 600 }}>
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {tableCit.result_rows.slice(0, 50).map((row, rIdx) => (
                        <tr
                          key={rIdx}
                          style={{
                            borderBottom: '1px solid var(--border-subtle)',
                            backgroundColor: rIdx % 2 === 0 ? 'transparent' : 'var(--bg-paper)',
                          }}
                        >
                          {Object.values(row).map((val: any, cIdx) => (
                            <td key={cIdx} style={{ padding: '5px 8px' }}>
                              {String(val ?? '')}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        ) : docCit ? (
          <div>
            {/* Document Citation Provenance */}
            <div style={{ marginBottom: '14px' }}>
              <div style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
                Document Provenance
              </div>
              <div style={{ fontSize: '13px', fontWeight: 600, marginTop: '2px' }}>
                {docCit.source || docCit.file_name}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                Document Date: <b>{docCit.date || 'Undated'}</b> {docCit.page ? `• Page ${docCit.page}` : ''} {docCit.section ? `• ${docCit.section}` : ''}
              </div>
            </div>

            {/* Verbatim Quote Card */}
            {docCit.quote && (
              <div style={{
                backgroundColor: 'var(--bg-paper)',
                borderLeft: '3px solid var(--accent-volt-dark)',
                padding: '10px 12px',
                borderRadius: '0 4px 4px 0',
                marginBottom: '16px',
                fontSize: '12px',
                lineHeight: 1.5,
              }}>
                <div style={{ fontSize: '10.5px', fontWeight: 600, color: 'var(--color-success)', marginBottom: '4px' }}>
                  ✓ Machine-Verified Verbatim Quote
                </div>
                <div style={{ fontStyle: 'italic', color: 'var(--text-primary)' }}>
                  "{docCit.quote}"
                </div>
              </div>
            )}

            {/* Version Timeline / Superseded Facts */}
            {docCit.superseded && docCit.superseded.length > 0 && (
              <div style={{ marginTop: '16px' }}>
                <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '8px' }}>
                  Version Timeline (Historical Superseded Facts)
                </div>
                <div style={{ borderLeft: '2px solid var(--border-strong)', paddingLeft: '12px' }}>
                  {docCit.superseded.map((sup, sIdx) => (
                    <div key={sIdx} style={{ marginBottom: '10px', fontSize: '11.5px' }}>
                      <div style={{ fontWeight: 600, color: 'var(--text-muted)' }}>
                        Version {sup.version || sup.date || 'Older'}
                      </div>
                      <div style={{ color: 'var(--text-dim)', marginTop: '1px' }}>
                        {sup.value || JSON.stringify(sup)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </aside>
  );
};
