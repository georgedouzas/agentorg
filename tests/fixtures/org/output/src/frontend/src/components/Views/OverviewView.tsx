import { useEffect, useState } from 'react';
import { StatsGrid } from '../Widgets/StatsGrid';
import { EntityGrid } from '../Widgets/EntityGrid';
import { BarTable } from '../Widgets/BarTable';
import { Feed } from '../Widgets/Feed';
import { ChartWidget } from '../Widgets/ChartWidget';
import { ChartArea } from '../Visualization/ChartArea';
import { apiFetch } from '../../api';
import type { AppConfig, WidgetConfig, WidgetType } from '../../types';
import styles from './OverviewView.module.css';

interface OverviewViewProps {
  config: AppConfig;
  configured: boolean;
  onPanelOpen: (title: string, endpoint: string) => void;
}

interface FeedRow {
  type: string;
  name: string;
  title: string | null;
  display: { widget?: WidgetType; featured?: boolean; cols?: number; order?: number; empty?: string };
  metadata: Record<string, unknown>;
  last_computed: string | null;
}

export function OverviewView({ config, configured, onPanelOpen }: OverviewViewProps) {
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  const [entityCounts, setEntityCounts] = useState<Record<string, number>>({});
  const [feeds, setFeeds] = useState<FeedRow[]>([]);

  useEffect(() => {
    if (!configured) return;
    apiFetch<FeedRow[]>('/api/feeds')
      .then(setFeeds)
      .catch(() => setFeeds([]));
  }, [configured]);

  function handleEntitySelect(id: string) {
    setSelectedEntityId(prev => prev === id ? null : id);
  }

  function renderFeed(feed: FeedRow) {
    const widget: WidgetConfig = {
      type: (feed.display.widget ?? 'stats-grid') as WidgetType,
      title: feed.title ?? feed.name,
      endpoint: `/api/knowledge/${feed.type}/${feed.name}/data`,
      id: feed.name,
      cols: feed.display.cols,
      empty: feed.display.empty,
    };
    switch (widget.type) {
      case 'stats-grid':
        return (
          <section key={feed.name} className={styles.section}>
            <h2 className={styles.sectionTitle}>{widget.title}</h2>
            <StatsGrid config={widget} />
          </section>
        );
      case 'entity-grid':
        return (
          <section key={feed.name} className={styles.section}>
            <h2 className={styles.sectionTitle}>{widget.title}</h2>
            <EntityGrid
              config={widget}
              onEntitySelect={handleEntitySelect}
              selectedEntityId={selectedEntityId ?? undefined}
              onItemsChange={n => setEntityCounts(prev => ({ ...prev, [feed.name]: n }))}
            />
          </section>
        );
      case 'bar-table':
        return (
          <section key={feed.name} className={styles.section}>
            <h2 className={styles.sectionTitle}>{widget.title}</h2>
            <BarTable
              config={widget}
              onAction={endpoint => onPanelOpen(widget.title, endpoint)}
            />
          </section>
        );
      case 'feed':
        return (
          <section key={feed.name} className={styles.section}>
            <h2 className={styles.sectionTitle}>{widget.title}</h2>
            <Feed config={widget} />
          </section>
        );
      case 'candlestick':
      case 'line':
      case 'area':
        return (
          <section key={feed.name} className={styles.section}>
            <h2 className={styles.sectionTitle}>{widget.title}</h2>
            <ChartWidget config={widget} chartType={widget.type as 'candlestick' | 'line' | 'area'} />
          </section>
        );
      default:
        return null;
    }
  }

  if (configured !== true) {
    return <div className={styles.view} />;
  }

  return (
    <div className={styles.view}>
      {feeds.map(renderFeed)}
      {config.visualizations.length > 0 && (
        <section className={styles.section}>
          <ChartArea
            configs={config.visualizations}
            selectedEntityId={selectedEntityId}
            linkedItemCounts={entityCounts}
          />
        </section>
      )}
    </div>
  );
}
