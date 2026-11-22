import React from 'react';
import { ChartSpec } from '../types';

interface InlineChartProps {
  chart: ChartSpec;
}

export const InlineChart: React.FC<InlineChartProps> = ({ chart }) => {
  const { chart_type, title, x_label, y_label, data_points } = chart;

  if (!data_points || data_points.length === 0) {
    return null;
  }

  const svgWidth = 640;
  const svgHeight = 260;
  const padding = { top: 30, right: 30, bottom: 50, left: 75 };
  const chartWidth = svgWidth - padding.left - padding.right;
  const chartHeight = svgHeight - padding.top - padding.bottom;

  const maxY = Math.max(...data_points.map((p) => p.y), 1.0);
  const minY = Math.min(...data_points.map((p) => p.y), 0.0);
  const rangeY = maxY - minY || 1.0;

  // Format currency/number helper
  const formatVal = (v: number) => {
    if (v >= 1000) {
      return v.toLocaleString('en-IN', { maximumFractionDigits: 2 });
    }
    return v.toFixed(v % 1 === 0 ? 0 : 2);
  };

  return (
    <div
      style={{
        marginTop: '14px',
        marginBottom: '10px',
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
        borderRadius: '6px',
        padding: '16px',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <h4 style={{ margin: 0, fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
          {title}
        </h4>
        <span
          style={{
            fontSize: '10px',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            padding: '2px 6px',
            borderRadius: '3px',
            backgroundColor: 'var(--bg-paper)',
            border: '1px solid var(--border-subtle)',
            color: 'var(--text-muted)',
            fontWeight: 600,
          }}
        >
          {chart_type} chart
        </span>
      </div>

      {/* SVG Visualization */}
      <div style={{ width: '100%', overflowX: 'auto' }}>
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          style={{ width: '100%', maxWidth: `${svgWidth}px`, height: 'auto', display: 'block' }}
        >
          {/* Y Axis Grid lines and Labels */}
          {[0, 0.25, 0.5, 0.75, 1.0].map((ratio, idx) => {
            const yPos = padding.top + chartHeight - ratio * chartHeight;
            const val = minY + ratio * rangeY;
            return (
              <g key={idx}>
                <line
                  x1={padding.left}
                  y1={yPos}
                  x2={svgWidth - padding.right}
                  y2={yPos}
                  stroke="var(--border-subtle)"
                  strokeDasharray={ratio === 0 ? 'none' : '3 3'}
                  strokeWidth="1"
                />
                <text
                  x={padding.left - 8}
                  y={yPos + 4}
                  textAnchor="end"
                  fontSize="10"
                  fill="var(--text-muted)"
                  fontFamily="monospace"
                >
                  {formatVal(val)}
                </text>
              </g>
            );
          })}

          {/* Bar Chart rendering */}
          {chart_type === 'bar' && (
            <g>
              {data_points.map((p, i) => {
                const barWidth = Math.max((chartWidth / data_points.length) * 0.6, 12);
                const slotWidth = chartWidth / data_points.length;
                const xPos = padding.left + i * slotWidth + (slotWidth - barWidth) / 2;
                const barH = (p.y / maxY) * chartHeight;
                const yPos = padding.top + chartHeight - barH;

                return (
                  <g key={i}>
                    <rect
                      x={xPos}
                      y={yPos}
                      width={barWidth}
                      height={barH}
                      fill="var(--color-primary, #0F766E)"
                      rx="2"
                    />
                    <text
                      x={xPos + barWidth / 2}
                      y={svgHeight - padding.bottom + 14}
                      textAnchor="middle"
                      fontSize="9"
                      fill="var(--text-primary)"
                    >
                      {p.x.length > 10 ? `${p.x.slice(0, 9)}…` : p.x}
                    </text>
                  </g>
                );
              })}
            </g>
          )}

          {/* Line Chart rendering */}
          {chart_type === 'line' && (
            <g>
              {/* Draw connected polyline */}
              <polyline
                fill="none"
                stroke="var(--color-primary, #0F766E)"
                strokeWidth="2.5"
                points={data_points
                  .map((p, i) => {
                    const xPos = padding.left + (i / Math.max(data_points.length - 1, 1)) * chartWidth;
                    const yPos = padding.top + chartHeight - ((p.y - minY) / rangeY) * chartHeight;
                    return `${xPos},${yPos}`;
                  })
                  .join(' ')}
              />
              {/* Draw points & labels */}
              {data_points.map((p, i) => {
                const xPos = padding.left + (i / Math.max(data_points.length - 1, 1)) * chartWidth;
                const yPos = padding.top + chartHeight - ((p.y - minY) / rangeY) * chartHeight;
                return (
                  <g key={i}>
                    <circle
                      cx={xPos}
                      cy={yPos}
                      r="4"
                      fill="var(--accent-volt, #D4E815)"
                      stroke="var(--color-primary, #0F766E)"
                      strokeWidth="2"
                    />
                    <text
                      x={xPos}
                      y={svgHeight - padding.bottom + 14}
                      textAnchor="middle"
                      fontSize="9"
                      fill="var(--text-primary)"
                    >
                      {p.x.length > 7 ? p.x.slice(-5) : p.x}
                    </text>
                  </g>
                );
              })}
            </g>
          )}

          {/* X & Y Axis titles */}
          <text
            x={padding.left}
            y={padding.top - 12}
            fontSize="10"
            fill="var(--text-muted)"
            fontWeight="500"
          >
            {y_label}
          </text>
          <text
            x={svgWidth / 2}
            y={svgHeight - 10}
            fontSize="10"
            textAnchor="middle"
            fill="var(--text-muted)"
            fontWeight="500"
          >
            {x_label}
          </text>
        </svg>
      </div>

      {/* Tabular data table below chart (Spec 7.8) */}
      <div style={{ marginTop: '14px', borderTop: '1px solid var(--border-subtle)', paddingTop: '10px' }}>
        <table
          className="tabular-nums"
          style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11.5px' }}
        >
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-strong)', textAlign: 'left', color: 'var(--text-muted)' }}>
              <th style={{ padding: '6px 8px', fontWeight: 600 }}>{x_label}</th>
              <th style={{ padding: '6px 8px', fontWeight: 600, textAlign: 'right' }}>{y_label}</th>
            </tr>
          </thead>
          <tbody>
            {data_points.map((dp, idx) => (
              <tr
                key={idx}
                style={{
                  borderBottom: '1px solid var(--border-subtle)',
                  backgroundColor: idx % 2 === 0 ? 'transparent' : 'var(--bg-paper)',
                }}
              >
                <td style={{ padding: '6px 8px', color: 'var(--text-primary)' }}>{dp.x}</td>
                <td style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 500, color: 'var(--text-primary)' }}>
                  {formatVal(dp.y)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
