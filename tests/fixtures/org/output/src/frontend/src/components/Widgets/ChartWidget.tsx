import { useEffect, useRef, useState } from 'react';
import { createChart, ISeriesApi, SeriesType } from 'lightweight-charts';
import { apiFetch } from '../../api';
import type { WidgetConfig, OHLCVBar, LinePoint } from '../../types';
import styles from './ChartWidget.module.css';

interface ChartWidgetProps {
  config: WidgetConfig;
  chartType?: 'candlestick' | 'line' | 'area';
}

interface FeedResponse<T> { data: T | null; last_computed: string | null; last_error: string | null; }

export function ChartWidget({ config, chartType = 'candlestick' }: ChartWidgetProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ReturnType<typeof createChart> | null>(null);
  const seriesRef = useRef<ISeriesApi<SeriesType> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [empty, setEmpty] = useState(false);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: { background: { color: 'transparent' }, textColor: '#6e7681' },
      grid: { vertLines: { color: '#1e1e3f' }, horzLines: { color: '#1e1e3f' } },
      crosshair: {
        vertLine: { color: '#58a6ff', width: 1, labelBackgroundColor: '#13132b' },
        horzLine: { color: '#58a6ff', width: 1, labelBackgroundColor: '#13132b' },
      },
      rightPriceScale: { borderColor: '#1e1e3f' },
      timeScale: { borderColor: '#1e1e3f', timeVisible: true },
      width: containerRef.current.clientWidth,
      height: 280,
    });
    chartRef.current = chart;

    const obs = new ResizeObserver(entries => {
      const e = entries[0];
      if (e) chart.applyOptions({ width: e.contentRect.width });
    });
    obs.observe(containerRef.current);
    return () => { obs.disconnect(); chart.remove(); chartRef.current = null; seriesRef.current = null; };
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    setLoading(true);
    setError(null);

    if (seriesRef.current) {
      chart.removeSeries(seriesRef.current);
      seriesRef.current = null;
    }

    apiFetch<OHLCVBar[] | LinePoint[] | FeedResponse<OHLCVBar[] | LinePoint[]>>(config.endpoint)
      .then(payload => {
        const points = Array.isArray(payload) ? payload : (payload.data ?? []);
        if (!chartRef.current) return;
        if (points.length === 0) {
          setEmpty(true);
          return;
        }
        setEmpty(false);
        if (chartType === 'candlestick') {
          const series = chart.addCandlestickSeries({
            upColor: '#3fb950', downColor: '#f85149',
            borderUpColor: '#3fb950', borderDownColor: '#f85149',
            wickUpColor: '#3fb950', wickDownColor: '#f85149',
          });
          series.setData(points as OHLCVBar[]);
          seriesRef.current = series;
        } else if (chartType === 'line') {
          const series = chart.addLineSeries({ color: '#58a6ff', lineWidth: 2 });
          series.setData(points as LinePoint[]);
          seriesRef.current = series;
        } else {
          const series = chart.addAreaSeries({
            lineColor: '#58a6ff', topColor: 'rgba(88,166,255,0.3)',
            bottomColor: 'rgba(88,166,255,0.0)', lineWidth: 2,
          });
          series.setData(points as LinePoint[]);
          seriesRef.current = series;
        }
        chart.timeScale().fitContent();
      })
      .catch(e => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, [config.endpoint, chartType]);

  return (
    <div className={styles.panel}>
      {loading && <div className={styles.overlay}>Loading chart…</div>}
      {error && <div className={styles.overlayError}>{error}</div>}
      {empty && !loading && !error && (
        <div className={styles.overlay}>{config.empty ?? 'No data yet'}</div>
      )}
      <div ref={containerRef} className={styles.container} />
    </div>
  );
}
