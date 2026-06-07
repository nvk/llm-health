import '@mantine/core/styles.css';
import './styles.css';

import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Accordion,
  ActionIcon,
  AppShell,
  Badge,
  Button,
  Card,
  Checkbox,
  ComboboxItem,
  Divider,
  Group,
  MantineProvider,
  MultiSelect,
  Paper,
  ScrollArea,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Tabs,
  Text,
  TextInput,
  ThemeIcon,
  Title,
  Tooltip as MantineTooltip,
  rem,
} from '@mantine/core';
import {
  IconActivity,
  IconAlertTriangle,
  IconChartDots3,
  IconClipboardList,
  IconDatabase,
  IconDownload,
  IconExternalLink,
  IconFlag,
  IconMoon,
  IconSearch,
  IconSun,
  IconTimeline,
} from '@tabler/icons-react';
import {
  CartesianGrid,
  LabelList,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

type ThemeMode = 'light' | 'dark';
type SectionId = 'review' | 'timeline' | 'sources';
type TimeRange = 'all' | '30d' | '90d' | 'ytd' | '18mo';
type TimelineMode = 'stack' | 'overlay';
type ScaleMode = 'auto' | 'raw' | 'norm' | 'center' | 'pctmean' | 'pctfirst' | 'z' | 'log';
type AggMode = 'observed' | 'mean-date';
type RowFocus = 'all' | 'flags' | 'pending' | 'numeric';

type RawObservation = Record<string, string | undefined>;
type RawWearable = Record<string, string | undefined>;
type RawReport = Record<string, string | undefined>;

type ProfilePayload = {
  profile_id: string;
  role?: string;
  birth_year?: number;
  birth_month?: number;
  tags?: string[];
};

type HealthPayload = {
  generated?: string;
  source?: string;
  observations?: RawObservation[];
  reports?: RawReport[];
  wearable_daily?: RawWearable[];
  profile_context?: Record<string, Record<string, unknown>>;
  profiles?: ProfilePayload[];
  export_summary?: Record<string, unknown>;
};

declare global {
  interface Window {
    HEALTH_ASSESSMENT_V2?: HealthPayload;
  }
}

type LabPoint = {
  id: string;
  profileId: string;
  familyRole: string;
  date: string;
  time: number;
  sourceId: string;
  sourceTitle: string;
  panel: string;
  category: string;
  marker: string;
  unit: string;
  valueRaw: string;
  value: number | null;
  resultType: string;
  refRaw: string;
  flagRaw: string;
  interpretation: string;
  specimen: string;
  method: string;
  confidence: string;
  notes: string;
  pending: boolean;
  derived: boolean;
  sourceNotePath?: string;
};

type WearablePoint = {
  id: string;
  profileId: string;
  familyRole: string;
  date: string;
  time: number;
  category: string;
  metric: string;
  unit: string;
  value: number;
  aggregation: string;
};

type ChartPoint = {
  id: string;
  date: string;
  time: number;
  value: number;
  rawValue: number;
  valueRaw: string;
  flagRaw: string;
  pending?: boolean;
  sourceId?: string;
  refRaw?: string;
  note?: string;
  plotValue?: number;
  label?: string;
};

type RangeBand = { low: number | null; high: number | null; label: string };

type Series = {
  id: string;
  label: string;
  shortLabel: string;
  category: string;
  unit: string;
  kind: 'lab' | 'context';
  color: string;
  points: ChartPoint[];
  ref: RangeBand | null;
  derived: boolean;
};

type UiState = {
  profile: string;
  range: TimeRange;
  category: string;
  section: SectionId;
  mode: TimelineMode;
  scale: ScaleMode;
  agg: AggMode;
  smoothing: string;
  rowFocus: RowFocus;
  query: string;
  contextMetrics: string[];
  showFlags: boolean;
  showLabels: boolean;
  theme: ThemeMode;
};

const DATA = window.HEALTH_ASSESSMENT_V2 || {};
const REPORTS = new Map((DATA.reports || []).map((report) => [String(report.source_id || ''), report]));
const RANGE_OPTIONS: { value: TimeRange; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: '30d', label: '30d' },
  { value: '90d', label: '90d' },
  { value: 'ytd', label: 'YTD' },
  { value: '18mo', label: '18mo' },
];
const SCALE_OPTIONS: ComboboxItem[] = [
  { value: 'auto', label: 'Auto' },
  { value: 'raw', label: 'Raw values' },
  { value: 'norm', label: 'Normalized 0–100' },
  { value: 'center', label: 'Mean-centered' },
  { value: 'pctmean', label: '% of mean' },
  { value: 'pctfirst', label: '% change from first' },
  { value: 'z', label: 'Z-score' },
  { value: 'log', label: 'Log10' },
];
const SMOOTH_OPTIONS: ComboboxItem[] = [
  { value: 'none', label: 'No smoothing' },
  { value: 'mean3', label: '3-point mean' },
  { value: 'mean7', label: '7-point mean' },
  { value: 'mean30', label: '30-point mean' },
];
const PALETTE = ['#2f6fb2', '#2f855a', '#b7791f', '#805ad5', '#d94670', '#0891b2', '#b64035', '#64748b', '#14b8a6', '#f97316'];
const CONTEXT_COLOR = '#a36a00';
const TAG_LABELS: Record<string, string> = {
  OBSERVED: 'Observed',
  DERIVED: 'Derived',
  WEARABLE_CONTEXT: 'Wearable context',
  CONTEXT: 'Context',
  INFERENCE: 'Inference',
  DATA_GAP: 'Data gap',
  QA_ISSUE: 'QA issue',
};

function App() {
  const labRows = useMemo(() => (DATA.observations || []).map(normalizeLab).filter(Boolean) as LabPoint[], []);
  const wearableRows = useMemo(() => (DATA.wearable_daily || []).map(normalizeWearable).filter(Boolean) as WearablePoint[], []);
  const profileOptions = useMemo(() => buildProfiles(labRows, wearableRows), [labRows, wearableRows]);
  const [state, setState] = useState<UiState>(() => initialState(profileOptions));

  useEffect(() => {
    if (!profileOptions.some((profile) => profile.value === state.profile)) {
      setState((current) => ({ ...current, profile: profileOptions[0]?.value || 'rod' }));
    }
  }, [profileOptions, state.profile]);

  const allProfileRows = useMemo(
    () => labRows.filter((row) => row.profileId === state.profile),
    [labRows, state.profile],
  );
  const filteredRows = useMemo(() => filterLabs(allProfileRows, state), [allProfileRows, state]);
  const contextSeries = useMemo(() => buildContextSeries(wearableRows, labRows, state), [wearableRows, labRows, state]);
  const labSeries = useMemo(() => buildLabSeries(filteredRows), [filteredRows]);
  const categories = useMemo(() => buildCategoryOptions(allProfileRows), [allProfileRows]);
  const activeSeries = useMemo(() => {
    const series = [...labSeries, ...contextSeries];
    return series.sort(seriesSort);
  }, [labSeries, contextSeries]);
  const focusedRows = useMemo(() => focusRows(filteredRows, state.rowFocus), [filteredRows, state.rowFocus]);

  useEffect(() => {
    persistState(state);
  }, [state]);

  const update = (patch: Partial<UiState>) => setState((current) => ({ ...current, ...patch }));
  const visibleCategories = categoryGroups(activeSeries);
  const theme = state.theme;

  return (
    <MantineProvider
      forceColorScheme={theme}
      theme={{
        primaryColor: theme === 'dark' ? 'yellow' : 'blue',
        defaultRadius: 'sm',
        radius: {
          xs: rem(2),
          sm: rem(3),
          md: rem(5),
          lg: rem(7),
          xl: rem(8),
        },
      }}
    >
      <AppShell navbar={{ width: 334, breakpoint: 'sm' }} padding="lg" className="health-shell" data-v3-ui data-theme={theme}>
        <AppShell.Navbar p="md" className="nav-panel">
          <Stack gap="md" h="100%">
            <Group gap="sm" align="flex-start">
              <ThemeIcon size="xl" radius="xl" variant="gradient" gradient={{ from: theme === 'dark' ? 'yellow' : 'blue', to: theme === 'dark' ? 'orange' : 'cyan' }}>
                <IconActivity size={24} />
              </ThemeIcon>
              <div>
                <Text size="xs" tt="uppercase" fw={800} c="dimmed" lts={1.6}>llm-health</Text>
                <Title order={2} className="nav-title">Assessment board</Title>
                <Text size="sm" c="dimmed">Private local review board</Text>
              </div>
            </Group>

            <Paper className="risk-card" p="sm" radius="lg">
              <Group gap="xs" mb={4}><Badge color="red" variant="light">OWN-RISK</Badge><Text size="xs" fw={700}>Not medical advice</Text></Group>
              <Text size="xs" c="dimmed">Local, de-identified review layer. Verify sources before decisions.</Text>
            </Paper>

            <ScrollArea className="controls-scroll" type="auto">
              <Stack gap="md" pr="xs">
                <ControlLabel label="Profile" />
                <SegmentedControl
                  className="profile-switch"
                  data={profileOptions}
                  value={state.profile}
                  onChange={(value) => update({ profile: value, section: 'review' })}
                  fullWidth
                />

                <ControlLabel label="Time" />
                <SegmentedControl
                  data={RANGE_OPTIONS}
                  value={state.range}
                  onChange={(value) => update({ range: value as TimeRange })}
                  fullWidth
                />

                <ControlLabel label="Domain" />
                <Select
                  searchable
                  data={categories}
                  value={state.category}
                  onChange={(value) => update({ category: value || 'All categories' })}
                />

                <ControlLabel label="Timeline" />
                <SegmentedControl
                  data={[{ value: 'stack', label: 'Stack' }, { value: 'overlay', label: 'Overlay' }]}
                  value={state.mode}
                  onChange={(value) => update({ mode: value as TimelineMode, section: 'timeline' })}
                  fullWidth
                />

                <Group grow align="flex-end">
                  <Select label="Scale" data={SCALE_OPTIONS} value={state.scale} onChange={(value) => update({ scale: (value || 'auto') as ScaleMode })} />
                  <Select label="Smooth" data={SMOOTH_OPTIONS} value={state.smoothing} onChange={(value) => update({ smoothing: value || 'none' })} />
                </Group>

                <SegmentedControl
                  data={[{ value: 'observed', label: 'Observed' }, { value: 'mean-date', label: 'Mean/date' }]}
                  value={state.agg}
                  onChange={(value) => update({ agg: value as AggMode })}
                  fullWidth
                />

                <MultiSelect
                  label="Context overlays"
                  placeholder="Weight, steps, sleep…"
                  data={contextMetricOptions(wearableRows, state.profile)}
                  value={state.contextMetrics}
                  onChange={(value) => update({ contextMetrics: value })}
                  searchable
                  clearable
                  maxDropdownHeight={260}
                />

                <TextInput
                  label="Search markers"
                  leftSection={<IconSearch size={16} />}
                  value={state.query}
                  onChange={(event) => update({ query: event.currentTarget.value })}
                  placeholder="ALT, bilirubin, mercury…"
                />

                <Stack gap={6} className="toggle-stack">
                  <Checkbox label="Source flag rings" checked={state.showFlags} onChange={(event) => update({ showFlags: event.currentTarget.checked })} />
                  <Checkbox label="Exact date labels" checked={state.showLabels} onChange={(event) => update({ showLabels: event.currentTarget.checked })} />
                </Stack>
              </Stack>
            </ScrollArea>
          </Stack>
        </AppShell.Navbar>

        <AppShell.Main>
          <Stack gap="lg">
            <Header
              state={state}
              rows={filteredRows}
              allRows={allProfileRows}
              series={activeSeries}
              profileOptions={profileOptions}
              setState={setState}
            />

            <SummaryGrid
              rows={filteredRows}
              series={activeSeries}
              state={state}
              setState={setState}
            />

            <Tabs value={state.section} onChange={(value) => update({ section: (value || 'review') as SectionId })} className="main-tabs">
              <Tabs.List>
                <Tabs.Tab value="review" leftSection={<IconClipboardList size={16} />}>Review</Tabs.Tab>
                <Tabs.Tab value="timeline" leftSection={<IconTimeline size={16} />}>Timeline</Tabs.Tab>
                <Tabs.Tab value="sources" leftSection={<IconDatabase size={16} />}>Sources</Tabs.Tab>
              </Tabs.List>

              <Tabs.Panel value="review" pt="lg">
                <ReviewBoard
                  rows={filteredRows}
                  allRows={allProfileRows}
                  series={activeSeries}
                  groups={visibleCategories}
                  state={state}
                  setState={setState}
                />
              </Tabs.Panel>

              <Tabs.Panel value="timeline" pt="lg">
                <TimelineBoard
                  series={activeSeries}
                  state={state}
                  setState={setState}
                />
              </Tabs.Panel>

              <Tabs.Panel value="sources" pt="lg">
                <SourcesTable
                  rows={focusedRows}
                  totalRows={filteredRows.length}
                  rowFocus={state.rowFocus}
                  setState={setState}
                />
              </Tabs.Panel>
            </Tabs>
          </Stack>
        </AppShell.Main>
      </AppShell>
    </MantineProvider>
  );
}

function ControlLabel({ label }: { label: string }) {
  return <Text size="xs" tt="uppercase" fw={800} c="dimmed" lts={1.3} mb={-10}>{label}</Text>;
}

function Header({ state, rows, allRows, series, profileOptions, setState }: {
  state: UiState;
  rows: LabPoint[];
  allRows: LabPoint[];
  series: Series[];
  profileOptions: ComboboxItem[];
  setState: React.Dispatch<React.SetStateAction<UiState>>;
}) {
  const profile = profileOptions.find((option) => option.value === state.profile)?.label || displayAlias(state.profile);
  const latest = latestDate(rows);
  const totalLatest = latestDate(allRows);
  const flagged = rows.filter((row) => row.flagRaw && !row.pending).length;
  const pending = rows.filter((row) => row.pending).length;
  const themeToggle = () => setState((current) => ({ ...current, theme: current.theme === 'dark' ? 'light' : 'dark' }));
  return (
    <Paper className="hero" p="xl" radius="xl">
      <Group justify="space-between" align="flex-start" gap="lg">
        <div>
          <Group gap="xs" mb="sm">
            <Badge variant="light">{profile}</Badge>
            <Badge variant="light" color="gray">{state.range}</Badge>
            <Badge variant="light" color="gray">{state.category}</Badge>
          </Group>
          <Title order={1}>Longitudinal health evidence</Title>
          <Text c="dimmed" maw={760} mt={6}>
            Clean charts, source rows, context overlays, and deterministic flags from local de-identified data.
          </Text>
        </div>
        <Group gap="xs">
          <MantineTooltip label="Copy bookmarkable view">
            <Button variant="light" leftSection={<IconExternalLink size={16} />} onClick={() => navigator.clipboard?.writeText(location.href)}>Copy view</Button>
          </MantineTooltip>
          <MantineTooltip label="Export filtered rows">
            <Button leftSection={<IconDownload size={16} />} onClick={() => downloadCsv(rows)}>CSV</Button>
          </MantineTooltip>
          <ActionIcon variant="light" size="lg" onClick={themeToggle} aria-label="Toggle light/dark theme">
            {state.theme === 'dark' ? <IconSun size={19} /> : <IconMoon size={19} />}
          </ActionIcon>
        </Group>
      </Group>
      <Group mt="lg" gap="sm" className="hero-metrics">
        <MetricPill label={`${series.length.toLocaleString()} chart series`} icon={<IconChartDots3 size={15} />} onClick={() => setState((current) => ({ ...current, section: 'timeline' }))} />
        <MetricPill label={`${flagged.toLocaleString()} source flags`} icon={<IconFlag size={15} />} tone={flagged ? 'warn' : 'ok'} onClick={() => setState((current) => ({ ...current, section: 'sources', rowFocus: flagged ? 'flags' : 'all' }))} />
        <MetricPill label={`${pending.toLocaleString()} pending`} icon={<IconAlertTriangle size={15} />} tone={pending ? 'bad' : 'ok'} onClick={() => setState((current) => ({ ...current, section: 'sources', rowFocus: pending ? 'pending' : 'all' }))} />
        <MetricPill label={`latest ${latest || totalLatest || '—'}`} icon={<IconTimeline size={15} />} />
      </Group>
    </Paper>
  );
}

function MetricPill({ label, icon, tone = 'default', onClick }: { label: string; icon: React.ReactNode; tone?: 'default' | 'warn' | 'bad' | 'ok'; onClick?: () => void }) {
  return <button type="button" className={`metric-pill ${tone}`} onClick={onClick}>{icon}<span>{label}</span></button>;
}

function SummaryGrid({ rows, series, state, setState }: {
  rows: LabPoint[];
  series: Series[];
  state: UiState;
  setState: React.Dispatch<React.SetStateAction<UiState>>;
}) {
  const numeric = rows.filter((row) => row.value !== null).length;
  const flagged = rows.filter((row) => row.flagRaw && !row.pending).length;
  const pending = rows.filter((row) => row.pending).length;
  const derived = rows.filter((row) => row.derived).length;
  const cards = [
    { title: 'Evidence points', value: numeric.toLocaleString(), note: `${series.length} plotted series`, icon: IconChartDots3, section: 'timeline' as SectionId },
    { title: 'Source flags', value: flagged.toLocaleString(), note: flagged ? 'Click to audit' : 'None in filter', icon: IconFlag, section: 'sources' as SectionId, focus: 'flags' as RowFocus },
    { title: 'Pending rows', value: pending.toLocaleString(), note: 'Never plotted as dots', icon: IconAlertTriangle, section: 'sources' as SectionId, focus: 'pending' as RowFocus },
    { title: 'Derived rows', value: derived.toLocaleString(), note: 'Visible as Derived tags', icon: IconActivity, section: 'sources' as SectionId },
  ];
  return (
    <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="md">
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <Card key={card.title} className="stat-card" p="lg" radius="xl" onClick={() => setState((current) => ({ ...current, section: card.section, rowFocus: card.focus || current.rowFocus }))}>
            <Group justify="space-between" align="flex-start">
              <div>
                <Text size="xs" fw={800} c="dimmed" tt="uppercase" lts={1}>{card.title}</Text>
                <Title order={2}>{card.value}</Title>
                <Text size="sm" c="dimmed">{card.note}</Text>
              </div>
              <ThemeIcon radius="xl" variant="light" color={state.theme === 'dark' ? 'yellow' : 'blue'}><Icon size={20} /></ThemeIcon>
            </Group>
          </Card>
        );
      })}
    </SimpleGrid>
  );
}

function ReviewBoard({ rows, allRows, series, groups, state, setState }: {
  rows: LabPoint[];
  allRows: LabPoint[];
  series: Series[];
  groups: Map<string, Series[]>;
  state: UiState;
  setState: React.Dispatch<React.SetStateAction<UiState>>;
}) {
  const flagged = rows.filter((row) => row.flagRaw && !row.pending);
  const pending = rows.filter((row) => row.pending);
  const recent = [...rows].sort((a, b) => b.time - a.time).slice(0, 8);
  const rowsByCategory = countBy(allRows, (row) => row.category);
  const domainCards = [...groups.entries()].map(([category, list]) => ({ category, count: list.length, flags: list.flatMap((s) => s.points).filter((p) => p.flagRaw).length }));

  return (
    <Stack gap="lg">
      <SimpleGrid cols={{ base: 1, md: 3 }} spacing="md">
        <ReviewCard
          title="Needs source audit"
          tag={flagged.length ? 'QA_ISSUE' : 'OBSERVED'}
          value={`${flagged.length} flagged`}
          body={flagged.length ? summarizeMarkers(flagged) : 'No source-flagged rows in this filter.'}
          onClick={() => setState((current) => ({ ...current, section: 'sources', rowFocus: flagged.length ? 'flags' : 'all' }))}
        />
        <ReviewCard
          title="Pending / nonnumeric"
          tag={pending.length ? 'DATA_GAP' : 'OBSERVED'}
          value={`${pending.length} rows`}
          body={pending.length ? summarizeMarkers(pending) : 'Pending rows are kept in sources and are not plotted.'}
          onClick={() => setState((current) => ({ ...current, section: 'sources', rowFocus: pending.length ? 'pending' : 'all' }))}
        />
        <ReviewCard
          title="Timeline coverage"
          tag="OBSERVED"
          value={`${series.length} series`}
          body={`${state.category}; ${state.range}; latest ${latestDate(rows) || '—'}.`}
          onClick={() => setState((current) => ({ ...current, section: 'timeline' }))}
        />
      </SimpleGrid>

      <Paper p="lg" radius="xl" className="board-card">
        <Group justify="space-between" mb="md">
          <div>
            <Title order={3}>Domain map</Title>
            <Text size="sm" c="dimmed">Click a category to open its chart stack.</Text>
          </div>
          <Badge variant="light">{rowsByCategory.size} domains</Badge>
        </Group>
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="sm">
          {domainCards.map((domain) => (
            <button key={domain.category} type="button" className="domain-card" onClick={() => setState((current) => ({ ...current, category: domain.category, section: 'timeline' }))}>
              <Group justify="space-between">
                <Text fw={800}>{domain.category}</Text>
                <Badge color={domain.flags ? 'red' : 'gray'} variant="light">{domain.count} charts</Badge>
              </Group>
              <Text size="sm" c="dimmed">{rowsByCategory.get(domain.category) || 0} observations · {domain.flags} flags</Text>
            </button>
          ))}
        </SimpleGrid>
      </Paper>

      <Paper p="lg" radius="xl" className="board-card">
        <Group justify="space-between" mb="sm"><Title order={3}>Latest rows</Title><Badge variant="light">source preview</Badge></Group>
        <Stack gap="xs">
          {recent.map((row) => <SourceMiniRow key={row.id} row={row} />)}
          {!recent.length && <Text c="dimmed">No rows in the current filter.</Text>}
        </Stack>
      </Paper>
    </Stack>
  );
}

function ReviewCard({ title, tag, value, body, onClick }: { title: string; tag: string; value: string; body: string; onClick: () => void }) {
  return (
    <Card className="review-card" p="lg" radius="xl" onClick={onClick}>
      <Group justify="space-between" mb="xs"><Badge className={`tag tag-${tag.toLowerCase()}`} data-tag={tag} title={tag}>{tagLabel(tag)}</Badge><IconExternalLink size={16} /></Group>
      <Title order={3}>{title}</Title>
      <Text className="review-value">{value}</Text>
      <Text size="sm" c="dimmed">{body}</Text>
    </Card>
  );
}

function TimelineBoard({ series, state, setState }: {
  series: Series[];
  state: UiState;
  setState: React.Dispatch<React.SetStateAction<UiState>>;
}) {
  const labSeries = series.filter((item) => item.kind === 'lab');
  const contextSeries = series.filter((item) => item.kind === 'context');
  const scale = effectiveScale(state, series.length);
  const groups = categoryGroups(labSeries);
  const chartCount = state.mode === 'overlay' ? Math.min(series.length, 16) : series.length;

  return (
    <Stack gap="lg">
      <Paper p="lg" radius="xl" className="timeline-head board-card">
        <Group justify="space-between" align="flex-start">
          <div>
            <Title order={3}>{state.category === 'All categories' ? 'All domains' : state.category} · {state.mode}</Title>
            <Text size="sm" c="dimmed">{chartCount.toLocaleString()} plotted series · scale {scaleLabel(scale)} · pending rows stay out of plots.</Text>
          </div>
          <Group gap="xs">
            <Badge variant="light">{state.agg === 'mean-date' ? 'mean/date' : 'observed'}</Badge>
            <Badge color="green" variant="light">reference bands when parseable</Badge>
            {contextSeries.length ? <Badge color="yellow" variant="light">{contextSeries.length} context overlays</Badge> : null}
          </Group>
        </Group>
      </Paper>

      {state.mode === 'overlay' ? (
        <OverlayChart series={series.slice(0, 16)} state={state} />
      ) : (
        <Stack gap="lg">
          {contextSeries.length ? (
            <Paper p="md" radius="xl" className="category-section">
              <Group justify="space-between" mb="sm"><Title order={4}>Context overlays</Title><Badge color="yellow" variant="light">weight / wearables</Badge></Group>
              <SimpleGrid cols={{ base: 1, xl: 2 }} spacing="md">
                {contextSeries.map((item) => <SeriesCard key={item.id} series={item} state={state} />)}
              </SimpleGrid>
            </Paper>
          ) : null}

          {state.category === 'All categories' ? (
            <Accordion multiple defaultValue={[...groups.keys()].slice(0, 4)} variant="separated" radius="xl" className="category-accordion">
              {[...groups.entries()].map(([category, list]) => (
                <Accordion.Item key={category} value={category}>
                  <Accordion.Control>
                    <Group justify="space-between" pr="md"><Text fw={900}>{category}</Text><Badge variant="light">{list.length} charts</Badge></Group>
                  </Accordion.Control>
                  <Accordion.Panel>
                    <SimpleGrid cols={{ base: 1, xl: 2 }} spacing="md">
                      {list.map((item) => <SeriesCard key={item.id} series={item} state={state} />)}
                    </SimpleGrid>
                  </Accordion.Panel>
                </Accordion.Item>
              ))}
            </Accordion>
          ) : (
            <SimpleGrid cols={{ base: 1, xl: 2 }} spacing="md">
              {labSeries.map((item) => <SeriesCard key={item.id} series={item} state={state} />)}
            </SimpleGrid>
          )}
        </Stack>
      )}

      {!series.length ? (
        <Paper p="xl" radius="xl" className="empty-card">
          <Title order={3}>No numeric chart series</Title>
          <Text c="dimmed">Try All categories, a wider time range, or clearing search.</Text>
          <Button mt="md" onClick={() => setState((current) => ({ ...current, range: 'all', category: 'All categories', query: '' }))}>Reset filters</Button>
        </Paper>
      ) : null}
    </Stack>
  );
}

function SeriesCard({ series, state }: { series: Series; state: UiState }) {
  const prepared = prepareSeries(series, state, effectiveScale(state, 1));
  const flags = series.points.filter((point) => point.flagRaw).length;
  const latest = series.points.at(-1);
  return (
    <Card p="md" radius="xl" className="chart-card">
      <Group justify="space-between" align="flex-start" mb="xs">
        <div className="chart-title-wrap">
          <Group gap="xs">
            <Title order={4} className="chart-title">{series.label}</Title>
            {series.derived ? <Badge color="violet" variant="light" data-tag="DERIVED" title="DERIVED">{tagLabel('DERIVED')}</Badge> : null}
            {series.kind === 'context' ? <Badge color="yellow" variant="light" data-tag="WEARABLE_CONTEXT" title="WEARABLE_CONTEXT">{tagLabel('WEARABLE_CONTEXT')}</Badge> : null}
          </Group>
          <Text size="xs" c="dimmed">{series.category} · {series.points.length} points · latest {latest ? `${latest.date} ${formatValue(latest.rawValue, series.unit)}` : '—'} · {series.ref?.label || 'range missing'}</Text>
        </div>
        {flags ? <Badge color="red" variant="light">{flags} flags</Badge> : <Badge color="gray" variant="light">clean</Badge>}
      </Group>
      <ChartCanvas series={prepared} state={state} />
    </Card>
  );
}

function OverlayChart({ series, state }: { series: Series[]; state: UiState }) {
  const scale = effectiveScale(state, series.length);
  const prepared = series.map((item) => prepareSeries(item, state, scale));
  const data = overlayData(prepared);
  return (
    <Card p="md" radius="xl" className="chart-card overlay-card">
      <Group justify="space-between" align="flex-start" mb="sm">
        <div>
          <Title order={3}>Overlay comparison</Title>
          <Text size="sm" c="dimmed">Different units are converted by the selected scale. First 16 series shown for readability.</Text>
        </div>
        <Badge variant="light">{scaleLabel(scale)}</Badge>
      </Group>
      <div className="overlay-legend">
        {prepared.map((item) => <span key={item.id}><i style={{ background: item.color }} />{item.shortLabel}</span>)}
      </div>
      <div className="chart-frame tall">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 16, right: 20, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.35} />
            <XAxis dataKey="date" tickFormatter={compactDate} minTickGap={24} />
            <YAxis width={54} tick={{ fontSize: 12 }} />
            <Tooltip content={<OverlayTooltip series={prepared} />} />
            {prepared.map((item) => (
              <Line key={item.id} type="monotone" dataKey={item.id} name={item.shortLabel} connectNulls dot={false} stroke={item.color} strokeWidth={2.2} isAnimationActive={false} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

function ChartCanvas({ series, state }: { series: Series; state: UiState }) {
  const data = series.points;
  const rawScale = effectiveScale(state, 1) === 'raw';
  const [minY, maxY] = yDomain(data, series.ref, rawScale);
  const ref = series.ref;
  return (
    <div className="chart-frame">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 10, right: 18, left: 2, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.35} />
          {rawScale && ref && ref.low !== null && ref.high !== null ? (
            <ReferenceArea y1={ref.low ?? undefined} y2={ref.high ?? undefined} fill="var(--range-band)" fillOpacity={0.45} />
          ) : null}
          {rawScale && ref?.high !== null && ref?.high !== undefined ? <ReferenceLine y={ref.high} stroke="var(--range-line)" strokeDasharray="6 5" /> : null}
          {rawScale && ref?.low !== null && ref?.low !== undefined ? <ReferenceLine y={ref.low} stroke="var(--range-line)" strokeDasharray="6 5" /> : null}
          <XAxis dataKey="date" tickFormatter={compactDate} minTickGap={24} />
          <YAxis domain={[minY, maxY]} width={50} tick={{ fontSize: 12 }} tickFormatter={(value) => compactNumber(Number(value))} />
          <Tooltip content={<PointTooltip series={series} />} />
          <Line
            type="monotone"
            dataKey="plotValue"
            connectNulls
            dot={(props) => <FlagDot {...props} showFlags={state.showFlags} color={series.color} />}
            activeDot={{ r: 5, strokeWidth: 2 }}
            stroke={series.color}
            strokeWidth={2.5}
            isAnimationActive={false}
          >
            {state.showLabels ? <LabelList dataKey="date" position="top" formatter={(value) => shortDay(String(value || ''))} className="date-label" /> : null}
          </Line>
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function SourcesTable({ rows, totalRows, rowFocus, setState }: {
  rows: LabPoint[];
  totalRows: number;
  rowFocus: RowFocus;
  setState: React.Dispatch<React.SetStateAction<UiState>>;
}) {
  const visible = [...rows].sort((a, b) => b.time - a.time).slice(0, 400);
  return (
    <Paper p="lg" radius="xl" className="board-card source-table-card">
      <Group justify="space-between" align="flex-start" mb="md">
        <div>
          <Title order={3}>Source rows</Title>
          <Text size="sm" c="dimmed">{visible.length.toLocaleString()} shown of {totalRows.toLocaleString()} matching rows. Pending rows are source evidence, not chart dots.</Text>
        </div>
        <SegmentedControl
          data={[{ value: 'all', label: 'All' }, { value: 'flags', label: 'Flags' }, { value: 'pending', label: 'Pending' }, { value: 'numeric', label: 'Numeric' }]}
          value={rowFocus}
          onChange={(value) => setState((current) => ({ ...current, rowFocus: value as RowFocus }))}
        />
      </Group>
      <Table.ScrollContainer minWidth={980}>
        <Table className="source-table" verticalSpacing="sm" highlightOnHover>
          <Table.Thead><Table.Tr><Table.Th>Date</Table.Th><Table.Th>Domain</Table.Th><Table.Th>Marker</Table.Th><Table.Th>Result</Table.Th><Table.Th>Reference</Table.Th><Table.Th>Flag</Table.Th><Table.Th>Source</Table.Th></Table.Tr></Table.Thead>
          <Table.Tbody>
            {visible.map((row) => <SourceTableRow key={row.id} row={row} />)}
            {!visible.length ? <Table.Tr><Table.Td colSpan={7}><Text c="dimmed" ta="center" py="xl">No source rows in this focus.</Text></Table.Td></Table.Tr> : null}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
    </Paper>
  );
}

function SourceTableRow({ row }: { row: LabPoint }) {
  const report = REPORTS.get(row.sourceId);
  const sourceNote = String(report?.source_note_path || row.sourceNotePath || '');
  const sourceCell = sourceNote ? <a href={sourceNote} target="_blank" rel="noreferrer">source note</a> : truncate(row.sourceId, 36);
  return (
    <Table.Tr>
      <Table.Td><Text fw={700}>{row.date}</Text></Table.Td>
      <Table.Td>{row.category}</Table.Td>
      <Table.Td><Group gap="xs"><Text fw={700}>{row.marker}</Text>{row.derived ? <Badge size="xs" color="violet" data-tag="DERIVED" title="DERIVED">{tagLabel('DERIVED')}</Badge> : null}</Group></Table.Td>
      <Table.Td><Text ff="monospace">{row.valueRaw || (row.value !== null ? formatValue(row.value, row.unit) : '—')}</Text></Table.Td>
      <Table.Td><Text size="sm" c="dimmed">{row.refRaw || '—'}</Text></Table.Td>
      <Table.Td>{row.pending ? <Badge color="orange">pending</Badge> : row.flagRaw ? <Badge color="red">{row.flagRaw}</Badge> : <Badge color="green" variant="light">ok</Badge>}</Table.Td>
      <Table.Td>{sourceCell}</Table.Td>
    </Table.Tr>
  );
}

function SourceMiniRow({ row }: { row: LabPoint }) {
  return (
    <Group justify="space-between" className="mini-row" wrap="nowrap">
      <div>
        <Text fw={800}>{row.marker} <Text span c="dimmed" fw={500}>· {row.category}</Text></Text>
        <Text size="xs" c="dimmed">{row.date} · {row.refRaw || 'range missing'}</Text>
      </div>
      <Group gap="xs" wrap="nowrap">
        <Text ff="monospace" fw={800}>{row.valueRaw || formatValue(row.value || 0, row.unit)}</Text>
        {row.pending ? <Badge color="orange">pending</Badge> : row.flagRaw ? <Badge color="red">{row.flagRaw}</Badge> : null}
      </Group>
    </Group>
  );
}

function FlagDot(props: any & { showFlags: boolean; color: string }) {
  const { cx, cy, payload, showFlags, color } = props;
  if (cx == null || cy == null) return null;
  const flagged = showFlags && payload?.flagRaw;
  return <circle cx={cx} cy={cy} r={flagged ? 5 : 4} fill="var(--paper)" stroke={flagged ? 'var(--flag)' : color} strokeWidth={flagged ? 3 : 2.2} />;
}

type TooltipProps = { active?: boolean; payload?: any[]; label?: unknown };

function PointTooltip({ active, payload, label, series }: TooltipProps & { series: Series }) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload as ChartPoint;
  return (
    <div className="chart-tooltip">
      <Text fw={900}>{series.label}</Text>
      <Text size="sm">{String(label || '')}: <b>{formatValue(point.rawValue, series.unit)}</b></Text>
      {point.valueRaw && point.valueRaw !== String(point.rawValue) ? <Text size="xs" c="dimmed">source: {point.valueRaw}</Text> : null}
      {point.refRaw ? <Text size="xs" c="dimmed">ref: {point.refRaw}</Text> : null}
      {point.flagRaw ? <Badge color="red" size="xs">{point.flagRaw}</Badge> : null}
    </div>
  );
}

function OverlayTooltip({ active, payload, label, series }: TooltipProps & { series: Series[] }) {
  if (!active || !payload?.length) return null;
  const byId = new Map(series.map((item) => [item.id, item]));
  return (
    <div className="chart-tooltip overlay-tip">
      <Text fw={900}>{String(label || '')}</Text>
      {payload.slice(0, 10).map((entry: any) => {
        const item = byId.get(entry.dataKey);
        if (!item || entry.value == null) return null;
        return <Text key={entry.dataKey} size="sm"><i style={{ background: item.color }} />{item.shortLabel}: <b>{compactNumber(Number(entry.value))}</b></Text>;
      })}
    </div>
  );
}

function normalizeLab(row: RawObservation): LabPoint | null {
  const profileId = clean(row.profile_id);
  if (!profileId || !isSafeAlias(profileId)) return null;
  const date = clean(row.observation_date) || clean(row.collection_date) || clean(row.report_date);
  const time = parseDate(date);
  if (!date || !Number.isFinite(time)) return null;
  const valueRaw = clean(row.value_raw);
  const numeric = parseNumber(row.numeric_value);
  const resultText = `${row.result_type || ''} ${valueRaw} ${row.interpretation_en || ''}`;
  const pending = /pending|pendiente|not resulted|in process|en proceso|cancelled/i.test(resultText);
  const panel = clean(row.panel_en) || clean(row.panel_original) || 'Other';
  const marker = clean(row.analyte_en) || clean(row.analyte_original) || 'Unknown marker';
  const report = REPORTS.get(clean(row.source_id));
  return {
    id: clean(row.observation_id) || slug(`${profileId}-${date}-${marker}-${clean(row.source_id)}-${valueRaw}`),
    profileId,
    familyRole: clean(row.family_role),
    date,
    time,
    sourceId: clean(row.source_id),
    sourceTitle: clean(row.source_title),
    panel,
    category: canonicalCategory(panel, marker),
    marker,
    unit: clean(row.unit_raw) || clean(row.ucum_unit),
    valueRaw,
    value: numeric,
    resultType: clean(row.result_type),
    refRaw: clean(row.reference_range_raw),
    flagRaw: normalizeFlag(row.flag_raw),
    interpretation: clean(row.interpretation_en),
    specimen: clean(row.specimen),
    method: clean(row.method),
    confidence: clean(row.confidence),
    notes: clean(row.notes),
    pending,
    derived: /^derived|derived|ratio|index/i.test(marker) || /DERIVED/i.test(`${row.notes || ''} ${row.source_id || ''}`),
    sourceNotePath: clean(report?.source_note_path),
  };
}

function normalizeWearable(row: RawWearable): WearablePoint | null {
  const profileId = clean(row.profile_id);
  const date = clean(row.date);
  const time = parseDate(date);
  if (!profileId || !isSafeAlias(profileId) || !date || !Number.isFinite(time)) return null;
  const aggregation = clean(row.aggregation_preferred) || 'average';
  const value = wearableValue(row, aggregation);
  if (!Number.isFinite(value)) return null;
  return {
    id: `${profileId}-${date}-${clean(row.metric_en)}`,
    profileId,
    familyRole: clean(row.family_role),
    date,
    time,
    category: clean(row.category) || 'Wearables',
    metric: clean(row.metric_en) || clean(row.record_type) || 'Wearable metric',
    unit: clean(row.unit),
    value,
    aggregation,
  };
}

function wearableValue(row: RawWearable, aggregation: string): number {
  const preferred = aggregation.toLowerCase();
  if (preferred.includes('sum')) return parseNumber(row.value_sum) ?? NaN;
  if (preferred.includes('duration')) return parseNumber(row.duration_seconds) ?? parseNumber(row.value_sum) ?? NaN;
  if (preferred.includes('last')) return parseNumber(row.value_last) ?? NaN;
  return parseNumber(row.value_avg) ?? parseNumber(row.value_last) ?? parseNumber(row.value_sum) ?? NaN;
}

function filterLabs(rows: LabPoint[], state: UiState): LabPoint[] {
  const latest = Math.max(...rows.map((row) => row.time).filter(Number.isFinite), 0);
  const start = rangeStart(latest, state.range);
  const query = state.query.trim().toLowerCase();
  return rows.filter((row) => {
    if (start && row.time < start) return false;
    if (state.category !== 'All categories' && row.category !== state.category) return false;
    if (query && !`${row.marker} ${row.panel} ${row.category} ${row.valueRaw} ${row.sourceId}`.toLowerCase().includes(query)) return false;
    return true;
  });
}

function buildLabSeries(rows: LabPoint[]): Series[] {
  const groups = new Map<string, LabPoint[]>();
  rows.filter((row) => row.value !== null && !row.pending).forEach((row) => {
    const key = `${row.category}::${row.marker}::${row.unit}`;
    groups.set(key, [...(groups.get(key) || []), row]);
  });
  let idx = 0;
  return [...groups.entries()].map(([key, list]) => {
    const [category, marker, unit] = key.split('::');
    const sorted = list.sort((a, b) => a.time - b.time);
    const ref = bestReference(sorted.map((row) => row.refRaw));
    const color = PALETTE[idx++ % PALETTE.length];
    return {
      id: slug(key),
      label: `${marker}${unit ? ` (${unit})` : ''}`,
      shortLabel: marker.length > 22 ? `${marker.slice(0, 22)}…` : marker,
      category,
      unit,
      kind: 'lab' as const,
      color,
      points: sorted.map((row) => ({
        id: row.id,
        date: row.date,
        time: row.time,
        value: row.value as number,
        rawValue: row.value as number,
        valueRaw: row.valueRaw,
        flagRaw: row.flagRaw,
        pending: row.pending,
        sourceId: row.sourceId,
        refRaw: row.refRaw,
      })),
      ref,
      derived: sorted.some((row) => row.derived),
    };
  });
}

function buildContextSeries(wearableRows: WearablePoint[], labRows: LabPoint[], state: UiState): Series[] {
  const selected = new Set(state.contextMetrics);
  if (!selected.size) return [];
  const start = rangeStart(Math.max(...labRows.filter((row) => row.profileId === state.profile).map((row) => row.time), ...wearableRows.filter((row) => row.profileId === state.profile).map((row) => row.time), 0), state.range);
  const series: Series[] = [];
  if (selected.has('Weight')) {
    const labWeight = labRows.filter((row) => row.profileId === state.profile && row.value !== null && /weight|body mass/i.test(row.marker));
    const wearableWeight = wearableRows.filter((row) => row.profileId === state.profile && /body mass|weight/i.test(row.metric));
    const points = [
      ...labWeight.map((row) => ({ id: row.id, date: row.date, time: row.time, value: row.value as number, rawValue: row.value as number, valueRaw: row.valueRaw, flagRaw: row.flagRaw, refRaw: row.refRaw })),
      ...wearableWeight.map((row) => ({ id: row.id, date: row.date, time: row.time, value: row.value, rawValue: row.value, valueRaw: String(row.value), flagRaw: '', note: 'wearable body mass' })),
    ].filter((point) => !start || point.time >= start).sort((a, b) => a.time - b.time);
    if (points.length) series.push({ id: 'context-weight', label: 'Weight context (kg)', shortLabel: 'Weight', category: 'Context', unit: 'kg', kind: 'context', color: CONTEXT_COLOR, points, ref: null, derived: false });
  }
  const remaining = [...selected].filter((metric) => metric !== 'Weight');
  remaining.forEach((metric, index) => {
    const points = wearableRows
      .filter((row) => row.profileId === state.profile && row.metric === metric)
      .filter((row) => !start || row.time >= start)
      .sort((a, b) => a.time - b.time)
      .map((row) => ({ id: row.id, date: row.date, time: row.time, value: row.value, rawValue: row.value, valueRaw: String(row.value), flagRaw: '', note: `${row.aggregation} wearable metric` }));
    if (!points.length) return;
    const unit = wearableRows.find((row) => row.profileId === state.profile && row.metric === metric)?.unit || '';
    series.push({ id: `context-${slug(metric)}`, label: `${metric}${unit ? ` (${unit})` : ''}`, shortLabel: metric, category: 'Context', unit, kind: 'context', color: PALETTE[(index + 2) % PALETTE.length], points, ref: null, derived: false });
  });
  return series;
}

function prepareSeries(series: Series, state: UiState, scale: ScaleMode): Series {
  const aggregated = state.agg === 'mean-date' ? meanByDate(series.points) : [...series.points];
  const transformed = transformPoints(aggregated, scale);
  const smoothed = smoothPoints(transformed, state.smoothing);
  return { ...series, points: smoothed };
}

function transformPoints(points: ChartPoint[], scale: ScaleMode): ChartPoint[] {
  const values = points.map((point) => point.value).filter(Number.isFinite);
  if (!values.length) return points;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  const first = values[0] || 1;
  const sd = Math.sqrt(values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / values.length) || 1;
  return points.map((point) => {
    let plotValue = point.value;
    if (scale === 'norm') plotValue = max === min ? 50 : ((point.value - min) / (max - min)) * 100;
    if (scale === 'center') plotValue = point.value - mean;
    if (scale === 'pctmean') plotValue = mean ? (point.value / mean) * 100 : point.value;
    if (scale === 'pctfirst') plotValue = first ? ((point.value - first) / first) * 100 : point.value;
    if (scale === 'z') plotValue = (point.value - mean) / sd;
    if (scale === 'log') plotValue = point.value > 0 ? Math.log10(point.value) : 0;
    return { ...point, plotValue, label: point.date };
  });
}

function meanByDate(points: ChartPoint[]): ChartPoint[] {
  const groups = new Map<string, ChartPoint[]>();
  points.forEach((point) => groups.set(point.date, [...(groups.get(point.date) || []), point]));
  return [...groups.entries()].map(([date, list]) => {
    const avg = list.reduce((sum, point) => sum + point.value, 0) / list.length;
    const first = list[0];
    return { ...first, id: `${first.id}-mean-${date}`, value: avg, rawValue: avg, valueRaw: `${compactNumber(avg)} mean`, flagRaw: list.find((point) => point.flagRaw)?.flagRaw || '' };
  }).sort((a, b) => a.time - b.time);
}

function smoothPoints(points: ChartPoint[], smoothing: string): ChartPoint[] {
  const windowSize = smoothing === 'mean3' ? 3 : smoothing === 'mean7' ? 7 : smoothing === 'mean30' ? 30 : 1;
  if (windowSize <= 1) return points;
  return points.map((point, index) => {
    const slice = points.slice(Math.max(0, index - windowSize + 1), index + 1);
    const avg = slice.reduce((sum, item) => sum + Number(item.plotValue ?? item.value), 0) / slice.length;
    return { ...point, plotValue: avg };
  });
}

function overlayData(series: Series[]): Record<string, string | number | null>[] {
  const dates = new Map<string, Record<string, string | number | null>>();
  series.forEach((item) => {
    item.points.forEach((point) => {
      const row = dates.get(point.date) || { date: point.date };
      row[item.id] = point.plotValue ?? point.value;
      dates.set(point.date, row);
    });
  });
  return [...dates.values()].sort((a, b) => parseDate(String(a.date)) - parseDate(String(b.date)));
}

function effectiveScale(state: UiState, seriesCount: number): ScaleMode {
  if (state.scale !== 'auto') return state.scale;
  return state.mode === 'overlay' || seriesCount > 1 ? 'norm' : 'raw';
}

function focusRows(rows: LabPoint[], focus: RowFocus): LabPoint[] {
  if (focus === 'flags') return rows.filter((row) => row.flagRaw && !row.pending);
  if (focus === 'pending') return rows.filter((row) => row.pending);
  if (focus === 'numeric') return rows.filter((row) => row.value !== null && !row.pending);
  return rows;
}

function buildProfiles(labRows: LabPoint[], wearableRows: WearablePoint[]): ComboboxItem[] {
  const ids = new Set<string>();
  (DATA.profiles || []).forEach((profile) => profile.profile_id && ids.add(profile.profile_id));
  labRows.forEach((row) => ids.add(row.profileId));
  wearableRows.forEach((row) => ids.add(row.profileId));
  Object.keys(DATA.profile_context || {}).forEach((id) => ids.add(id));
  if (!ids.size) ['rod', 'cara'].forEach((id) => ids.add(id));
  return [...ids].filter(isSafeAlias).sort((a, b) => profileRank(a) - profileRank(b) || a.localeCompare(b)).map((id) => ({ value: id, label: displayAlias(id) }));
}

function buildCategoryOptions(rows: LabPoint[]): ComboboxItem[] {
  const categories = [...new Set(rows.map((row) => row.category))].sort((a, b) => categoryRank(a) - categoryRank(b) || a.localeCompare(b));
  return [{ value: 'All categories', label: 'All categories' }, ...categories.map((category) => ({ value: category, label: category }))];
}

function contextMetricOptions(wearableRows: WearablePoint[], profileId: string): ComboboxItem[] {
  const metrics = [...new Set(wearableRows.filter((row) => row.profileId === profileId).map((row) => row.metric))]
    .sort((a, b) => contextRank(a) - contextRank(b) || a.localeCompare(b));
  const options = [{ value: 'Weight', label: 'Weight context' }, ...metrics.filter((metric) => !/body mass|weight/i.test(metric)).map((metric) => ({ value: metric, label: metric }))];
  return options;
}

function categoryGroups(series: Series[]): Map<string, Series[]> {
  const groups = new Map<string, Series[]>();
  series.forEach((item) => {
    const key = item.category;
    groups.set(key, [...(groups.get(key) || []), item]);
  });
  return new Map([...groups.entries()].sort(([a], [b]) => categoryRank(a) - categoryRank(b) || a.localeCompare(b)));
}

function rangeStart(latestTime: number, range: TimeRange): number | null {
  if (!latestTime || range === 'all') return null;
  const latest = new Date(latestTime);
  if (range === 'ytd') return new Date(latest.getFullYear(), 0, 1).getTime();
  const days = range === '30d' ? 30 : range === '90d' ? 90 : 548;
  return latestTime - days * 86400000;
}

function canonicalCategory(panel: string, marker = ''): string {
  const text = `${panel} ${marker}`.toLowerCase();
  if (/mercury|lead|arsenic|cadmium|heavy metal/.test(text)) return 'Heavy metals';
  if (/bilirubin|albumin|globulin|protein total|alkaline|gamma|ggt|ast|alt|liver|hepatic/.test(text)) return 'Liver';
  if (/cholesterol|triglyceride|ldl|hdl|apob|lipoprotein|lipid/.test(text)) return 'Lipids';
  if (/cbc|hemogram|hematology|hemoglobin|hematocrit|platelet|neutrophil|lymphocyte|monocyte|eosinophil|basophil|rbc|wbc|mcv|mch/.test(text)) return 'CBC / Hematology';
  if (/testosterone|estradiol|progesterone|hormone|cortisol|dhea|hcg/.test(text)) return 'Hormones';
  if (/thyroid|tsh|t3|t4/.test(text)) return 'Thyroid';
  if (/kidney|renal|creatinine|urea|bun|uric|egfr|microalbumin/.test(text)) return 'Kidney / urate';
  if (/glucose|a1c|insulin|glyc/.test(text)) return 'Glycemia';
  if (/iron|ferritin|b12|folate|vitamin|mineral|nutrition/.test(text)) return 'Nutrition';
  if (/urinalysis|urine|uro/.test(text)) return 'Urinalysis';
  if (/weight|height|bmi|blood pressure|pulse|vital/.test(text)) return 'Vitals';
  if (/crp|sedimentation|inflammation|immune|immunology/.test(text)) return 'Inflammation / immune';
  if (/stool|gi|gastro|calprotectin/.test(text)) return 'GI / stool';
  return panel || 'Other';
}

function bestReference(raws: string[]): RangeBand | null {
  const parsed = raws.map(parseReference).find((range) => range && (range.low !== null || range.high !== null));
  return parsed || null;
}

function parseReference(raw: string): RangeBand | null {
  const text = clean(raw).replace(',', '.');
  if (!text) return null;
  const range = text.match(/(-?\d+(?:\.\d+)?)\s*(?:-|–|to)\s*(-?\d+(?:\.\d+)?)/i);
  if (range) return { low: Number(range[1]), high: Number(range[2]), label: text };
  const upper = text.match(/(?:<|≤|<=|up to|less than)\s*(-?\d+(?:\.\d+)?)/i);
  if (upper) return { low: null, high: Number(upper[1]), label: text };
  const lower = text.match(/(?:>|≥|>=|more than)\s*(-?\d+(?:\.\d+)?)/i);
  if (lower) return { low: Number(lower[1]), high: null, label: text };
  return null;
}

function yDomain(points: ChartPoint[], ref: RangeBand | null, rawScale: boolean): [number | 'auto', number | 'auto'] {
  const values = points.map((point) => point.plotValue ?? point.value).filter(Number.isFinite);
  if (!values.length) return ['auto', 'auto'];
  if (rawScale && ref) {
    if (ref.low !== null) values.push(ref.low);
    if (ref.high !== null) values.push(ref.high);
  }
  let min = Math.min(...values);
  let max = Math.max(...values);
  if (min === max) {
    min -= Math.abs(min || 1) * 0.15;
    max += Math.abs(max || 1) * 0.15;
  }
  const pad = (max - min) * 0.12;
  return [Math.min(0, min - pad), max + pad];
}

function initialState(profiles: ComboboxItem[]): UiState {
  const params = new URLSearchParams(location.search);
  const category = params.get('category') || 'All categories';
  const context = params.get('context');
  return {
    profile: params.get('profile') || profiles[0]?.value || 'rod',
    range: (params.get('range') as TimeRange) || 'all',
    category,
    section: (params.get('section') as SectionId) || 'review',
    mode: (params.get('mode') as TimelineMode) || 'stack',
    scale: (params.get('scale') as ScaleMode) || 'auto',
    agg: (params.get('agg') as AggMode) || 'observed',
    smoothing: params.get('smooth') || 'none',
    rowFocus: (params.get('rows') as RowFocus) || 'all',
    query: params.get('q') || '',
    contextMetrics: context ? context.split(',').filter(Boolean) : ['Weight'],
    showFlags: params.get('flags') !== '0',
    showLabels: params.get('labels') === '1',
    theme: (params.get('theme') as ThemeMode) || (localStorage.getItem('health-v3-theme') as ThemeMode) || 'light',
  };
}

function persistState(state: UiState) {
  const params = new URLSearchParams();
  params.set('profile', state.profile);
  params.set('range', state.range);
  params.set('category', state.category);
  params.set('section', state.section);
  params.set('mode', state.mode);
  if (state.scale !== 'auto') params.set('scale', state.scale);
  if (state.agg !== 'observed') params.set('agg', state.agg);
  if (state.smoothing !== 'none') params.set('smooth', state.smoothing);
  if (state.rowFocus !== 'all') params.set('rows', state.rowFocus);
  if (state.query) params.set('q', state.query);
  if (state.contextMetrics.length) params.set('context', state.contextMetrics.join(','));
  if (!state.showFlags) params.set('flags', '0');
  if (state.showLabels) params.set('labels', '1');
  if (state.theme === 'dark') params.set('theme', state.theme);
  const next = `${location.pathname}?${params.toString()}`;
  history.replaceState(null, '', next);
  localStorage.setItem('health-v3-theme', state.theme);
}

function downloadCsv(rows: LabPoint[]) {
  const cols = ['date', 'category', 'marker', 'valueRaw', 'unit', 'refRaw', 'flagRaw', 'sourceId'];
  const body = [cols.join(',')].concat(rows.map((row) => cols.map((key) => csvEscape(String((row as any)[key] ?? ''))).join(','))).join('\n');
  const blob = new Blob([body], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'llm-health-filtered-observations.csv';
  link.click();
  URL.revokeObjectURL(url);
}

function countBy<T>(items: T[], fn: (item: T) => string): Map<string, number> {
  const map = new Map<string, number>();
  items.forEach((item) => map.set(fn(item), (map.get(fn(item)) || 0) + 1));
  return map;
}

function summarizeMarkers(rows: LabPoint[]): string {
  return [...new Set(rows.map((row) => row.marker))].slice(0, 4).join(', ') || '—';
}

function latestDate(rows: LabPoint[]): string | null {
  return rows.map((row) => row.date).sort().at(-1) || null;
}

function seriesSort(a: Series, b: Series): number {
  return categoryRank(a.category) - categoryRank(b.category) || a.shortLabel.localeCompare(b.shortLabel);
}

function categoryRank(category: string): number {
  const order = ['Heavy metals', 'Liver', 'Lipids', 'Glycemia', 'CBC / Hematology', 'Kidney / urate', 'Hormones', 'Thyroid', 'Nutrition', 'Vitals', 'Context'];
  const idx = order.indexOf(category);
  return idx === -1 ? 99 : idx;
}

function contextRank(metric: string): number {
  const order = ['Body mass', 'Step count', 'Active energy burned', 'Sleep analysis', 'Resting heart rate', 'Heart rate', 'Walking/running distance'];
  const idx = order.findIndex((item) => metric.toLowerCase().includes(item.toLowerCase()));
  return idx === -1 ? 99 : idx;
}

function profileRank(id: string): number {
  return id === 'rod' ? 0 : id === 'cara' ? 1 : 10;
}

function displayAlias(id: string): string {
  return id ? id[0].toUpperCase() + id.slice(1) : 'Profile';
}

function tagLabel(tag: string): string {
  return TAG_LABELS[tag] || tag.toLowerCase().replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

function clean(value: unknown): string {
  return String(value ?? '').trim();
}

function parseNumber(value: unknown): number | null {
  const text = clean(value).replace(',', '.');
  if (!text) return null;
  const match = text.match(/-?\d+(?:\.\d+)?(?:e[+-]?\d+)?/i);
  if (!match) return null;
  const n = Number(match[0]);
  return Number.isFinite(n) ? n : null;
}

function parseDate(value: string): number {
  return Date.parse(`${value.slice(0, 10)}T00:00:00`);
}

function normalizeFlag(value: unknown): string {
  const text = clean(value);
  if (!text || /^normal$/i.test(text)) return '';
  return text;
}

function isSafeAlias(value: string): boolean {
  return /^[a-z][a-z0-9_-]{1,31}$/.test(value);
}

function slug(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 80) || 'series';
}

function formatValue(value: number, unit: string): string {
  return `${compactNumber(value)}${unit ? ` ${unit}` : ''}`;
}

function compactNumber(value: number): string {
  if (!Number.isFinite(value)) return '—';
  if (Math.abs(value) >= 100000) return value.toExponential(2);
  if (Math.abs(value) >= 1000) return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (Math.abs(value) >= 10) return value.toLocaleString(undefined, { maximumFractionDigits: 1 });
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function compactDate(value: string): string {
  const date = new Date(`${String(value).slice(0, 10)}T00:00:00`);
  if (!Number.isFinite(date.getTime())) return String(value);
  return date.toLocaleDateString(undefined, { month: 'short', year: '2-digit' });
}

function shortDay(value: string): string {
  const date = new Date(`${String(value).slice(0, 10)}T00:00:00`);
  if (!Number.isFinite(date.getTime())) return String(value);
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function scaleLabel(scale: ScaleMode): string {
  return SCALE_OPTIONS.find((option) => option.value === scale)?.label || scale;
}

function truncate(value: string, max: number): string {
  return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}

function csvEscape(value: string): string {
  return /[",\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

createRoot(document.getElementById('root')!).render(<App />);
