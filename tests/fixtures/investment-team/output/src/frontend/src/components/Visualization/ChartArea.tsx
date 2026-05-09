import { useState, useEffect, useRef } from 'react';
import { createChart, ISeriesApi, SeriesType } from 'lightweight-charts';
import { apiFetch } from '../../api';
import type { ChartConfig, OHLCVBar, LinePoint } from '../../types';
import styles from './ChartArea.module.css';

interface ChartAreaProps {
  configs: ChartConfig[];
  selectedEntityId: string | null;
  linkedItemCounts?: Record<string, number>;
}

interface ChartPanelProps {
  config: ChartConfig;
  selectedEntityId: string | null;
  linkedItemCount?: number;
}

function ChartPanel({ config, selectedEntityId, linkedItemCount }: ChartPanelProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ReturnType<typeof createChart> | null>(null);
  // Track the active series so we can remove it before adding a new one
  const seriesRef = useRef<ISeriesApi<SeriesType> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [noSelection, setNoSelection] = useState(false);

  const needsEntity = !!config.linked_to;

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: 'transparent' },
        textColor: '#6e7681',
      },
      grid: {
        vertLines: { color: '#1e1e3f' },
        horzLines: { color: '#1e1e3f' },
      },
      crosshair: {
        vertLine: { color: '#58a6ff', width: 1, labelBackgroundColor: '#13132b' },
        horzLine: { color: '#58a6ff', width: 1, labelBackgroundColor: '#13132b' },
      },
      rightPriceScale: { borderColor: '#1e1e3f' },
      timeScale: { borderColor: '#1e1e3f', timeVisible: true },
      width: containerRef.current.clientWidth,
      height: 260,
    });

    chartRef.current = chart;

    const resizeObs = new ResizeObserver(entries => {
      const entry = entries[0];
      if (entry) {
        chart.applyOptions({ width: entry.contentRect.width });
      }
    });
    resizeObs.observe(containerRef.current);

    return () => {
      resizeObs.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    if (needsEntity && !selectedEntityId) {
      setNoSelection(true);
      return;
    }
    setNoSelection(false);

    const endpoint = selectedEntityId
      ? config.endpoint.replace('{entity_id}', selectedEntityId)
      : config.endpoint;

    setLoading(true);
    setError(null);

    // Remove previous series before adding a new one
    if (seriesRef.current) {
      chart.removeSeries(seriesRef.current);
      seriesRef.current = null;
    }

    apiFetch<OHLCVBar[] | LinePoint[]>(endpoint)
      .then(data => {
        if (!chartRef.current) return;
        if (config.type === 'candlestick') {
          const series = chart.addCandlestickSeries({
            upColor: '#3fb950',
            downColor: '#f85149',
            borderUpColor: '#3fb950',
            borderDownColor: '#f85149',
            wickUpColor: '#3fb950',
            wickDownColor: '#f85149',
          });
          series.setData(data as OHLCVBar[]);
          seriesRef.current = series;
        } else if (config.type === 'line') {
          const series = chart.addLineSeries({ color: '#58a6ff', lineWidth: 2 });
          series.setData(data as LinePoint[]);
          seriesRef.current = series;
        } else if (config.type === 'area') {
          const series = chart.addAreaSeries({
            lineColor: '#58a6ff',
            topColor: 'rgba(88,166,255,0.3)',
            bottomColor: 'rgba(88,166,255,0.0)',
            lineWidth: 2,
          });
          series.setData(data as LinePoint[]);
          seriesRef.current = series;
        }
        chart.timeScale().fitContent();
      })
      .catch(e => setError((e as Error).message))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedEntityId, config.endpoint, config.type]);

  const linkedEmpty = needsEntity && linkedItemCount === 0;

  return (
    <div className={styles.panel}>
      {loading && <div className={styles.overlay}>Loading chart…</div>}
      {error && <div className={styles.overlayError}>{error}</div>}
      {noSelection && linkedEmpty && (
        <div className={styles.overlay}>No data yet</div>
      )}
      {noSelection && !linkedEmpty && (
        <div className={styles.overlay}>Select an entity to view the chart</div>
      )}
      <div ref={containerRef} className={styles.chartContainer} />
    </div>
  );
}

export function ChartArea({ configs, selectedEntityId, linkedItemCounts }: ChartAreaProps) {
  const [activeTab, setActiveTab] = useState(0);

  if (!configs || configs.length === 0) return null;

  const active = configs[activeTab] ?? configs[0];
  if (!active) return null;

  const linkedItemCount = active.linked_to ? linkedItemCounts?.[active.linked_to] : undefined;

  return (
    <div className={styles.chartArea}>
      {configs.length > 1 && (
        <div className={styles.tabs}>
          {configs.map((c, i) => (
            <button
              key={i}
              className={`${styles.tab} ${activeTab === i ? styles.tabActive : ''}`}
              onClick={() => setActiveTab(i)}
            >
              {c.title}
            </button>
          ))}
        </div>
      )}
      {configs.length === 1 && (
        <div className={styles.singleTitle}>{active.title}</div>
      )}
      <ChartPanel config={active} selectedEntityId={selectedEntityId} linkedItemCount={linkedItemCount} />
    </div>
  );
}
