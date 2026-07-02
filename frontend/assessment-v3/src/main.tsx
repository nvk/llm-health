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
  Modal,
  Paper,
  ScrollArea,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Tabs,
  Text,
  Textarea,
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
  IconDna2,
  IconDownload,
  IconExternalLink,
  IconFlag,
  IconHome2,
  IconMail,
  IconMoon,
  IconSearch,
  IconSun,
  IconTimeline,
  IconUser,
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
type SectionId = 'profile' | 'review' | 'genomics' | 'timeline' | 'sources';
type TimeRange = 'all' | '30d' | '90d' | 'ytd' | '18mo';
type TimelineMode = 'stack' | 'overlay';
type ScaleMode = 'auto' | 'raw' | 'norm' | 'center' | 'pctmean' | 'pctfirst' | 'z' | 'log';
type AggMode = 'observed' | 'mean-date';
type RowFocus = 'all' | 'flags' | 'resolved' | 'pending' | 'numeric' | 'qa';
type OverlayPreset = 'smart' | 'current' | 'flagged' | 'recent' | 'core' | 'context';
type FlagStatus = 'none' | 'active' | 'resolved';
type PendingStatus = 'none' | 'active' | 'superseded';
type InterviewMode = 'baseline' | 'followup' | 'family-history' | 'ask-parents';

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

type ProfileArtifact = {
  kind?: string;
  date?: string;
  title?: string;
  status?: string;
  summary?: string;
  tags?: string[];
  evidence?: string;
  profile_id?: string;
  relative_id?: string;
  related_profile_ids?: string[];
  relation?: string;
  degree?: number | null;
  lineage?: string;
  shared_household?: boolean | null;
  priority?: number | null;
  gap_type?: string;
  candidate_tests?: string[];
  context_questions?: string[];
  lenses?: string[];
  onset_age?: number | null;
};

type SourceVaultSummary = {
  count?: number;
  copied?: number;
  unmatched?: number;
  types?: Record<string, number>;
  first_date?: string;
  latest_date?: string;
};

type ProfileContextPayload = Record<string, unknown> & {
  contextNotes?: ProfileArtifact[];
  specialistNotes?: ProfileArtifact[];
  hereditaryRisks?: ProfileArtifact[];
  familyRelationships?: ProfileArtifact[];
  familyHistory?: ProfileArtifact[];
  quickReviewCards?: ProfileArtifact[];
  diagnosticGaps?: ProfileArtifact[];
  researchJobs?: ProfileArtifact[];
  sourceVault?: SourceVaultSummary;
  genomicsSummary?: GenomicsSummaryPayload;
};

type GenomicsSummaryPayload = {
  source_count?: number;
  marker_count?: number;
  card_count?: number;
  lead?: string;
  tags?: string[];
};

type PatientSummaryPayload = {
  lead?: string;
  bullets?: string[];
  tags?: string[];
};

type GenomicsSourcePayload = {
  profile_id?: string;
  source_id?: string;
  source_kind?: string;
  assay_type?: string;
  genome_build?: string;
  marker_count?: number;
  called_count?: number;
  no_call_count?: number;
  duplicate_marker_count?: number;
  stored_variant_scope?: string;
  stored_variant_count?: number;
  clinical_grade?: boolean;
  call_rate?: number;
  tags?: string[];
  imported_at?: string;
};

type GenomicsQcDetail = {
  code?: string;
  label?: string;
};

type GenomicsQcPayload = {
  profile_id?: string;
  source_id?: string;
  marker_count?: number;
  called_count?: number;
  no_call_count?: number;
  duplicate_marker_count?: number;
  call_rate?: number;
  warnings?: string[];
  warning_details?: GenomicsQcDetail[];
  generated_on?: string;
};

type GenomicCardPayload = {
  inference_id?: string;
  profile_id?: string;
  finding_type?: string;
  title?: string;
  summary?: string;
  patient_summary?: string;
  evidence?: string[];
  source_ids?: string[];
  variant_ids?: string[];
  related_observation_ids?: string[];
  required_confirmation?: boolean;
  discussion_target?: string;
  confidence?: string;
  status?: string;
  tags?: string[];
  created_at?: string;
};

type GenomicsReviewPayload = {
  profile_id?: string;
  sources?: {
    count?: number;
    variant_count?: number;
    sources?: GenomicsSourcePayload[];
  };
  qc?: {
    count?: number;
    qc?: GenomicsQcPayload[];
  };
  crossrefs?: {
    count?: number;
    cards?: GenomicCardPayload[];
  };
  patient_summary?: PatientSummaryPayload;
  notice?: string;
};

type HealthPayload = {
  generated?: string;
  source?: string;
  observations?: RawObservation[];
  normalization_issues?: Record<string, unknown>[];
  reports?: RawReport[];
  wearable_daily?: RawWearable[];
  profile_context?: Record<string, Record<string, unknown>>;
  genomics?: Record<string, GenomicsReviewPayload>;
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
  flagStatus: FlagStatus;
  resolvedByDate?: string;
  resolvedByValue?: string;
  resolvedById?: string;
  interpretation: string;
  specimen: string;
  method: string;
  confidence: string;
  notes: string;
  normalizationStatus: string;
  normalizationApplied: string;
  normalizationWarnings: string;
  pending: boolean;
  pendingStatus: PendingStatus;
  supersededByDate?: string;
  supersededByValue?: string;
  supersededById?: string;
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
  flagStatus: FlagStatus;
  resolvedByDate?: string;
  resolvedByValue?: string;
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
  overlayPreset: OverlayPreset;
  rowFocus: RowFocus;
  query: string;
  contextMetrics: string[];
  showFlags: boolean;
  showLabels: boolean;
  theme: ThemeMode;
};

const DATA = window.HEALTH_ASSESSMENT_V2 || {};
const REPORTS = new Map((DATA.reports || []).map((report) => [String(report.source_id || ''), report]));
const NORMALIZATION_ISSUES = DATA.normalization_issues || [];
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
const OVERLAY_OPTIONS: ComboboxItem[] = [
  { value: 'smart', label: 'Smart overlay' },
  { value: 'current', label: 'Current domain' },
  { value: 'flagged', label: 'Source-note first' },
  { value: 'recent', label: 'Recent movement' },
  { value: 'core', label: 'Core markers' },
  { value: 'context', label: 'Context only' },
];
const OVERLAY_LIMIT = 12;
const PALETTE = ['#2f6fb2', '#2f855a', '#b7791f', '#805ad5', '#d94670', '#0891b2', '#b64035', '#64748b', '#14b8a6', '#f97316'];
const CONTEXT_COLOR = '#a36a00';
const TAG_LABELS: Record<string, string> = {
  OBSERVED: 'Observed',
  DERIVED: 'Derived',
  WEARABLE_CONTEXT: 'Wearable context',
  CONTEXT: 'Context',
  INFERENCE: 'Inference',
  DATA_GAP: 'Data gap',
  QA_ISSUE: 'QA note',
  TEST_CANDIDATE: 'Test candidate',
  PROTOCOL_REVIEW: 'Protocol review',
  SPECIALIST_NOTE: 'Specialist note',
  FAMILY_HISTORY: 'Family history',
  HEREDITARY_RISK: 'Hereditary risk',
  FAMILY_PATTERN: 'Family pattern',
  CONFIRM_FIRST: 'Confirm first',
};

function App() {
  const labRows = useMemo(
    () => markSupersededPending(
      markResolvedFlags((DATA.observations || []).map(normalizeLab).filter(Boolean) as LabPoint[]),
    ),
    [],
  );
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
  const profileContext = useMemo(() => currentProfileContext(state.profile), [state.profile]);
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
              <Group gap="xs" mb={4}><Badge color="yellow" variant="light">LOCAL</Badge><Text size="xs" fw={700}>Review workspace</Text></Group>
              <Text size="xs" c="dimmed">Private source review and follow-up planning. Verify sources before decisions.</Text>
            </Paper>

            <ScrollArea className="controls-scroll" type="auto">
              <Stack gap="md" pr="xs">
                <Select
                  label="Profile"
                  className="profile-switch"
                  data={profileOptions}
                  value={state.profile}
                  onChange={(value) => update({ profile: value || profileOptions[0]?.value || 'rod', section: 'profile' })}
                  searchable
                  allowDeselect={false}
                  leftSection={<IconUser size={16} />}
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
                  onChange={(value) => {
                    const mode = value as TimelineMode;
                    update({ mode, section: 'timeline', range: mode === 'overlay' && state.range === 'all' ? '18mo' : state.range });
                  }}
                  fullWidth
                />

                <Select
                  label="Overlay group"
                  data={OVERLAY_OPTIONS}
                  value={state.overlayPreset}
                  onChange={(value) => update({ overlayPreset: (value || 'smart') as OverlayPreset, mode: 'overlay', section: 'timeline', range: state.range === 'all' ? '18mo' : state.range })}
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
                  <Checkbox label="Source note rings" checked={state.showFlags} onChange={(event) => update({ showFlags: event.currentTarget.checked })} />
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
              profileContext={profileContext}
              setState={setState}
            />

            <SummaryGrid
              rows={filteredRows}
              series={activeSeries}
              state={state}
              profileContext={profileContext}
              setState={setState}
            />

            <Tabs value={state.section} onChange={(value) => update({ section: (value || 'review') as SectionId })} className="main-tabs">
              <Tabs.List>
                <Tabs.Tab value="profile" leftSection={<IconHome2 size={16} />}>Home</Tabs.Tab>
                <Tabs.Tab value="review" leftSection={<IconClipboardList size={16} />}>Review</Tabs.Tab>
                <Tabs.Tab value="genomics" leftSection={<IconDna2 size={16} />}>Genomics</Tabs.Tab>
                <Tabs.Tab value="timeline" leftSection={<IconTimeline size={16} />}>Timeline</Tabs.Tab>
                <Tabs.Tab value="sources" leftSection={<IconDatabase size={16} />}>Sources</Tabs.Tab>
              </Tabs.List>

              <Tabs.Panel value="profile" pt="lg">
                <PatientProfileBoard
                  profileId={state.profile}
                  profileOptions={profileOptions}
                  profileContext={profileContext}
                  rows={allProfileRows}
                  wearableRows={wearableRows.filter((row) => row.profileId === state.profile)}
                  setState={setState}
                />
              </Tabs.Panel>

              <Tabs.Panel value="review" pt="lg">
                <ReviewBoard
                  rows={filteredRows}
                  allRows={allProfileRows}
                  series={activeSeries}
                  groups={visibleCategories}
                  state={state}
                  profileContext={profileContext}
                  setState={setState}
                />
              </Tabs.Panel>

              <Tabs.Panel value="genomics" pt="lg">
                <GenomicsBoard
                  profileId={state.profile}
                  genomics={currentGenomics(state.profile)}
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

function Header({ state, rows, allRows, series, profileOptions, profileContext, setState }: {
  state: UiState;
  rows: LabPoint[];
  allRows: LabPoint[];
  series: Series[];
  profileOptions: ComboboxItem[];
  profileContext: ProfileContextPayload;
  setState: React.Dispatch<React.SetStateAction<UiState>>;
}) {
  const profile = profileOptions.find((option) => option.value === state.profile)?.label || displayAlias(state.profile);
  const latest = latestDate(rows);
  const totalLatest = latestDate(allRows);
  const flagged = activeFlagRows(rows).length;
  const resolved = resolvedFlagRows(rows).length;
  const pending = activePendingRows(rows).length;
  const qa = rows.filter((row) => row.normalizationWarnings || row.normalizationApplied).length;
  const qaWarnings = rows.filter((row) => row.normalizationWarnings).length;
  const contextCount = profileArtifactCount(profileContext);
  const sourceVaultCount = sourceVaultCountFor(profileContext);
  const genomics = currentGenomics(state.profile);
  const genomicCards = genomicsCardCount(genomics);
  const genomicMarkers = genomicsMarkerCount(genomics);
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
            Clean charts, source rows, context overlays, genomics review cards, and source notes from local de-identified data.
          </Text>
        </div>
        <Group gap="xs">
          <MantineTooltip label="Open genotype import / matching">
            <Button component="a" href={genomicsUiHref(state.profile)} target="_blank" rel="noreferrer" variant="light" leftSection={<IconDna2 size={16} />}>Genomics import</Button>
          </MantineTooltip>
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
        <MetricPill label={`${flagged.toLocaleString()} active notes`} icon={<IconFlag size={15} />} tone={flagged ? 'warn' : 'ok'} onClick={() => setState((current) => ({ ...current, section: 'sources', rowFocus: flagged ? 'flags' : 'all' }))} />
        {resolved ? <MetricPill label={`${resolved.toLocaleString()} resolved`} icon={<IconTimeline size={15} />} tone="ok" onClick={() => setState((current) => ({ ...current, section: 'sources', rowFocus: 'resolved' }))} /> : null}
        <MetricPill label={`${pending.toLocaleString()} pending`} icon={<IconAlertTriangle size={15} />} tone={pending ? 'bad' : 'ok'} onClick={() => setState((current) => ({ ...current, section: 'sources', rowFocus: pending ? 'pending' : 'all' }))} />
        {qa ? <MetricPill label={`${qa.toLocaleString()} normalized`} icon={<IconDatabase size={15} />} tone={qaWarnings ? 'warn' : 'ok'} onClick={() => setState((current) => ({ ...current, section: 'sources', rowFocus: 'qa' }))} /> : null}
        {contextCount ? <MetricPill label={`${contextCount.toLocaleString()} context notes`} icon={<IconClipboardList size={15} />} tone="warn" onClick={() => setState((current) => ({ ...current, section: 'profile' }))} /> : null}
        {sourceVaultCount ? <MetricPill label={`${sourceVaultCount.toLocaleString()} vaulted sources`} icon={<IconDatabase size={15} />} tone="warn" onClick={() => setState((current) => ({ ...current, section: 'profile' }))} /> : null}
        {genomics ? <MetricPill label={`${genomicCards || genomicMarkers} genomic ${genomicCards ? 'cards' : 'markers'}`} icon={<IconDna2 size={15} />} tone={genomicCards ? 'warn' : 'default'} onClick={() => setState((current) => ({ ...current, section: 'genomics' }))} /> : null}
        <MetricPill label={`latest ${latest || totalLatest || '—'}`} icon={<IconTimeline size={15} />} />
      </Group>
    </Paper>
  );
}

function MetricPill({ label, icon, tone = 'default', onClick }: { label: string; icon: React.ReactNode; tone?: 'default' | 'warn' | 'bad' | 'ok'; onClick?: () => void }) {
  return <button type="button" className={`metric-pill ${tone}`} onClick={onClick}>{icon}<span>{label}</span></button>;
}

function PatientProfileBoard({ profileId, profileOptions, profileContext, rows, wearableRows, setState }: {
  profileId: string;
  profileOptions: ComboboxItem[];
  profileContext: ProfileContextPayload;
  rows: LabPoint[];
  wearableRows: WearablePoint[];
  setState: React.Dispatch<React.SetStateAction<UiState>>;
}) {
  const profile = (DATA.profiles || []).find((item) => item.profile_id === profileId);
  const label = profileOptions.find((item) => item.value === profileId)?.label || displayAlias(profileId);
  const contextNotes = safeArtifacts(profileContext.contextNotes);
  const familyRelationships = safeArtifacts(profileContext.familyRelationships);
  const familyHistory = safeArtifacts(profileContext.familyHistory);
  const hereditaryRisks = safeArtifacts(profileContext.hereditaryRisks);
  const specialistNotes = safeArtifacts(profileContext.specialistNotes);
  const genomics = currentGenomics(profileId);
  const genomicsSummary = profileContext.genomicsSummary;
  const gaps = safeArtifacts(profileContext.diagnosticGaps);
  const reviewCards = safeArtifacts(profileContext.quickReviewCards);
  const researchJobs = safeArtifacts(profileContext.researchJobs);
  const artifacts = profileArtifacts(profileContext);
  const flags = activeFlagRows(rows);
  const pending = activePendingRows(rows);
  const resolved = resolvedFlagRows(rows);
  const qa = rows.filter((row) => row.normalizationWarnings || row.normalizationApplied);
  const domains = [...new Set(rows.map((row) => row.category))].sort((a, b) => categoryRank(a) - categoryRank(b) || a.localeCompare(b));
  const wearableMetrics = [...new Set(wearableRows.map((row) => row.metric))].sort((a, b) => contextRank(a) - contextRank(b) || a.localeCompare(b));
  const timeline = patientHistoryItems(profileId, rows, profileContext).slice(0, 40);
  const dataRange = dateSpan(rows.map((row) => row.date));
  const wearableRange = dateSpan(wearableRows.map((row) => row.date));
  const birth = profileBirthLabel(profile);
  const age = approximateAge(profile);
  const showAllProfileRows = { range: 'all' as TimeRange, category: 'All categories' };
  const [interviewOpen, setInterviewOpen] = useState(false);
  const [interviewMode, setInterviewMode] = useState<InterviewMode>('baseline');
  const [copiedInterview, setCopiedInterview] = useState(false);
  const interviewText = useMemo(() => buildInterviewText({
    mode: interviewMode,
    profileId,
    profile,
    rows,
    wearableRows,
    profileContext,
  }), [interviewMode, profileId, profile, rows, wearableRows, profileContext]);
  const copyInterview = () => {
    navigator.clipboard?.writeText(interviewText);
    setCopiedInterview(true);
    window.setTimeout(() => setCopiedInterview(false), 1600);
  };

  return (
    <>
    <Stack gap="lg">
      <SimpleGrid cols={{ base: 1, lg: 3 }} spacing="md">
        <Card p="lg" radius="xl" className="stat-card profile-overview-card">
          <Text size="xs" fw={800} c="dimmed" tt="uppercase" lts={1}>Patient profile</Text>
          <Title order={2}>{label}</Title>
          <Stack gap={4} mt="sm">
            <ProfileFact label="Alias" value={profileId} />
            <ProfileFact label="Role" value={clean(profile?.role) || 'not set'} />
            <ProfileFact label="Birth" value={birth} />
            <ProfileFact label="Approx age" value={age ? `~${age}` : 'unknown'} />
          </Stack>
          <Button mt="md" variant="light" leftSection={<IconMail size={16} />} onClick={() => setInterviewOpen(true)}>
            Draft interview
          </Button>
        </Card>

        <Card p="lg" radius="xl" className="stat-card">
          <Text size="xs" fw={800} c="dimmed" tt="uppercase" lts={1}>Data coverage</Text>
          <Title order={2}>{rows.length.toLocaleString()}</Title>
          <Text size="sm" c="dimmed">lab/source rows · {domains.length || 0} domains</Text>
          <Divider my="sm" />
          <ProfileFact label="Lab range" value={dataRange || 'no numeric lab rows'} />
          <ProfileFact label="Wearables" value={wearableRows.length ? `${wearableRows.length.toLocaleString()} rows · ${wearableMetrics.length} metrics` : 'none'} />
          <ProfileFact label="Wearable range" value={wearableRange || '—'} />
          {domains.length ? (
            <Group gap={5} mt="xs">
              {domains.slice(0, 8).map((domain) => <Badge key={domain} size="xs" variant="light" color="gray">{domain}</Badge>)}
              {domains.length > 8 ? <Badge size="xs" variant="light" color="gray">+{domains.length - 8}</Badge> : null}
            </Group>
          ) : null}
        </Card>

        <Card p="lg" radius="xl" className="stat-card">
          <Text size="xs" fw={800} c="dimmed" tt="uppercase" lts={1}>Review state</Text>
          <Title order={2}>{profileArtifactCount(profileContext).toLocaleString()}</Title>
          <Text size="sm" c="dimmed">profile/context artifacts</Text>
          <Divider my="sm" />
          <ProfileFact label="Active source notes" value={`${flags.length}`} tone={flags.length ? 'bad' : 'ok'} />
          <ProfileFact label="Pending rows" value={`${pending.length}`} tone={pending.length ? 'warn' : 'ok'} />
          <ProfileFact label="Open gaps" value={`${gaps.length}`} tone={gaps.length ? 'warn' : 'ok'} />
          <ProfileFact label="Genomic markers" value={`${genomicsMarkerCount(genomics) || genomicsSummary?.marker_count || 0}`} />
          <ProfileFact label="Vaulted sources" value={`${sourceVaultCountFor(profileContext)}`} />
        </Card>
      </SimpleGrid>

      <SimpleGrid cols={{ base: 1, xl: 2 }} spacing="md">
        <Paper p="lg" radius="xl" className="board-card profile-section">
          <Group justify="space-between" mb="md">
            <div>
              <Title order={3}>What to know first</Title>
              <Text size="sm" c="dimmed">Compact profile facts, active concerns, and context-only records.</Text>
            </div>
            <Badge variant="light">{artifacts.length} notes</Badge>
          </Group>
          <Stack gap="xs">
            {sourceVaultCountFor(profileContext) ? <SourceVaultSummaryRow summary={profileContext.sourceVault} /> : null}
            {genomics ? <PriorityRow title="Genomic review" detail={genomicsSummaryLine(genomics)} tag="INFERENCE" onClick={() => setState((current) => ({ ...current, section: 'genomics' }))} /> : null}
            {flags.length ? <PriorityRow title="Active source notes" detail={summarizeMarkers(flags)} tag="QA_ISSUE" onClick={() => setState((current) => ({ ...current, ...showAllProfileRows, section: 'sources', rowFocus: 'flags' }))} /> : null}
            {pending.length ? <PriorityRow title="Pending / nonnumeric rows" detail={summarizeMarkers(pending)} tag="DATA_GAP" onClick={() => setState((current) => ({ ...current, ...showAllProfileRows, section: 'sources', rowFocus: 'pending' }))} /> : null}
            {qa.length ? <PriorityRow title="Normalization notes" detail={`${qa.length} row(s) have translated/normalized display fields`} tag="QA_ISSUE" onClick={() => setState((current) => ({ ...current, ...showAllProfileRows, section: 'sources', rowFocus: 'qa' }))} /> : null}
            {gaps.slice(0, 4).map((gap) => <PriorityRow key={`${gap.title}-${gap.date}`} title={gap.title || 'Diagnostic gap'} detail={gapDetail(gap)} tag="DATA_GAP" />)}
            {!sourceVaultCountFor(profileContext) && !genomics && !flags.length && !pending.length && !qa.length && !gaps.length ? (
              <Text c="dimmed">No active source notes or gaps in this profile filter.</Text>
            ) : null}
          </Stack>
        </Paper>

        <Paper p="lg" radius="xl" className="board-card profile-section">
          <Group justify="space-between" mb="md">
            <div>
              <Title order={3}>Family & hereditary context</Title>
              <Text size="sm" c="dimmed">Relationship graph and family-history clues for follow-up planning.</Text>
            </div>
            <Badge color={familyHistory.length || hereditaryRisks.length ? 'yellow' : 'gray'} variant="light">{familyRelationships.length} relations</Badge>
          </Group>
          <Stack gap="xs">
            {familyRelationships.slice(0, 8).map((rel, index) => <FamilyRelationshipRow key={`${rel.profile_id}-${rel.relative_id}-${index}`} profileId={profileId} relationship={rel} />)}
            {familyHistory.slice(0, 6).map((item, index) => <ContextMiniCard key={`fh-${item.title}-${index}`} artifact={{ ...item, kind: 'family_history' }} />)}
            {hereditaryRisks.slice(0, 4).map((item, index) => <ContextMiniCard key={`hr-${item.title}-${index}`} artifact={item} />)}
            {!familyRelationships.length && !familyHistory.length && !hereditaryRisks.length ? <Text c="dimmed">No family/history context recorded yet.</Text> : null}
          </Stack>
        </Paper>
      </SimpleGrid>

      <SimpleGrid cols={{ base: 1, xl: 2 }} spacing="md">
        <Paper p="lg" radius="xl" className="board-card profile-section">
          <Group justify="space-between" mb="md">
            <div>
              <Title order={3}>History timeline</Title>
              <Text size="sm" c="dimmed">Labs, context records, family-history events, gaps, consults, and source-vault milestones.</Text>
            </div>
            <Badge variant="light">{timeline.length} events</Badge>
          </Group>
          <Stack gap="xs" className="profile-timeline">
            {timeline.map((item, index) => <ProfileTimelineRow key={`${item.date}-${item.title}-${index}`} item={item} />)}
            {!timeline.length ? <Text c="dimmed">No timeline entries yet.</Text> : null}
          </Stack>
        </Paper>

        <Paper p="lg" radius="xl" className="board-card profile-section">
          <Group justify="space-between" mb="md">
            <div>
              <Title order={3}>Notes, consults, research</Title>
              <Text size="sm" c="dimmed">Most useful narrative artifacts for understanding the patient quickly.</Text>
            </div>
            <Group gap="xs">
              {specialistNotes.length ? <Badge color="yellow" variant="light">{specialistNotes.length} consults</Badge> : null}
              {researchJobs.length ? <Badge color="blue" variant="light">{researchJobs.length} research</Badge> : null}
            </Group>
          </Group>
          <Stack gap="sm">
            {[...contextNotes, ...reviewCards, ...specialistNotes, ...researchJobs].slice(0, 12).map((artifact, index) => <ContextMiniCard key={`${artifact.kind}-${artifact.title}-${index}`} artifact={artifact} />)}
            {!contextNotes.length && !reviewCards.length && !specialistNotes.length && !researchJobs.length ? <Text c="dimmed">No narrative artifacts recorded yet.</Text> : null}
          </Stack>
        </Paper>
      </SimpleGrid>
    </Stack>
    <Modal
      opened={interviewOpen}
      onClose={() => setInterviewOpen(false)}
      title="Copyable profile interview"
      size="xl"
      centered
    >
      <Stack gap="md">
        <Text size="sm" c="dimmed">
          Draft text you can copy into email or chat. Review before sending; avoid sending IDs,
          full birth dates, raw source files, or anything you do not want in email.
        </Text>
        <SegmentedControl
          data={[
            { value: 'baseline', label: 'Baseline intake' },
            { value: 'followup', label: 'Follow-up gaps' },
            { value: 'family-history', label: 'Family history' },
            { value: 'ask-parents', label: 'Ask parents' },
          ]}
          value={interviewMode}
          onChange={(value) => setInterviewMode(value as InterviewMode)}
          fullWidth
        />
        <Textarea
          className="interview-textarea"
          value={interviewText}
          minRows={20}
          maxRows={32}
          autosize
          readOnly
        />
        <Group justify="space-between">
          <Text size="xs" c="dimmed">Alias-only local draft · not medical advice</Text>
          <Group gap="xs">
            <Button variant="light" onClick={() => setInterviewOpen(false)}>Close</Button>
            <Button onClick={copyInterview}>{copiedInterview ? 'Copied' : 'Copy questionnaire'}</Button>
          </Group>
        </Group>
      </Stack>
    </Modal>
    </>
  );
}

function ProfileFact({ label, value, tone = 'default' }: { label: string; value: string; tone?: 'default' | 'warn' | 'bad' | 'ok' }) {
  return (
    <Group justify="space-between" gap="md" className={`profile-fact ${tone}`} wrap="nowrap">
      <Text size="sm" c="dimmed">{label}</Text>
      <Text size="sm" fw={800} ta="right">{value || '—'}</Text>
    </Group>
  );
}

function PriorityRow({ title, detail, tag, onClick }: { title: string; detail: string; tag: string; onClick?: () => void }) {
  return (
    <button type="button" className="priority-row" onClick={onClick}>
      <Badge size="xs" className={`tag tag-${tag.toLowerCase()}`} data-tag={tag} title={tag}>{tagLabel(tag)}</Badge>
      <div>
        <Text fw={900}>{title}</Text>
        <Text size="sm" c="dimmed" lineClamp={2}>{detail}</Text>
      </div>
    </button>
  );
}

function gapDetail(gap: ProfileArtifact): string {
  if (gap.candidate_tests?.length) return `Candidate tests: ${gap.candidate_tests.slice(0, 4).join(', ')}`;
  if (gap.context_questions?.length) return `Questions: ${gap.context_questions.slice(0, 3).join(' · ')}`;
  return gap.summary || gap.status || 'Needs context';
}

function SourceVaultSummaryRow({ summary }: { summary?: SourceVaultSummary }) {
  if (!summary?.count) return null;
  const typeText = Object.entries(summary.types || {}).map(([type, count]) => `${count} ${type}`).join(', ');
  const dateText = dateSpan([summary.first_date || '', summary.latest_date || '']);
  return (
    <div className="priority-row static">
      <Badge size="xs" color="gray" variant="light">Sources</Badge>
      <div>
        <Text fw={900}>Private source vault</Text>
        <Text size="sm" c="dimmed">{summary.count} source(s){summary.copied ? ` · ${summary.copied} copied` : ''}{summary.unmatched ? ` · ${summary.unmatched} unmatched` : ''}{typeText ? ` · ${typeText}` : ''}{dateText ? ` · catalog ${dateText}` : ''}</Text>
      </div>
    </div>
  );
}

function FamilyRelationshipRow({ profileId, relationship }: { profileId: string; relationship: ProfileArtifact }) {
  const other = profileId === relationship.profile_id ? relationship.relative_id : relationship.profile_id;
  const relation = profileId === relationship.profile_id ? relationship.relation : reverseRelation(relationship.relation || '');
  return (
    <div className="mini-row">
      <Group justify="space-between" wrap="nowrap">
        <div>
          <Text fw={900}>{displayAlias(other || '')}</Text>
          <Text size="xs" c="dimmed">{relation || 'relative'}{relationship.lineage ? ` · ${relationship.lineage}` : ''}{relationship.degree ? ` · degree ${relationship.degree}` : ''}</Text>
        </div>
        <Badge className="tag tag-family_history" size="xs">{tagLabel('FAMILY_HISTORY')}</Badge>
      </Group>
    </div>
  );
}

function ProfileTimelineRow({ item }: { item: ProfileArtifact }) {
  const tag = primaryTag(item.tags);
  return (
    <div className="timeline-row">
      <div className="timeline-date">{item.date || '—'}</div>
      <div className="timeline-dot" />
      <div className="timeline-body">
        <Group gap="xs" mb={3}>
          <Badge size="xs" className={`tag tag-${tag.toLowerCase()}`} data-tag={tag} title={tag}>{tagLabel(tag)}</Badge>
          {item.status ? <Text size="xs" c="dimmed">{item.status}</Text> : null}
        </Group>
        <Text fw={900}>{item.title || artifactKindLabel(item.kind)}</Text>
        {item.summary ? <Text size="sm" c="dimmed" lineClamp={3}>{item.summary}</Text> : null}
      </div>
    </div>
  );
}

function buildInterviewText({ mode, profileId, profile, rows, wearableRows, profileContext }: {
  mode: InterviewMode;
  profileId: string;
  profile?: ProfilePayload;
  rows: LabPoint[];
  wearableRows: WearablePoint[];
  profileContext: ProfileContextPayload;
}): string {
  const alias = displayAlias(profileId);
  const domains = topDomains(rows);
  const flags = activeFlagRows(rows);
  const pending = activePendingRows(rows);
  const gaps = safeArtifacts(profileContext.diagnosticGaps);
  const familyRelationships = safeArtifacts(profileContext.familyRelationships);
  const familyHistory = safeArtifacts(profileContext.familyHistory);
  const contextNotes = safeArtifacts(profileContext.contextNotes);
  const wearableMetrics = [...new Set(wearableRows.map((row) => row.metric))]
    .sort((a, b) => contextRank(a) - contextRank(b) || a.localeCompare(b));
  const sourceVault = sourceVaultCountFor(profileContext);
  const coverage = [
    `Profile alias in our private local tracker: ${alias}`,
    `Birth precision currently stored: ${profileBirthLabel(profile)}; please confirm year/month only if wrong.`,
    rows.length
      ? `Local data coverage: ${rows.length.toLocaleString()} lab/source rows from ${dateSpan(rows.map((row) => row.date))}.`
      : 'Local data coverage: no chartable lab rows yet.',
    domains.length ? `Areas currently represented: ${domains.join(', ')}.` : '',
    wearableRows.length
      ? `Wearable/context rows: ${wearableRows.length.toLocaleString()} rows; main metrics: ${wearableMetrics.slice(0, 6).join(', ')}.`
      : 'Wearable/context rows: none yet.',
    sourceVault ? `Private source catalog: ${sourceVault} file(s) cataloged locally.` : '',
  ].filter(Boolean);
  const gapQuestions = gaps.flatMap((gap) => gap.context_questions || []).slice(0, 10);
  const candidateChecks = gaps.flatMap((gap) => gap.candidate_tests || []).slice(0, 8);
  const subject = mode === 'ask-parents'
    ? `Subject: Family health timeline questions from ${alias}`
    : mode === 'family-history'
      ? `Subject: Family health history questions for ${alias}`
      : mode === 'followup'
        ? `Subject: Follow-up health profile questions for ${alias}`
        : `Subject: Quick health profile interview for ${alias}`;

  const intro = [
    subject,
    '',
    'Hi [name],',
    '',
    `We are improving a private, local health profile for ${alias}. Could you reply with as much detail as you remember? Prose is perfect; bullets are fine. Approximate dates are useful, and "unknown" is a valid answer.`,
    '',
    'Please do not send legal IDs, full birth dates, insurance numbers, or anything you do not want in email. If you want to share records or exports, remove identifiers when possible or use a safer channel.',
    '',
    'Current local snapshot:',
    ...coverage.map((line) => `- ${line}`),
    '',
  ];

  if (mode === 'ask-parents') {
    return [
      ...intro,
      'Ask-your-parents hereditary interview',
      '',
      'This is a longer memory questionnaire for parents or older relatives. The goal is not perfect medical paperwork; the goal is to recover family patterns, approximate timelines, and clues that may change what we track.',
      '',
      '1) First, your side of the story',
      '- What major health issues have you had? Include approximate age/year of onset, whether confirmed or suspected, severity, treatment, and what helped or hurt.',
      '- Any surgeries, hospitalizations, ER visits, major injuries, head injuries, dental/jaw issues, infections, long antibiotic courses, transfusions, or unusual recoveries?',
      '- Any current medications, frequent past medications, supplements, hormones, pain relievers, psychiatric meds, blood thinners, seizure meds, or drugs that caused bad reactions?',
      '- Any allergies, anesthesia reactions, medication sensitivities, vaccine/procedure reactions, or unusual bleeding/clotting/bruising?',
      '',
      '2) What do you remember about me / this profile as a child?',
      '- Pregnancy and birth context if known: complications, prematurity, C-section/vaginal, feeding issues, jaundice, infections, antibiotics, hospital stays. Year/month precision is enough; no full birth dates.',
      '- Childhood patterns: ear infections, asthma/allergies/eczema, digestive issues, headaches, injuries, sleep issues, learning/attention, anxiety/mood, recurrent fevers, growth/weight, dental issues.',
      '- Anything that started after a move, infection, medication, vaccine/procedure, injury, dental work, travel, mold/water damage, pet exposure, or diet change?',
      '',
      '3) Map the family tree medically',
      '- For parents, siblings, children, grandparents, aunts/uncles, cousins, and any biologically related relatives: what conditions do you know about?',
      '- For each: relationship, condition, approximate age at onset, confirmed vs suspected, outcome, and whether multiple relatives had similar issues.',
      '- If someone died young or suddenly, what was the suspected cause and approximate age?',
      '',
      '4) High-yield hereditary categories',
      '- Heart/vascular: early heart attack, stroke, aneurysm, high blood pressure, rhythm issues, sudden death, fainting, high cholesterol, clotting or bleeding problems.',
      '- Brain/nerves: dementia, Parkinson-like symptoms, seizures, migraines, psychiatric disease, addiction, neuropathy, hearing loss, vision loss, tremor, unusual movement problems.',
      '- Cancer: type, side of family, age at diagnosis, recurrence, multiple cancers, colon polyps, breast/ovarian/prostate/pancreatic/skin/brain cancers.',
      '- Metabolic/endocrine: diabetes, thyroid, obesity pattern, gout, kidney stones, osteoporosis, infertility, pregnancy losses, early menopause, PCOS-like symptoms.',
      '- Immune/inflammatory: autoimmune disease, celiac/IBD, psoriasis, rheumatoid-like disease, lupus-like disease, chronic infections, severe allergies/asthma/eczema.',
      '- Liver/kidney/GI: jaundice/Gilbert-like history, gallbladder disease, fatty liver, hepatitis, kidney disease, recurrent UTIs, ulcers/reflux, bowel disease.',
      '- Connective tissue: hypermobility, easy bruising, hernias, varicose veins, aneurysms, scoliosis, tendon/ligament tears.',
      '',
      '5) Shared household and exposure clues',
      '- Homes and locations: major moves, water source, wells, old plumbing, mold/water damage, renovations, pesticides, pets, pests, nearby industry/farms, wildfire/smoke exposure.',
      '- Occupations/hobbies in the family: solvents, metals, paint, welding, mining, shooting ranges, ceramics, stained glass, agriculture, salons, healthcare, labs, construction.',
      '- Diet/substances: smoking/secondhand smoke, alcohol patterns, cannabis/other substances, unusual diets, seafood/fish frequency, supplements/remedies, parasites/travel/infections.',
      '',
      '6) Existing clues to verify or correct',
      familyRelationships.length || familyHistory.length
        ? '- Please verify these relationship/history clues from the local profile:'
        : '- We do not have much verified family-history context yet, so your memory is the starting point.',
      ...familyRelationships.slice(0, 10).map((rel) => `  - Relationship clue: ${displayAlias(rel.profile_id || '')} / ${displayAlias(rel.relative_id || '')} (${rel.relation || 'relative'}). Correct?`),
      ...familyHistory.slice(0, 10).map((item) => `  - History clue: ${item.title || 'condition'} (${item.status || 'status unknown'}). What is the accurate version?`),
      '',
      '7) Records or people who would know more',
      '- Are there old lab reports, imaging summaries, discharge papers, medication lists, genetic tests, family trees, death certificates, or relatives who remember details better?',
      '- If sharing files, remove identifiers where possible or use a safer channel than email.',
      '',
      '8) Uncertainty is useful',
      '- Please mark memories as confirmed, suspected, rumor, or unknown. Approximate decade/age is still useful.',
      '- What feels important that this questionnaire did not ask?',
      '',
      'Thank you — this helps us spot hereditary patterns without assuming anyone has a condition just because a relative did.',
    ].join('\n');
  }

  if (mode === 'family-history') {
    return [
      ...intro,
      'Family-history interview',
      '',
      '1) Close relatives',
      '- For parents, siblings, children, grandparents, aunts/uncles, and cousins: what major conditions do you know about?',
      '- For each condition: who had it, approximate age of onset, confirmed vs suspected, severity, and outcome if known.',
      '- Any early deaths, strokes, heart attacks, aneurysms, cancers, dementia, autoimmune disease, psychiatric disease, clotting/bleeding issues, kidney stones, gout, thyroid disease, diabetes, or unusual reactions to medications?',
      '',
      '2) Patterns and shared context',
      '- Do multiple relatives share the same issue, similar age of onset, or similar triggers?',
      '- Did relatives share diet, water, mold, pets, occupations, hobbies, smoking exposure, heavy metals, travel, parasites, infections, or unusual supplement/medication use?',
      '- Any known hereditary diagnoses or genetic test results? Please summarize; no raw identifiers needed.',
      '',
      '3) Household timeline',
      '- Major moves, homes, water source changes, renovations, mold/water damage, pests, pets, occupational exposures, or unusual diet changes.',
      '- Any family-wide illnesses, rashes, gut issues, neurological symptoms, sleep issues, or medication/supplement experiments?',
      '',
      familyRelationships.length || familyHistory.length
        ? 'What we already have as context to verify or correct:'
        : 'We do not have much family-history context yet.',
      ...familyRelationships.slice(0, 8).map((rel) => `- Relationship clue: ${displayAlias(rel.profile_id || '')} / ${displayAlias(rel.relative_id || '')} (${rel.relation || 'relative'}). Is this correct?`),
      ...familyHistory.slice(0, 8).map((item) => `- History clue: ${item.title || 'condition'} (${item.status || 'status unknown'}). What is the best version of this story?`),
      '',
      '4) Anything else',
      '- What feels important that we did not ask?',
      '- What are you uncertain about?',
      '',
      'Thank you — rough memory is much better than no timeline.',
    ].join('\n');
  }

  if (mode === 'followup') {
    return [
      ...intro,
      'Follow-up interview',
      '',
      flags.length ? `Local watch items by marker/category: ${uniqueMarkerList(flags, 10)}.` : 'No active source-note rows are currently showing.',
      pending.length ? `Pending or nonnumeric source rows to reconcile: ${uniqueMarkerList(pending, 10)}.` : 'No active pending rows are currently showing.',
      '',
      '1) Timeline and recent changes',
      '- Since the last labs/records, what changed? Diet, sleep, weight, exercise, travel, illness, stress, work, home, dental work, pets, water, sauna, fasting, alcohol, nicotine, cannabis, other substances?',
      '- Any symptoms that appeared, disappeared, or changed? Include mild symptoms and approximate timing.',
      '- Any medications, antibiotics, pain relievers, antihistamines, hormones, supplements, binders, detox products, or home remedies started/stopped? Include dose/frequency if remembered.',
      '',
      '2) Open questions from the local gap layer',
      ...(gapQuestions.length ? gapQuestions.map((question) => `- ${question}`) : ['- Are any important symptoms, exposures, medications, or family-history clues missing from the profile?']),
      ...(candidateChecks.length ? ['', 'Candidate checks to discuss or confirm:', ...candidateChecks.map((check) => `- ${check}`)] : []),
      '',
      '3) Source QA',
      '- Are any lab dates, specimen types, fasting status, units, or result labels wrong?',
      '- Were any results pending, cancelled, repeated, or corrected later?',
      '- Do you have newer records or wearable exports that would close the timeline gap?',
      '',
      '4) Priorities',
      '- What are the top 3 things you want understood or tracked better?',
      '- What would count as improvement?',
      '',
      'Thank you — please answer in whatever format is easiest.',
    ].join('\n');
  }

  return [
    ...intro,
    'Baseline intake interview',
    '',
    '1) Short health story',
    '- In your own words, tell the health story from childhood to now. Major events, injuries, illnesses, surgeries, dental work, hospitalizations, infections, antibiotics, medications, and what changed afterward.',
    '- What are the top current concerns, even if they feel minor or intermittent?',
    '- What has improved, worsened, or stayed stable over time?',
    '',
    '2) Habits and context',
    '- Typical sleep schedule, light/screens at night, snoring, waking, energy, naps.',
    '- Food pattern, appetite, digestion, bowel pattern, food reactions, fasting, caffeine.',
    '- Movement/exercise, injuries, pain, work posture, travel rhythm.',
    '- Alcohol, nicotine/smoking/vaping, cannabis, recreational drugs, and exposure to secondhand smoke. Include true "none" answers.',
    '- Home/work exposures: water source, mold/water damage, pets, solvents, metals, dust, pesticides, hobbies, occupations, travel.',
    '',
    '3) Medications and supplements',
    '- Current and past medications: name/class, dose if known, start/stop dates, why used, benefits, side effects, and whether stopping changed anything.',
    '- Antibiotics, pain relievers, acid blockers, antihistamines, hormones, steroids, sleep aids, and psychiatric medications are especially useful to timeline.',
    '- Supplements/remedies: brand if useful, dose, timing, what changed, and any bad reactions.',
    '',
    '4) Family history',
    '- Parents, siblings, children, grandparents, aunts/uncles: major conditions, approximate ages, and patterns.',
    '- Anything that seems hereditary, runs in the household, or clusters around a shared exposure?',
    '',
    '5) Records/data that would help',
    '- Recent labs, old labs, imaging summaries, hospital/clinic summaries, medication lists, vaccine/procedure timelines, dental records, wearable exports, weight history, blood pressure, sleep data.',
    '- If sending files, remove identifiers where possible or use a safer channel than email.',
    '',
    contextNotes.length ? 'Context notes we already have; please correct if wrong:' : 'We have very little narrative context yet.',
    ...contextNotes.slice(0, 6).map((note) => `- ${note.title || note.status || 'Context note'}: ${note.summary || 'please verify.'}`),
    '',
    '6) What did we miss?',
    '- Add anything you think could matter, even if it seems weird or unrelated.',
    '- Mark uncertain memories as uncertain; approximate dates are okay.',
    '',
    'Thank you — the goal is a better timeline, not perfect answers.',
  ].join('\n');
}

function topDomains(rows: LabPoint[]): string[] {
  const counts = new Map<string, number>();
  rows.forEach((row) => counts.set(row.category, (counts.get(row.category) || 0) + 1));
  return [...counts.entries()]
    .sort(([a, countA], [b, countB]) => countB - countA || categoryRank(a) - categoryRank(b) || a.localeCompare(b))
    .slice(0, 10)
    .map(([category]) => category);
}

function uniqueMarkerList(rows: LabPoint[], limit: number): string {
  return [...new Set(rows.map((row) => `${row.marker}${row.category ? ` (${row.category})` : ''}`))]
    .slice(0, limit)
    .join(', ');
}

function SummaryGrid({ rows, series, state, profileContext, setState }: {
  rows: LabPoint[];
  series: Series[];
  state: UiState;
  profileContext: ProfileContextPayload;
  setState: React.Dispatch<React.SetStateAction<UiState>>;
}) {
  const numeric = rows.filter((row) => row.value !== null).length;
  const flagged = activeFlagRows(rows).length;
  const resolved = resolvedFlagRows(rows).length;
  const pending = activePendingRows(rows).length;
  const derived = rows.filter((row) => row.derived).length;
  const contextCount = profileArtifactCount(profileContext);
  const vaulted = sourceVaultCountFor(profileContext);
  const genomics = currentGenomics(state.profile);
  const genomicSources = genomicsSourceCount(genomics);
  const genomicMarkers = genomicsMarkerCount(genomics);
  const genomicCards = genomicsCardCount(genomics);
  const cards = [
    { title: 'Evidence points', value: numeric.toLocaleString(), note: `${series.length} plotted series`, icon: IconChartDots3, section: 'timeline' as SectionId },
    ...(contextCount || vaulted ? [{ title: 'Context packet', value: contextCount.toLocaleString(), note: vaulted ? `${vaulted} vaulted source(s)` : 'Records and notes, not chart dots', icon: IconClipboardList, section: 'profile' as SectionId }] : []),
    ...(genomics ? [{ title: 'Genomics', value: (genomicCards || genomicMarkers).toLocaleString(), note: `${genomicSources} source(s) · ${genomicMarkers} markers`, icon: IconDna2, section: 'genomics' as SectionId }] : []),
    { title: 'Source notes', value: flagged.toLocaleString(), note: flagged ? 'Click to review' : resolved ? `${resolved} resolved by later tests` : 'None in filter', icon: IconFlag, section: 'sources' as SectionId, focus: flagged ? 'flags' as RowFocus : resolved ? 'resolved' as RowFocus : 'all' as RowFocus },
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

function GenomicsBoard({ profileId, genomics }: {
  profileId: string;
  genomics: GenomicsReviewPayload | null;
}) {
  if (!genomics) {
    return (
      <Paper p="xl" radius="xl" className="empty-card genomics-empty">
        <Group justify="space-between" align="flex-start" gap="lg">
          <div>
            <Title order={3}>Genomics review</Title>
            <Text c="dimmed" maw={760} mt={6}>
              No rendered genomics review payload is included for {displayAlias(profileId)} yet.
              Import or cross-reference a local genotype file through the genomics pipeline, then refresh this board.
            </Text>
          </div>
          <Button component="a" href={genomicsUiHref(profileId)} target="_blank" rel="noreferrer" leftSection={<IconDna2 size={16} />}>
            Open genomics UI
          </Button>
        </Group>
      </Paper>
    );
  }

  const sources = safeGenomicsSources(genomics);
  const qcRows = safeGenomicsQc(genomics);
  const cards = safeGenomicsCards(genomics);
  const summary = genomics.patient_summary || {};
  const bullets = safeStrings(summary.bullets).slice(0, 4);
  const tags = safeTags(summary.tags);
  const callRates = qcRows.map((row) => numericValue(row.call_rate)).filter((value): value is number => value !== null);
  const bestCallRate = callRates.length ? Math.max(...callRates) : null;
  const lead = clean(summary.lead) || genomicsSummaryLine(genomics);
  const warningNotes = uniqueStrings(qcRows.flatMap((row) => safeStrings(row.warning_details?.map((detail) => detail.label) || row.warnings))).slice(0, 5);

  return (
    <Stack gap="lg" className="genomics-board">
      <Paper p="lg" radius="xl" className="board-card genomics-hero">
        <Group justify="space-between" align="flex-start" gap="lg">
          <div>
            <Group gap="xs" mb="xs">
              <ThemeIcon radius="xl" variant="light"><IconDna2 size={20} /></ThemeIcon>
              <Title order={3}>Genomics review</Title>
            </Group>
            <Text className="genomics-lead">{lead}</Text>
            {bullets.length ? (
              <Stack gap={5} mt="sm">
                {bullets.map((bullet) => <Text key={bullet} size="sm" c="dimmed">• {bullet}</Text>)}
              </Stack>
            ) : null}
          </div>
          <Stack gap="xs" align="flex-end">
            <InlineTags tags={tags.length ? tags : ['CONTEXT', 'CONFIRM_FIRST']} />
            <Button variant="light" component="a" href={genomicsUiHref(profileId)} target="_blank" rel="noreferrer" leftSection={<IconExternalLink size={16} />}>
              Open local genomics UI
            </Button>
          </Stack>
        </Group>
      </Paper>

      <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="md">
        <Card p="lg" radius="xl" className="stat-card">
          <Text size="xs" fw={800} c="dimmed" tt="uppercase" lts={1}>Sources</Text>
          <Title order={2}>{genomicsSourceCount(genomics).toLocaleString()}</Title>
          <Text size="sm" c="dimmed">local genotype source summaries</Text>
        </Card>
        <Card p="lg" radius="xl" className="stat-card">
          <Text size="xs" fw={800} c="dimmed" tt="uppercase" lts={1}>Markers</Text>
          <Title order={2}>{genomicsMarkerCount(genomics).toLocaleString()}</Title>
          <Text size="sm" c="dimmed">saved matched markers for review</Text>
        </Card>
        <Card p="lg" radius="xl" className="stat-card">
          <Text size="xs" fw={800} c="dimmed" tt="uppercase" lts={1}>Review cards</Text>
          <Title order={2}>{genomicsCardCount(genomics).toLocaleString()}</Title>
          <Text size="sm" c="dimmed">pipeline-generated discussion prompts</Text>
        </Card>
        <Card p="lg" radius="xl" className="stat-card">
          <Text size="xs" fw={800} c="dimmed" tt="uppercase" lts={1}>Best call rate</Text>
          <Title order={2}>{bestCallRate === null ? '—' : `${(bestCallRate * 100).toFixed(1)}%`}</Title>
          <Text size="sm" c="dimmed">readable checked spots in the source</Text>
        </Card>
      </SimpleGrid>

      <SimpleGrid cols={{ base: 1, xl: 2 }} spacing="md">
        <Paper p="lg" radius="xl" className="board-card genomics-section">
          <Group justify="space-between" align="flex-start" mb="md">
            <div>
              <Title order={3}>Source and QC summary</Title>
              <Text size="sm" c="dimmed">Rendered source summaries from the local genomics pipeline; raw filenames and dense calls are not shown here.</Text>
            </div>
            <Badge variant="light">{qcRows.length} QC row(s)</Badge>
          </Group>
          <Stack gap="sm">
            {sources.map((source) => {
              const qc = qcRows.find((row) => row.source_id === source.source_id);
              return <GenomicsSourceTile key={source.source_id || `${source.profile_id}-${source.imported_at}`} source={source} qc={qc} />;
            })}
            {!sources.length ? <Text c="dimmed">No source summaries were rendered.</Text> : null}
            {warningNotes.length ? (
              <div className="genomics-note-list">
                <Text fw={900} size="sm">QC notes</Text>
                {warningNotes.map((note) => <Text key={note} size="sm" c="dimmed">• {note}</Text>)}
              </div>
            ) : null}
          </Stack>
        </Paper>

        <Paper p="lg" radius="xl" className="board-card genomics-section">
          <Group justify="space-between" align="flex-start" mb="md">
            <div>
              <Title order={3}>Patient-friendly findings</Title>
              <Text size="sm" c="dimmed">These one-liners come from the genomics review pipeline, not browser heuristics.</Text>
            </div>
            <Badge color={cards.length ? 'yellow' : 'gray'} variant="light">{cards.length} cards</Badge>
          </Group>
          <Stack gap="sm">
            {cards.slice(0, 6).map((card, index) => <GenomicsFindingMini key={card.inference_id || `${card.title}-${index}`} card={card} />)}
            {!cards.length ? <Text c="dimmed">No matched review cards are showing yet.</Text> : null}
          </Stack>
        </Paper>
      </SimpleGrid>

      {cards.length ? (
        <Accordion multiple variant="separated" radius="xl" className="category-accordion genomics-accordion" defaultValue={cards.slice(0, 4).map((card, index) => card.inference_id || `genomics-card-${index}`)}>
          {cards.map((card, index) => {
            const value = card.inference_id || `genomics-card-${index}`;
            const tag = primaryTag(card.tags);
            const evidence = safeStrings(card.evidence).slice(0, 4);
            return (
              <Accordion.Item key={value} value={value}>
                <Accordion.Control>
                  <Group justify="space-between" pr="md" align="flex-start" wrap="nowrap">
                    <div>
                      <Text fw={900}>{clean(card.title) || 'Genomic review card'}</Text>
                      <Text size="sm" c="dimmed" lineClamp={2}>{clean(card.patient_summary) || clean(card.summary) || 'Review prompt generated by the local genomics pipeline.'}</Text>
                    </div>
                    <Group gap="xs" wrap="nowrap">
                      <Badge size="xs" className={`tag tag-${tag.toLowerCase()}`} data-tag={tag} title={tag}>{tagLabel(tag)}</Badge>
                      {card.required_confirmation ? <Badge size="xs" color="yellow" variant="light">confirm first</Badge> : null}
                    </Group>
                  </Group>
                </Accordion.Control>
                <Accordion.Panel>
                  <Stack gap="sm">
                    <Text>{clean(card.patient_summary) || clean(card.summary) || 'Review prompt generated by the local genomics pipeline.'}</Text>
                    {card.summary && card.summary !== card.patient_summary ? <Text size="sm" c="dimmed">{card.summary}</Text> : null}
                    <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="sm">
                      <ProfileFact label="Type" value={clean(card.finding_type) || 'genomic context'} />
                      <ProfileFact label="Confidence" value={clean(card.confidence) || 'review'} />
                      <ProfileFact label="Status" value={clean(card.status) || 'review'} />
                      <ProfileFact label="Discuss with" value={clean(card.discussion_target) || 'clinician'} />
                    </SimpleGrid>
                    {evidence.length ? (
                      <div className="genomics-note-list">
                        <Text fw={900} size="sm">Clinical references / evidence</Text>
                        {evidence.map((item) => <Text key={item} size="sm" c="dimmed">• {item}</Text>)}
                      </div>
                    ) : null}
                    <InlineTags tags={safeTags(card.tags)} />
                  </Stack>
                </Accordion.Panel>
              </Accordion.Item>
            );
          })}
        </Accordion>
      ) : null}
    </Stack>
  );
}

function GenomicsSourceTile({ source, qc }: { source: GenomicsSourcePayload; qc?: GenomicsQcPayload }) {
  const callRate = numericValue(source.call_rate ?? qc?.call_rate);
  const tags = safeTags(source.tags);
  return (
    <div className="genomics-source-tile">
      <Group justify="space-between" align="flex-start" gap="md">
        <div>
          <Text fw={900}>{clean(source.source_id) || 'genotype source'}</Text>
          <Text size="sm" c="dimmed">
            {clean(source.source_kind) || 'source'} · {clean(source.genome_build) || 'build unknown'} · {source.clinical_grade ? 'clinical-grade marked' : 'consumer/local source'}
          </Text>
        </div>
        <InlineTags tags={tags.length ? tags : ['CONTEXT']} />
      </Group>
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="xs" mt="sm">
        <ProfileFact label="Source markers" value={(source.marker_count ?? qc?.marker_count ?? 0).toLocaleString()} />
        <ProfileFact label="Stored matched markers" value={(source.stored_variant_count ?? 0).toLocaleString()} />
        <ProfileFact label="Called / no-call" value={`${(source.called_count ?? qc?.called_count ?? 0).toLocaleString()} / ${(source.no_call_count ?? qc?.no_call_count ?? 0).toLocaleString()}`} />
        <ProfileFact label="Call rate" value={callRate === null ? '—' : `${(callRate * 100).toFixed(1)}%`} />
      </SimpleGrid>
    </div>
  );
}

function GenomicsFindingMini({ card }: { card: GenomicCardPayload }) {
  const tag = primaryTag(card.tags);
  return (
    <div className="context-mini genomics-finding-mini">
      <Group justify="space-between" align="flex-start" mb={4}>
        <Badge size="xs" className={`tag tag-${tag.toLowerCase()}`} data-tag={tag} title={tag}>{tagLabel(tag)}</Badge>
        <Text size="xs" c="dimmed">{clean(card.confidence) || 'review'}</Text>
      </Group>
      <Text fw={900}>{clean(card.title) || 'Genomic finding'}</Text>
      <Text size="sm" c="dimmed" lineClamp={3}>{clean(card.patient_summary) || clean(card.summary) || 'Review prompt generated by the local genomics pipeline.'}</Text>
    </div>
  );
}

function InlineTags({ tags }: { tags: string[] }) {
  const safe = safeTags(tags);
  if (!safe.length) return null;
  return (
    <Group gap={5} justify="flex-end">
      {safe.slice(0, 6).map((tag) => <Badge key={tag} size="xs" className={`tag tag-${tag.toLowerCase()}`} data-tag={tag} title={tag}>{tagLabel(tag)}</Badge>)}
    </Group>
  );
}

function ReviewBoard({ rows, allRows, series, groups, state, profileContext, setState }: {
  rows: LabPoint[];
  allRows: LabPoint[];
  series: Series[];
  groups: Map<string, Series[]>;
  state: UiState;
  profileContext: ProfileContextPayload;
  setState: React.Dispatch<React.SetStateAction<UiState>>;
}) {
  const flagged = activeFlagRows(rows);
  const resolved = resolvedFlagRows(rows);
  const pending = activePendingRows(rows);
  const supersededPending = supersededPendingRows(rows);
  const normalizationRows = rows.filter((row) => row.normalizationWarnings || row.normalizationApplied);
  const normalizationWarnings = rows.filter((row) => row.normalizationWarnings);
  const exportNormalizationIssues = NORMALIZATION_ISSUES.length;
  const recent = [...rows].sort((a, b) => b.time - a.time).slice(0, 8);
  const rowsByCategory = countBy(allRows, (row) => row.category);
  const domainCards = [...groups.entries()].map(([category, list]) => ({ category, count: list.length, flags: list.reduce((sum, s) => sum + flagCount(s), 0), resolved: list.reduce((sum, s) => sum + resolvedFlagCount(s), 0) }));
  const contextArtifacts = profileArtifacts(profileContext);
  const sourceVault = profileContext.sourceVault;

  return (
    <Stack gap="lg">
      <SimpleGrid cols={{ base: 1, md: 4 }} spacing="md">
        <ReviewCard
          title="Needs source audit"
          tag={flagged.length ? 'QA_ISSUE' : 'OBSERVED'}
          value={`${flagged.length} active`}
          body={flagged.length ? summarizeMarkers(flagged) : resolved.length ? `${resolved.length} older source note(s) appear resolved by later follow-up.` : 'No active source notes in this filter.'}
          onClick={() => setState((current) => ({ ...current, section: 'sources', rowFocus: flagged.length ? 'flags' : resolved.length ? 'resolved' : 'all' }))}
        />
        <ReviewCard
          title="Pending / nonnumeric"
          tag={pending.length ? 'DATA_GAP' : 'OBSERVED'}
          value={`${pending.length} rows`}
          body={pending.length ? summarizeMarkers(pending) : supersededPending.length ? `${supersededPending.length} old pending row(s) were matched to later results.` : 'Pending rows are kept in sources and are not plotted.'}
          onClick={() => setState((current) => ({ ...current, section: 'sources', rowFocus: pending.length ? 'pending' : 'all' }))}
        />
        <ReviewCard
          title="Timeline coverage"
          tag="OBSERVED"
          value={`${series.length} series`}
          body={`${state.category}; ${state.range}; latest ${latestDate(rows) || '—'}.`}
          onClick={() => setState((current) => ({ ...current, section: 'timeline' }))}
        />
        <ReviewCard
          title="Normalization notes"
          tag={normalizationWarnings.length ? 'QA_ISSUE' : 'OBSERVED'}
          value={normalizationWarnings.length ? `${normalizationWarnings.length} review` : `${normalizationRows.length} applied`}
          body={normalizationRows.length ? 'English display fields and approved unit conversions are used in charts/tables.' : exportNormalizationIssues ? 'Other filters have normalization notes.' : 'Display language and units already look consistent.'}
          onClick={() => setState((current) => ({ ...current, section: 'sources', rowFocus: normalizationRows.length ? 'qa' : 'all' }))}
        />
      </SimpleGrid>

      {(contextArtifacts.length || sourceVault?.count) ? (
        <Paper p="lg" radius="xl" className="board-card context-card">
          <Group justify="space-between" mb="md">
            <div>
              <Title order={3}>Profile context</Title>
              <Text size="sm" c="dimmed">
                Records, family context, source-vault status, and specialist notes. These are not plotted as numeric dots.
              </Text>
            </div>
            <Group gap="xs">
              {contextArtifacts.length ? <Badge color="yellow" variant="light">{contextArtifacts.length} notes</Badge> : null}
              {sourceVault?.count ? <Badge color="gray" variant="light">{sourceVault.count} vaulted sources</Badge> : null}
            </Group>
          </Group>
          {sourceVault?.count ? (
            <Group className="mini-row" justify="space-between" mb="sm" wrap="nowrap">
              <div>
                <Text fw={900}>Private source vault</Text>
                <Text size="xs" c="dimmed">Raw files are hash-named locally; original filenames/paths are not shown here.</Text>
              </div>
              <Group gap="xs" wrap="nowrap">
                <Badge variant="light">{sourceVault.count} sources</Badge>
                {sourceVault.copied ? <Badge color="green" variant="light">{sourceVault.copied} copied</Badge> : null}
                {sourceVault.unmatched ? <Badge color="orange" variant="light">{sourceVault.unmatched} unmatched</Badge> : null}
              </Group>
            </Group>
          ) : null}
          <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="sm">
            {contextArtifacts.slice(0, 12).map((artifact, index) => <ContextMiniCard key={`${artifact.kind}-${artifact.title}-${artifact.date}-${index}`} artifact={artifact} />)}
          </SimpleGrid>
          {contextArtifacts.length > 12 ? <Text size="xs" c="dimmed" mt="sm">{contextArtifacts.length - 12} more context item(s) hidden in this compact board.</Text> : null}
        </Paper>
      ) : null}

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
              <Text size="sm" c="dimmed">{rowsByCategory.get(domain.category) || 0} observations · {domain.flags} source notes · {domain.resolved} resolved</Text>
            </button>
          ))}
          {!domainCards.length ? (
            <div className="domain-card">
              <Text fw={800}>No numeric lab domains yet</Text>
              <Text size="sm" c="dimmed">This profile currently has context/source records but no chartable observations in the canonical dataset.</Text>
            </div>
          ) : null}
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

function ContextMiniCard({ artifact }: { artifact: ProfileArtifact }) {
  const tag = primaryTag(artifact.tags);
  return (
    <div className="context-mini">
      <Group justify="space-between" align="flex-start" mb={4}>
        <Badge size="xs" className={`tag tag-${tag.toLowerCase()}`} data-tag={tag} title={tag}>{tagLabel(tag)}</Badge>
        <Text size="xs" c="dimmed">{artifact.date || '—'}</Text>
      </Group>
      <Text fw={900}>{artifact.title || artifact.kind || 'Context'}</Text>
      {artifact.status ? <Text size="xs" c="dimmed">{artifact.status}</Text> : null}
      {artifact.summary ? <Text size="sm" lineClamp={3}>{artifact.summary}</Text> : null}
    </div>
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
  const groups = categoryGroups(labSeries);
  const overlay = selectOverlaySeries(series, state);
  const scale = effectiveScale(state, state.mode === 'overlay' ? overlay.series.length : series.length);
  const groupEntries = [...groups.entries()];
  const openGroups = defaultOpenGroups(groupEntries);
  const chartCount = state.mode === 'overlay' ? overlay.series.length : series.length;

  return (
    <Stack gap="lg">
      <Paper p="lg" radius="xl" className="timeline-head board-card">
        <Group justify="space-between" align="flex-start">
          <div>
            <Title order={3}>{state.category === 'All categories' ? 'All domains' : state.category} · {state.mode}</Title>
            <Text size="sm" c="dimmed">
              {chartCount.toLocaleString()} plotted series · scale {scaleLabel(scale)}
              {state.mode === 'overlay' ? ` · ${overlay.note}` : ' · priority groups open first'}
            </Text>
          </div>
          <Group gap="xs">
            <Badge variant="light">{state.agg === 'mean-date' ? 'mean/date' : 'observed'}</Badge>
            {state.mode === 'overlay' ? <Badge color="blue" variant="light">{overlay.badge}</Badge> : null}
            <Badge color="green" variant="light">reference bands when parseable</Badge>
            {contextSeries.length ? <Badge color="yellow" variant="light">{contextSeries.length} context overlays</Badge> : null}
          </Group>
        </Group>
      </Paper>

      {state.mode === 'overlay' ? (
        overlay.series.length ? (
          <OverlayChart series={overlay.series} state={state} title={overlay.title} note={overlay.note} />
        ) : (
          <Paper p="xl" radius="xl" className="empty-card">
            <Title order={3}>No overlay series</Title>
            <Text c="dimmed">Try Smart overlay, a wider time range, or a selected domain with numeric rows.</Text>
            <Button mt="md" onClick={() => setState((current) => ({ ...current, overlayPreset: 'smart', range: 'all' }))}>Reset overlay</Button>
          </Paper>
        )
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
            <Accordion multiple defaultValue={openGroups} key={openGroups.join('|')} variant="separated" radius="xl" className="category-accordion">
              {groupEntries.map(([category, list]) => {
                const stats = groupStats(list);
                return (
                <Accordion.Item key={category} value={category}>
                  <Accordion.Control>
                    <Group justify="space-between" pr="md">
                      <Text fw={900}>{category}</Text>
                      <Group gap="xs">
                        {stats.flags ? <Badge color="red" variant="light">{stats.flags} source notes</Badge> : null}
                        {!stats.flags && stats.resolved ? <Badge color="green" variant="light">{stats.resolved} resolved</Badge> : null}
                        <Badge variant="light">{list.length} charts</Badge>
                        <Badge color="gray" variant="light">latest {stats.latest || '—'}</Badge>
                      </Group>
                    </Group>
                  </Accordion.Control>
                  <Accordion.Panel>
                    <SimpleGrid cols={{ base: 1, xl: 2 }} spacing="md">
                      {list.map((item) => <SeriesCard key={item.id} series={item} state={state} />)}
                    </SimpleGrid>
                  </Accordion.Panel>
                </Accordion.Item>
                );
              })}
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
  const flags = flagCount(series);
  const resolved = resolvedFlagCount(series);
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
        {flags ? <Badge color="red" variant="light">{flags} source notes</Badge> : resolved ? <Badge color="green" variant="light">{resolved} resolved</Badge> : <Badge color="gray" variant="light">clean</Badge>}
      </Group>
      <ChartCanvas series={prepared} state={state} />
    </Card>
  );
}

function OverlayChart({ series, state, title, note }: { series: Series[]; state: UiState; title: string; note: string }) {
  const scale = effectiveScale(state, series.length);
  const prepared = series.map((item) => prepareSeries(item, state, scale));
  const data = overlayData(prepared);
  return (
    <Card p="md" radius="xl" className="chart-card overlay-card">
      <Group justify="space-between" align="flex-start" mb="sm">
        <div>
          <Title order={3}>{title}</Title>
          <Text size="sm" c="dimmed">{note}. Different units are converted by the selected scale.</Text>
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
          <Text size="sm" c="dimmed">{visible.length.toLocaleString()} shown of {totalRows.toLocaleString()} matching rows. Resolved source notes are historical, not active alerts.</Text>
        </div>
        <SegmentedControl
          data={[{ value: 'all', label: 'All' }, { value: 'flags', label: 'Notes' }, { value: 'resolved', label: 'Resolved' }, { value: 'pending', label: 'Pending' }, { value: 'numeric', label: 'Numeric' }, { value: 'qa', label: 'QA' }]}
          value={rowFocus}
          onChange={(value) => setState((current) => ({ ...current, rowFocus: value as RowFocus }))}
        />
      </Group>
      <Table.ScrollContainer minWidth={980}>
        <Table className="source-table" verticalSpacing="sm" highlightOnHover>
          <Table.Thead><Table.Tr><Table.Th>Date</Table.Th><Table.Th>Domain</Table.Th><Table.Th>Marker</Table.Th><Table.Th>Result</Table.Th><Table.Th>Reference</Table.Th><Table.Th>Source note</Table.Th><Table.Th>Source</Table.Th></Table.Tr></Table.Thead>
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
    <Table.Tr className={row.flagStatus === 'resolved' ? 'resolved-row' : undefined}>
      <Table.Td><Text fw={700}>{row.date}</Text></Table.Td>
      <Table.Td>{row.category}</Table.Td>
      <Table.Td>
        <Group gap="xs">
          <Text fw={700}>{row.marker}</Text>
          {row.derived ? <Badge size="xs" color="violet" data-tag="DERIVED" title="DERIVED">{tagLabel('DERIVED')}</Badge> : null}
          {row.normalizationWarnings ? <Badge size="xs" color="orange" data-tag="QA_ISSUE" title={row.normalizationWarnings}>{tagLabel('QA_ISSUE')}</Badge> : null}
        </Group>
      </Table.Td>
      <Table.Td><Text ff="monospace">{row.valueRaw || (row.value !== null ? formatValue(row.value, row.unit) : '—')}</Text></Table.Td>
      <Table.Td><Text size="sm" c="dimmed">{row.refRaw || '—'}</Text></Table.Td>
      <Table.Td><FlagBadge row={row} /></Table.Td>
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
        {row.normalizationWarnings ? <Badge color="orange" variant="light" size="sm">QA</Badge> : null}
        {row.pending || row.flagRaw ? <FlagBadge row={row} compact /> : null}
      </Group>
    </Group>
  );
}

function FlagBadge({ row, compact = false }: { row: LabPoint; compact?: boolean }) {
  if (row.pendingStatus === 'superseded') {
    return (
      <Stack gap={2}>
        <Badge color="green" variant="light">{compact ? 'resulted' : 'pending resulted'}</Badge>
        {!compact && row.supersededByDate ? <Text size="xs" c="dimmed">by {row.supersededByDate}{row.supersededByValue ? ` · ${row.supersededByValue}` : ''}</Text> : null}
      </Stack>
    );
  }
  if (row.pendingStatus === 'active' || row.pending) return <Badge color="orange">pending</Badge>;
  if (row.flagStatus === 'resolved') {
    const label = compact ? 'resolved' : `resolved ${row.flagRaw.toLowerCase()}`;
    return (
      <Stack gap={2}>
        <Badge color="green" variant="light">{label}</Badge>
        {!compact && row.resolvedByDate ? <Text size="xs" c="dimmed">by {row.resolvedByDate}{row.resolvedByValue ? ` · ${row.resolvedByValue}` : ''}</Text> : null}
      </Stack>
    );
  }
  if (row.flagStatus === 'active') return <Badge color="red">{row.flagRaw}</Badge>;
  return compact ? null : <Badge color="green" variant="light">ok</Badge>;
}

function FlagDot(props: any & { showFlags: boolean; color: string }) {
  const { cx, cy, payload, showFlags, color } = props;
  if (cx == null || cy == null) return null;
  const active = showFlags && payload?.flagStatus === 'active';
  const resolved = showFlags && payload?.flagStatus === 'resolved';
  return (
    <circle
      cx={cx}
      cy={cy}
      r={active ? 5 : resolved ? 4.5 : 4}
      fill="var(--paper)"
      stroke={active ? 'var(--flag)' : resolved ? 'var(--range-line)' : color}
      strokeWidth={active ? 3 : resolved ? 2.4 : 2.2}
      strokeDasharray={resolved ? '2 2' : undefined}
    />
  );
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
      {point.flagStatus === 'active' ? <Badge color="red" size="xs">{point.flagRaw}</Badge> : null}
      {point.flagStatus === 'resolved' ? <Badge color="green" variant="light" size="xs">resolved {point.flagRaw.toLowerCase()} by {point.resolvedByDate}</Badge> : null}
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
  const valueRaw = clean(row.value_display_en) || clean(row.value_raw);
  const numeric = parseNumber(row.numeric_value_display) ?? parseNumber(row.numeric_value);
  const interpretation = clean(row.interpretation_display_en) || clean(row.interpretation_en);
  const resultText = `${row.result_type || ''} ${valueRaw} ${interpretation}`;
  const pending = /pending|pendiente|not resulted|in process|en proceso|cancelled/i.test(resultText);
  const panel = clean(row.panel_display_en) || clean(row.panel_en) || clean(row.panel_original) || 'Other';
  const marker = clean(row.analyte_display_en) || clean(row.analyte_en) || clean(row.analyte_original) || 'Unknown marker';
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
    unit: clean(row.unit_display) || clean(row.unit_raw) || clean(row.ucum_unit),
    valueRaw,
    value: numeric,
    resultType: clean(row.result_type),
    refRaw: clean(row.reference_range_display) || clean(row.reference_range_raw),
    flagRaw: normalizeFlag(row.flag_raw),
    flagStatus: normalizeFlag(row.flag_raw) && !pending ? 'active' : 'none',
    interpretation,
    specimen: clean(row.specimen_display_en) || clean(row.specimen),
    method: clean(row.method),
    confidence: clean(row.confidence),
    notes: clean(row.notes),
    normalizationStatus: clean(row.normalization_status),
    normalizationApplied: clean(row.normalization_applied),
    normalizationWarnings: clean(row.normalization_warnings),
    pending,
    pendingStatus: pending ? 'active' : 'none',
    derived: /^derived|derived|ratio|index/i.test(marker) || /DERIVED/i.test(`${row.notes || ''} ${row.source_id || ''}`),
    sourceNotePath: clean(report?.source_note_path),
  };
}

function markSupersededPending(rows: LabPoint[]): LabPoint[] {
  const groups = new Map<string, LabPoint[]>();
  rows.forEach((row) => {
    const key = `${row.profileId}::${row.category}::${markerFamily(row.marker)}`;
    groups.set(key, [...(groups.get(key) || []), row]);
  });

  const superseded = new Map<string, LabPoint>();
  groups.forEach((list) => {
    const sorted = [...list].sort((a, b) => a.time - b.time);
    sorted.forEach((row) => {
      if (!row.pending || row.pendingStatus === 'superseded') return;
      const followup = sorted.find((candidate) => supersedesPending(row, candidate));
      if (followup) superseded.set(row.id, followup);
    });
  });

  if (!superseded.size) return rows;
  return rows.map((row) => {
    const followup = superseded.get(row.id);
    if (!followup) return row;
    return {
      ...row,
      pendingStatus: 'superseded',
      supersededByDate: followup.date,
      supersededByValue: followup.valueRaw || (followup.value !== null ? formatValue(followup.value, followup.unit) : undefined),
      supersededById: followup.id,
    };
  });
}

function supersedesPending(pending: LabPoint, candidate: LabPoint): boolean {
  if (candidate.time <= pending.time) return false;
  if (candidate.pending || candidate.value === null) return false;
  if (!compatibleSpecimens(pending, candidate)) return false;
  return markerFamily(pending.marker) === markerFamily(candidate.marker);
}

function markResolvedFlags(rows: LabPoint[]): LabPoint[] {
  const groups = new Map<string, LabPoint[]>();
  rows.forEach((row) => {
    const key = `${row.profileId}::${row.category}::${markerFamily(row.marker)}`;
    groups.set(key, [...(groups.get(key) || []), row]);
  });

  const resolutions = new Map<string, LabPoint>();
  groups.forEach((list) => {
    const sorted = [...list].sort((a, b) => a.time - b.time);
    sorted.forEach((row) => {
      if (!row.flagRaw || row.pending) return;
      const followup = sorted.find((candidate) => resolvesFlag(row, candidate));
      if (followup) resolutions.set(row.id, followup);
    });
  });

  if (!resolutions.size) return rows;
  return rows.map((row) => {
    const followup = resolutions.get(row.id);
    if (!followup) return row;
    return {
      ...row,
      flagStatus: 'resolved',
      resolvedByDate: followup.date,
      resolvedByValue: followup.valueRaw || (followup.value !== null ? formatValue(followup.value, followup.unit) : undefined),
      resolvedById: followup.id,
    };
  });
}

function resolvesFlag(flagged: LabPoint, candidate: LabPoint): boolean {
  if (candidate.time <= flagged.time) return false;
  if (candidate.pending || candidate.value === null) return false;
  if (candidate.flagRaw) return false;
  if (!compatibleSpecimens(flagged, candidate)) return false;
  if (!looksNormal(candidate)) return false;
  if (!sameUnit(flagged.unit, candidate.unit)) return true;
  if (/high|above|elevated/i.test(flagged.flagRaw)) return candidate.value <= (flagged.value ?? candidate.value);
  if (/low|below|decreased/i.test(flagged.flagRaw)) return candidate.value >= (flagged.value ?? candidate.value);
  return true;
}

function markerFamily(marker: string): string {
  return clean(marker)
    .toLowerCase()
    .replace(/\b(whole blood|serum|plasma|blood|urine|random|spot|level|test|tests)\b/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function compatibleSpecimens(a: LabPoint, b: LabPoint): boolean {
  const left = specimenFamily(a);
  const right = specimenFamily(b);
  if (!left || !right) return true;
  return left === right;
}

function specimenFamily(row: LabPoint): string {
  const text = `${row.specimen} ${row.marker}`.toLowerCase();
  if (/urine/.test(text)) return 'urine';
  if (/hair/.test(text)) return 'hair';
  if (/saliva/.test(text)) return 'saliva';
  if (/blood|serum|plasma/.test(text)) return 'blood';
  return '';
}

function looksNormal(row: LabPoint): boolean {
  if (row.flagRaw || row.pending || row.value === null) return false;
  const ref = parseReference(row.refRaw);
  if (!ref) return true;
  if (ref.low !== null && row.value < ref.low) return false;
  if (ref.high !== null && row.value > ref.high) return false;
  return true;
}

function sameUnit(a: string, b: string): boolean {
  const left = clean(a).toLowerCase().replace(/μ/g, 'µ');
  const right = clean(b).toLowerCase().replace(/μ/g, 'µ');
  return !!left && !!right && left === right;
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
    if (query && !`${row.marker} ${row.panel} ${row.category} ${row.valueRaw} ${row.refRaw} ${row.normalizationApplied} ${row.normalizationWarnings} ${row.sourceId}`.toLowerCase().includes(query)) return false;
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
        flagStatus: row.flagStatus,
        resolvedByDate: row.resolvedByDate,
        resolvedByValue: row.resolvedByValue,
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
      ...labWeight.map((row) => ({ id: row.id, date: row.date, time: row.time, value: row.value as number, rawValue: row.value as number, valueRaw: row.valueRaw, flagRaw: row.flagRaw, flagStatus: row.flagStatus, resolvedByDate: row.resolvedByDate, resolvedByValue: row.resolvedByValue, refRaw: row.refRaw })),
      ...wearableWeight.map((row) => ({ id: row.id, date: row.date, time: row.time, value: row.value, rawValue: row.value, valueRaw: String(row.value), flagRaw: '', flagStatus: 'none' as const, note: 'wearable body mass' })),
    ].filter((point) => !start || point.time >= start).sort((a, b) => a.time - b.time);
    if (points.length) series.push({ id: 'context-weight', label: 'Weight context (kg)', shortLabel: 'Weight', category: 'Context', unit: 'kg', kind: 'context', color: CONTEXT_COLOR, points, ref: null, derived: false });
  }
  const remaining = [...selected].filter((metric) => metric !== 'Weight');
  remaining.forEach((metric, index) => {
    const points = wearableRows
      .filter((row) => row.profileId === state.profile && row.metric === metric)
      .filter((row) => !start || row.time >= start)
      .sort((a, b) => a.time - b.time)
      .map((row) => ({ id: row.id, date: row.date, time: row.time, value: row.value, rawValue: row.value, valueRaw: String(row.value), flagRaw: '', flagStatus: 'none' as const, note: `${row.aggregation} wearable metric` }));
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
    const active = list.find((point) => point.flagStatus === 'active');
    const resolved = list.find((point) => point.flagStatus === 'resolved');
    const flagPoint = active || resolved;
    return {
      ...first,
      id: `${first.id}-mean-${date}`,
      value: avg,
      rawValue: avg,
      valueRaw: `${compactNumber(avg)} mean`,
      flagRaw: flagPoint?.flagRaw || '',
      flagStatus: flagPoint?.flagStatus || 'none',
      resolvedByDate: flagPoint?.resolvedByDate,
      resolvedByValue: flagPoint?.resolvedByValue,
    };
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
  if (focus === 'flags') return activeFlagRows(rows);
  if (focus === 'resolved') return resolvedFlagRows(rows);
  if (focus === 'pending') return activePendingRows(rows);
  if (focus === 'numeric') return rows.filter((row) => row.value !== null && !row.pending);
  if (focus === 'qa') return rows.filter((row) => row.normalizationWarnings || row.normalizationApplied);
  return rows;
}

type OverlayPick = { series: Series[]; title: string; note: string; badge: string };

function selectOverlaySeries(series: Series[], state: UiState): OverlayPick {
  const context = series
    .filter((item) => item.kind === 'context')
    .sort(contextSeriesSort)
    .slice(0, 4);
  const labs = series.filter((item) => item.kind === 'lab');
  const domainLabs = state.category === 'All categories' ? labs : labs.filter((item) => item.category === state.category);
  const domainLabel = state.category === 'All categories' ? 'all domains' : state.category;
  const preset = state.overlayPreset || 'smart';

  if (preset === 'context') {
    return {
      series: context,
      title: 'Context overlay',
      note: context.length ? 'Weight and wearable context only' : 'No selected context series in this filter',
      badge: 'context',
    };
  }

  if (preset === 'current') {
    const ranked = rankSeries(domainLabs.length ? domainLabs : labs, state);
    return {
      series: capOverlay([...context, ...ranked]),
      title: `${domainLabel} comparison`,
      note: `Top ${domainLabel} markers with selected context first`,
      badge: 'current domain',
    };
  }

  if (preset === 'flagged') {
    const flagged = labs.filter((item) => flagCount(item) > 0).sort((a, b) => flagCount(b) - flagCount(a) || seriesSignalScore(b, state) - seriesSignalScore(a, state));
    const fallback = rankSeries(domainLabs.length ? domainLabs : labs, state);
    return {
      series: capOverlay([...context, ...flagged, ...fallback]),
      title: 'Source-note overlay',
      note: 'Series with source notes first, then nearest useful comparators',
      badge: 'notes first',
    };
  }

  if (preset === 'recent') {
    const recent = [...(domainLabs.length ? domainLabs : labs)].sort((a, b) => latestTime(b) - latestTime(a) || movementScore(b) - movementScore(a));
    return {
      series: capOverlay([...context, ...recent]),
      title: 'Recent movement overlay',
      note: 'Newest updated markers first so recent tests line up with context',
      badge: 'recent',
    };
  }

  if (preset === 'core') {
    const core = coreOverlaySeries(labs, state);
    return {
      series: capOverlay([...context, ...core, ...rankSeries(domainLabs, state)]),
      title: 'Core-marker overlay',
      note: state.category === 'All categories' ? 'Representative high-signal markers across domains' : `Core ${state.category} markers with context`,
      badge: 'core markers',
    };
  }

  const smartBase = state.category === 'All categories'
    ? [...labs.filter((item) => flagCount(item) > 0), ...coreOverlaySeries(labs, state), ...rankSeries(labs, state)]
    : [...domainLabs.filter((item) => flagCount(item) > 0), ...rankSeries(domainLabs, state), ...coreOverlaySeries(labs, state)];
  return {
    series: capOverlay([...context, ...smartBase]),
    title: 'Smart overlay comparison',
    note: state.category === 'All categories'
      ? 'Auto-picked context, source-note rows, and representative domain markers'
      : `Auto-picked context, source-note rows, and high-signal ${state.category} markers`,
    badge: 'smart',
  };
}

function capOverlay(items: Series[]): Series[] {
  const unique = uniqueSeries(items);
  const contextCount = unique.filter((item) => item.kind === 'context').length;
  return unique.slice(0, Math.max(OVERLAY_LIMIT, contextCount));
}

function uniqueSeries(items: Series[]): Series[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    if (seen.has(item.id)) return false;
    seen.add(item.id);
    return true;
  });
}

function rankSeries(items: Series[], state: UiState): Series[] {
  return [...items].sort((a, b) => seriesSignalScore(b, state) - seriesSignalScore(a, state) || a.shortLabel.localeCompare(b.shortLabel));
}

function coreOverlaySeries(labs: Series[], state: UiState): Series[] {
  if (state.category !== 'All categories') {
    return rankSeries(labs.filter((item) => item.category === state.category), state).slice(0, OVERLAY_LIMIT);
  }

  const priorityCategories = ['Heavy metals', 'Liver', 'Lipids', 'Glycemia', 'Kidney / urate', 'CBC / Hematology', 'Vitals'];
  const picked: Series[] = [];
  priorityCategories.forEach((category) => {
    picked.push(...rankSeries(labs.filter((item) => item.category === category), state).slice(0, category === 'Liver' ? 3 : 2));
  });
  return uniqueSeries([...picked, ...rankSeries(labs, state)]);
}

function seriesSignalScore(series: Series, state: UiState): number {
  const categoryFit = state.category !== 'All categories' && series.category === state.category ? 120 : 0;
  const flags = flagCount(series) * 90;
  const priority = Math.max(0, 90 - markerPriority(series));
  const density = Math.min(series.points.length, 12) * 3;
  const recent = latestTime(series) / 100000000000;
  const movement = movementScore(series) * 6;
  const derivedPenalty = series.derived ? -8 : 0;
  return categoryFit + flags + priority + density + recent + movement + derivedPenalty;
}

function markerPriority(series: Series): number {
  const text = `${series.category} ${series.label} ${series.shortLabel}`.toLowerCase();
  const patterns = [
    /mercury/, /lead/, /arsenic/, /cadmium/,
    /\balt\b/, /\bast\b/, /\bggt\b|gamma/, /total bilirubin/, /direct bilirubin/, /indirect bilirubin/, /alkaline phosphatase/, /albumin/, /ast\/alt|ast alt/,
    /apob|apo b/, /\bldl\b/, /\bhdl\b/, /triglyceride/, /total cholesterol/, /lipoprotein/,
    /a1c|hba1c/, /glucose/, /insulin/,
    /creatinine/, /egfr/, /urea|bun/, /uric/,
    /hemoglobin/, /platelet/, /\bwbc\b|white blood/, /\brbc\b|red blood/, /neutrophil/, /lymphocyte/,
    /weight|body mass/, /blood pressure/, /resting heart rate|heart rate/,
  ];
  const idx = patterns.findIndex((pattern) => pattern.test(text));
  return idx === -1 ? 80 : idx;
}

function contextSeriesSort(a: Series, b: Series): number {
  return contextRank(a.shortLabel) - contextRank(b.shortLabel) || latestTime(b) - latestTime(a);
}

function flagCount(series: Series): number {
  return series.points.filter((point) => point.flagStatus === 'active').length;
}

function resolvedFlagCount(series: Series): number {
  return series.points.filter((point) => point.flagStatus === 'resolved').length;
}

function activeFlagRows(rows: LabPoint[]): LabPoint[] {
  return rows.filter((row) => row.flagStatus === 'active' && !row.pending);
}

function resolvedFlagRows(rows: LabPoint[]): LabPoint[] {
  return rows.filter((row) => row.flagStatus === 'resolved' && !row.pending);
}

function activePendingRows(rows: LabPoint[]): LabPoint[] {
  return rows.filter((row) => row.pendingStatus === 'active');
}

function supersededPendingRows(rows: LabPoint[]): LabPoint[] {
  return rows.filter((row) => row.pendingStatus === 'superseded');
}

function latestTime(series: Series): number {
  return Math.max(...series.points.map((point) => point.time).filter(Number.isFinite), 0);
}

function movementScore(series: Series): number {
  const values = series.points.map((point) => point.value).filter(Number.isFinite);
  if (values.length < 2) return 0;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
  return mean ? Math.min(Math.abs(max - min) / Math.abs(mean), 5) : 0;
}

function groupStats(list: Series[]) {
  const flags = list.reduce((sum, item) => sum + flagCount(item), 0);
  const resolved = list.reduce((sum, item) => sum + resolvedFlagCount(item), 0);
  const points = list.reduce((sum, item) => sum + item.points.length, 0);
  const latest = list.map((item) => item.points.at(-1)?.date || '').sort().at(-1) || '';
  return { flags, resolved, points, latest };
}

function defaultOpenGroups(entries: [string, Series[]][]): string[] {
  return [...entries]
    .sort(([catA, listA], [catB, listB]) => groupScore(catB, listB) - groupScore(catA, listA) || categoryRank(catA) - categoryRank(catB))
    .slice(0, 5)
    .map(([category]) => category);
}

function groupScore(category: string, list: Series[]): number {
  const stats = groupStats(list);
  return stats.flags * 100 + Math.min(stats.points, 250) + Math.max(0, 80 - categoryRank(category) * 5);
}

function buildProfiles(labRows: LabPoint[], wearableRows: WearablePoint[]): ComboboxItem[] {
  const ids = new Set<string>();
  (DATA.profiles || []).forEach((profile) => profile.profile_id && ids.add(profile.profile_id));
  labRows.forEach((row) => ids.add(row.profileId));
  wearableRows.forEach((row) => ids.add(row.profileId));
  Object.keys(DATA.profile_context || {}).forEach((id) => ids.add(id));
  Object.keys(DATA.genomics || {}).forEach((id) => ids.add(id));
  if (!ids.size) ['rod', 'cara'].forEach((id) => ids.add(id));
  return [...ids].filter(isSafeAlias).sort((a, b) => profileRank(a) - profileRank(b) || a.localeCompare(b)).map((id) => ({ value: id, label: displayAlias(id) }));
}

function currentProfileContext(profileId: string): ProfileContextPayload {
  const context = DATA.profile_context?.[profileId];
  return (context && typeof context === 'object' ? context : {}) as ProfileContextPayload;
}

function profileArtifacts(context: ProfileContextPayload): ProfileArtifact[] {
  const artifacts = [
    ...safeArtifacts(context.contextNotes),
    ...safeArtifacts(context.familyHistory),
    ...safeArtifacts(context.hereditaryRisks),
    ...safeArtifacts(context.specialistNotes),
    ...safeArtifacts(context.quickReviewCards),
    ...safeArtifacts(context.diagnosticGaps),
    ...safeArtifacts(context.researchJobs),
  ];
  return artifacts.sort((a, b) => clean(b.date).localeCompare(clean(a.date)) || artifactRank(a) - artifactRank(b));
}

function safeArtifacts(value: unknown): ProfileArtifact[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter((item): item is ProfileArtifact => !!item && typeof item === 'object')
    .map((item) => ({
      kind: clean(item.kind),
      date: clean(item.date),
      title: clean(item.title),
      status: clean(item.status),
      summary: clean(item.summary),
      evidence: clean(item.evidence),
      profile_id: clean(item.profile_id),
      relative_id: clean(item.relative_id),
      related_profile_ids: Array.isArray(item.related_profile_ids) ? item.related_profile_ids.map(clean).filter(Boolean) : [],
      relation: clean(item.relation),
      degree: typeof item.degree === 'number' ? item.degree : null,
      lineage: clean(item.lineage),
      shared_household: typeof item.shared_household === 'boolean' ? item.shared_household : null,
      priority: typeof item.priority === 'number' ? item.priority : null,
      gap_type: clean(item.gap_type),
      candidate_tests: Array.isArray(item.candidate_tests) ? item.candidate_tests.map(clean).filter(Boolean) : [],
      context_questions: Array.isArray(item.context_questions) ? item.context_questions.map(clean).filter(Boolean) : [],
      lenses: Array.isArray(item.lenses) ? item.lenses.map(clean).filter(Boolean) : [],
      onset_age: typeof item.onset_age === 'number' ? item.onset_age : null,
      tags: Array.isArray(item.tags) ? item.tags.map(clean).filter(Boolean) : [],
    }));
}

function artifactRank(artifact: ProfileArtifact): number {
  const kind = clean(artifact.kind).toLowerCase();
  if (kind === 'context') return 0;
  if (kind === 'family_history') return 1;
  if (kind === 'hereditary') return 2;
  if (kind === 'diagnostic_gap') return 3;
  if (kind === 'quick_review') return 4;
  if (kind === 'specialist') return 5;
  if (kind === 'research_job') return 6;
  return 5;
}

function profileArtifactCount(context: ProfileContextPayload): number {
  return profileArtifacts(context).length;
}

function sourceVaultCountFor(context: ProfileContextPayload): number {
  const count = Number(context.sourceVault?.count || 0);
  return Number.isFinite(count) ? count : 0;
}

function currentGenomics(profileId: string): GenomicsReviewPayload | null {
  const payload = DATA.genomics?.[profileId];
  return payload && typeof payload === 'object' ? payload : null;
}

function genomicsSourceCount(genomics: GenomicsReviewPayload | null): number {
  if (!genomics) return 0;
  const count = numericValue(genomics.sources?.count);
  if (count !== null) return count;
  return safeGenomicsSources(genomics).length;
}

function genomicsMarkerCount(genomics: GenomicsReviewPayload | null): number {
  if (!genomics) return 0;
  const count = numericValue(genomics.sources?.variant_count);
  if (count !== null) return count;
  return safeGenomicsSources(genomics).reduce((sum, source) => sum + Number(source.stored_variant_count || 0), 0);
}

function genomicsCardCount(genomics: GenomicsReviewPayload | null): number {
  if (!genomics) return 0;
  const count = numericValue(genomics.crossrefs?.count);
  if (count !== null) return count;
  return safeGenomicsCards(genomics).length;
}

function genomicsSummaryLine(genomics: GenomicsReviewPayload): string {
  const lead = clean(genomics.patient_summary?.lead);
  if (lead) return lead;
  const cards = safeGenomicsCards(genomics);
  const topics = uniqueStrings(cards.map((card) => clean(card.patient_summary).split(' — ', 1)[0]).filter(Boolean)).slice(0, 3);
  if (topics.length) return `Genetic review cards include ${topics.join(', ')}.`;
  if (genomicsMarkerCount(genomics)) return `${genomicsMarkerCount(genomics).toLocaleString()} matched genetic markers are saved for review.`;
  return 'No specific genomics matches are showing yet.';
}

function genomicsUiHref(profileId: string): string {
  const params = new URLSearchParams({ profile: profileId });
  if (location.protocol === 'file:') return `http://127.0.0.1:8766/genomics/ui?${params.toString()}`;
  return `/genomics/ui?${params.toString()}`;
}

function safeGenomicsSources(genomics: GenomicsReviewPayload | null): GenomicsSourcePayload[] {
  const sources = genomics?.sources?.sources;
  return Array.isArray(sources) ? sources.filter((source): source is GenomicsSourcePayload => !!source && typeof source === 'object') : [];
}

function safeGenomicsQc(genomics: GenomicsReviewPayload | null): GenomicsQcPayload[] {
  const rows = genomics?.qc?.qc;
  return Array.isArray(rows) ? rows.filter((row): row is GenomicsQcPayload => !!row && typeof row === 'object') : [];
}

function safeGenomicsCards(genomics: GenomicsReviewPayload | null): GenomicCardPayload[] {
  const cards = genomics?.crossrefs?.cards;
  return Array.isArray(cards) ? cards.filter((card): card is GenomicCardPayload => !!card && typeof card === 'object') : [];
}

function safeStrings(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map(clean).filter(Boolean);
}

function safeTags(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return uniqueStrings(value.map((item) => clean(item).toUpperCase()).filter((item) => /^[A-Z0-9_]+$/.test(item)));
}

function uniqueStrings(value: string[]): string[] {
  return [...new Set(value.map(clean).filter(Boolean))];
}

function primaryTag(tags: string[] | undefined): string {
  const ordered = ['QA_ISSUE', 'DATA_GAP', 'HEREDITARY_RISK', 'FAMILY_HISTORY', 'SPECIALIST_NOTE', 'INFERENCE', 'CONTEXT', 'OBSERVED'];
  const safe = new Set(safeTags(tags || []));
  return ordered.find((tag) => safe.has(tag)) || [...safe][0] || 'CONTEXT';
}

function patientHistoryItems(profileId: string, rows: LabPoint[], context: ProfileContextPayload): ProfileArtifact[] {
  const byDate = new Map<string, LabPoint[]>();
  rows.forEach((row) => {
    byDate.set(row.date, [...(byDate.get(row.date) || []), row]);
  });
  const labEvents: ProfileArtifact[] = [...byDate.entries()].map(([date, list]) => {
    const categories = [...new Set(list.map((row) => row.category))].sort((a, b) => categoryRank(a) - categoryRank(b) || a.localeCompare(b));
    const flags = activeFlagRows(list).length;
    const pending = activePendingRows(list).length;
    return {
      kind: 'lab',
      date,
      title: `${list.length} lab/source row(s)`,
      status: flags ? `${flags} active source note(s)` : pending ? `${pending} pending` : 'observed',
      summary: categories.slice(0, 6).join(', '),
      tags: flags ? ['QA_ISSUE'] : pending ? ['DATA_GAP'] : ['OBSERVED'],
    };
  });
  const sourceVault = context.sourceVault?.count
    ? [{
        kind: 'source_vault',
        date: context.sourceVault.latest_date || context.sourceVault.first_date || '',
        title: 'Private source vault cataloged',
        status: `${context.sourceVault.count} source(s)`,
        summary: 'Raw sources are stored locally as hash-named blobs; original filenames and paths are not exported.',
        tags: ['CONTEXT'],
      } as ProfileArtifact]
    : [];
  return [
    ...sourceVault,
    ...labEvents,
    ...profileArtifacts(context),
  ]
    .filter((item) => item.date || item.title)
    .sort((a, b) => clean(b.date).localeCompare(clean(a.date)) || artifactRank(a) - artifactRank(b));
}

function dateSpan(dates: string[]): string {
  const safe = dates.filter(Boolean).sort();
  if (!safe.length) return '';
  const first = safe[0];
  const last = safe.at(-1) || first;
  return first === last ? first : `${first} → ${last}`;
}

function profileBirthLabel(profile?: ProfilePayload): string {
  if (!profile?.birth_year) return 'not set';
  return profile.birth_month ? `${profile.birth_year}-${String(profile.birth_month).padStart(2, '0')}` : String(profile.birth_year);
}

function approximateAge(profile?: ProfilePayload): number | null {
  if (!profile?.birth_year) return null;
  const now = new Date();
  let age = now.getFullYear() - profile.birth_year;
  if (profile.birth_month && now.getMonth() + 1 < profile.birth_month) age -= 1;
  return age;
}

function reverseRelation(relation: string): string {
  const map: Record<string, string> = {
    father: 'child',
    mother: 'child',
    parent: 'child',
    son: 'parent',
    daughter: 'parent',
    child: 'parent',
    brother: 'sibling',
    sister: 'sibling',
    sibling: 'sibling',
    grandfather: 'grandchild',
    grandmother: 'grandchild',
    grandparent: 'grandchild',
    grandson: 'grandparent',
    granddaughter: 'grandparent',
    grandchild: 'grandparent',
  };
  return map[relation] || relation;
}

function artifactKindLabel(kind?: string): string {
  return clean(kind).replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase()) || 'Profile event';
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
  const mode = (params.get('mode') as TimelineMode) || 'stack';
  const range = (params.get('range') as TimeRange) || (mode === 'overlay' ? '18mo' : 'all');
  return {
    profile: params.get('profile') || profiles[0]?.value || 'rod',
    range,
    category,
    section: (params.get('section') as SectionId) || 'profile',
    mode,
    scale: (params.get('scale') as ScaleMode) || 'auto',
    agg: (params.get('agg') as AggMode) || 'observed',
    smoothing: params.get('smooth') || 'none',
    overlayPreset: (params.get('overlay') as OverlayPreset) || 'smart',
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
  if (state.overlayPreset !== 'smart') params.set('overlay', state.overlayPreset);
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
  const cols = ['date', 'category', 'marker', 'valueRaw', 'unit', 'refRaw', 'flagRaw', 'flagStatus', 'resolvedByDate', 'resolvedByValue', 'pendingStatus', 'supersededByDate', 'supersededByValue', 'normalizationStatus', 'normalizationApplied', 'normalizationWarnings', 'sourceId'];
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

function numericValue(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  return parseNumber(value);
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
