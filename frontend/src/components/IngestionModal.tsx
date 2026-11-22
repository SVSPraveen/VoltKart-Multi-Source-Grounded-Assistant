import React from 'react';
import { IngestionSummary } from '../types';

interface IngestionModalProps {
  isOpen: boolean;
  onClose: () => void;
  summary: IngestionSummary | null;
}

export const IngestionModal: React.FC<IngestionModalProps> = ({
  isOpen,
  onClose,
  summary,
}) => {
  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(17, 24, 39, 0.4)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 100,
      padding: '20px',
    }}>
      <div style={{
        backgroundColor: 'var(--bg-paper)',
        borderRadius: '8px',
        border: '1px solid var(--border-strong)',
        maxWidth: '750px',
        width: '100%',
        maxHeight: '85vh',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 10px 25px rgba(0,0,0,0.1)',
        overflow: 'hidden',
      }}>
        {/* Modal Header */}
        <div style={{
          padding: '16px 20px',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          backgroundColor: 'var(--bg-surface)',
        }}>
          <div>
            <h3 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)' }}>
              Ingestion Schema & Metadata Summary
            </h3>
            <p style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              Profiling across DuckDB analytical tables and SQLite versioned document chunks
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              fontSize: '16px',
              cursor: 'pointer',
              color: 'var(--text-muted)',
            }}
          >
            ✕
          </button>
        </div>

        {/* Modal Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
          {!summary ? (
            <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '30px' }}>
              Loading ingestion summary...
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {/* Tables Section */}
              <div>
                <h4 style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '10px' }}>
                  DuckDB Analytical Tables ({summary.tables?.length || 0})
                </h4>
                {summary.tables && summary.tables.length > 0 ? (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '10px' }}>
                    {summary.tables.map((t) => (
                      <div
                        key={t.table_name}
                        style={{
                          backgroundColor: 'var(--bg-surface)',
                          border: '1px solid var(--border-subtle)',
                          borderRadius: '6px',
                          padding: '12px',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontWeight: 600, fontSize: '13px' }}>{t.table_name}</span>
                          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }} className="tabular-nums">
                            {t.row_count} rows • {t.column_count} cols
                          </span>
                        </div>
                        <div style={{ fontSize: '11.5px', color: 'var(--text-muted)', marginTop: '4px' }}>
                          PK: <b>{t.primary_key || 'None inferred'}</b>
                        </div>
                        {t.inferred_relationships && t.inferred_relationships.length > 0 && (
                          <div style={{ marginTop: '6px', fontSize: '11px', color: 'var(--text-dim)' }}>
                            Rel: {t.inferred_relationships.map((r, rIdx) => (
                              <span key={rIdx}>
                                {r.from_column} → {r.to_table}.{r.to_column} ({(r.confidence * 100).toFixed(0)}%)
                                {rIdx < t.inferred_relationships.length - 1 ? ', ' : ''}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ fontSize: '12px', color: 'var(--text-dim)' }}>No tables currently loaded.</div>
                )}
              </div>

              {/* Documents Section */}
              <div>
                <h4 style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '10px' }}>
                  Ingested Documents & Version Families ({summary.documents?.length || 0})
                </h4>
                {summary.documents && summary.documents.length > 0 ? (
                  <div style={{ border: '1px solid var(--border-subtle)', borderRadius: '6px', overflow: 'hidden' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                      <thead>
                        <tr style={{ backgroundColor: 'var(--bg-surface)', borderBottom: '1px solid var(--border-subtle)' }}>
                          <th style={{ padding: '8px 10px', textAlign: 'left', fontWeight: 600 }}>File</th>
                          <th style={{ padding: '8px 10px', textAlign: 'left', fontWeight: 600 }}>Family</th>
                          <th style={{ padding: '8px 10px', textAlign: 'left', fontWeight: 600 }}>Detected Date</th>
                          <th style={{ padding: '8px 10px', textAlign: 'right', fontWeight: 600 }}>Chunks</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.documents.map((d, dIdx) => (
                          <tr
                            key={d.sha256}
                            style={{
                              borderBottom: '1px solid var(--border-subtle)',
                              backgroundColor: dIdx % 2 === 0 ? 'transparent' : 'var(--bg-surface)',
                            }}
                          >
                            <td style={{ padding: '7px 10px', fontWeight: 500 }}>{d.file_name}</td>
                            <td style={{ padding: '7px 10px', color: 'var(--text-muted)' }}>{d.version_family}</td>
                            <td style={{ padding: '7px 10px' }}>
                              <span>{d.doc_date || 'undated'}</span>
                              <span style={{ fontSize: '10px', color: 'var(--text-dim)', marginLeft: '4px' }}>
                                ({d.doc_date_source})
                              </span>
                            </td>
                            <td style={{ padding: '7px 10px', textAlign: 'right' }} className="tabular-nums">
                              {d.chunk_count}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div style={{ fontSize: '12px', color: 'var(--text-dim)' }}>No documents currently ingested.</div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div style={{
          padding: '12px 20px',
          borderTop: '1px solid var(--border-subtle)',
          display: 'flex',
          justifyContent: 'flex-end',
          backgroundColor: 'var(--bg-surface)',
        }}>
          <button
            onClick={onClose}
            style={{
              padding: '6px 14px',
              backgroundColor: 'var(--bg-paper)',
              border: '1px solid var(--border-strong)',
              borderRadius: '4px',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
