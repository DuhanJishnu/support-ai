'use client';

import { FormEvent, useMemo, useState } from 'react';
import { useAgentStream } from './hooks/useAgentStream';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

type AgentStatus =
  | 'resolved'
  | 'querying'
  | 'review'
  | 'in_progress'
  | 'succeeded'
  | 'failed'
  | 'needs_human';

type ChatMessage = {
  id: number;
  author: 'customer' | 'agent';
  body: string;
  time: string;
};

type ToolCall = {
  id: string;
  tool: string;
  status: AgentStatus;
  detail: string;
  input?: Record<string, unknown>;
  result?: Record<string, unknown>;
};

const tickets = [
  {
    id: 'TCK-1048',
    customer: 'Maya R.',
    issue: 'Duplicate charge',
    intent: 'BILLING',
    urgency: 3,
  },
  {
    id: 'TCK-1049',
    customer: 'Andre P.',
    issue: 'Route deviation',
    intent: 'SAFETY',
    urgency: 4,
  },
  {
    id: 'TCK-1050',
    customer: 'Nina K.',
    issue: 'Promo code failed',
    intent: 'GENERAL',
    urgency: 1,
  },
];

function statusClasses(status: AgentStatus) {
  if (status === 'resolved' || status === 'succeeded') {
    return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  }

  if (status === 'querying' || status === 'in_progress') {
    return 'border-cyan-200 bg-cyan-50 text-cyan-700';
  }

  if (status === 'failed' || status === 'needs_human') {
    return 'border-rose-200 bg-rose-50 text-rose-700';
  }

  return 'border-amber-200 bg-amber-50 text-amber-700';
}

function getRecord(value: unknown): Record<string, unknown> | null {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }

  return null;
}

function getToolData(
  result?: Record<string, unknown>
): Record<string, unknown> {
  const data = getRecord(result?.data);
  return data ?? result ?? {};
}

function ThinkingDots() {
  const delays = ['0s', '0.2s', '0.4s'];

  return (
    <div className="flex items-center gap-1.5">
      {delays.map((delay) => (
        <span
          key={delay}
          className="animate-thinking-wave h-2 w-2 rounded-full bg-linear-to-br from-cyan-300 to-cyan-500 shadow-lg shadow-cyan-500/40"
          style={{ animationDelay: delay }}
        />
      ))}
    </div>
  );
}

function summarizeToolCall(call: ToolCall) {
  const data = getToolData(call.result);

  if (call.tool === 'verify_transaction_status') {
    return `${String(data.transaction_id ?? 'transaction')} returned ${String(
      data.status ?? call.status
    )}`;
  }

  if (call.tool === 'get_ride_route_deviation') {
    return `${String(data.ride_id ?? 'ride')} deviation score ${String(
      data.deviation_score ?? 'pending'
    )}`;
  }

  return call.detail;
}

function toolCallsFromContext(context: Record<string, unknown>): ToolCall[] {
  return ['billing', 'telemetry']
    .map((key) => {
      const toolContext = getRecord(context[key]);
      if (!toolContext) {
        return null;
      }

      const tool = String(toolContext.tool ?? key);
      const result = getRecord(toolContext.result) ?? undefined;
      const input = getRecord(toolContext.input) ?? undefined;
      const call: ToolCall = {
        id: `context-${key}`,
        tool,
        status: 'succeeded',
        detail: summarizeToolCall({
          id: `context-${key}`,
          tool,
          status: 'succeeded',
          detail: '',
          input,
          result,
        }),
        input,
        result,
      };

      return call;
    })
    .filter((call): call is ToolCall => Boolean(call));
}

function ToolEvidence({ call }: { call: ToolCall }) {
  const data = getToolData(call.result);

  if (call.tool === 'verify_transaction_status') {
    return (
      <section className="mt-3 rounded-lg border border-l-4 border-zinc-200 border-l-emerald-500 bg-white p-3 shadow-sm transition-all hover:shadow-md">
        <div className="mb-3 flex items-center justify-between gap-3 border-b border-zinc-100 pb-2">
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-emerald-500" />
            <h3 className="text-sm font-semibold text-zinc-950">
              Billing Verification
            </h3>
          </div>
          <span
            className={`rounded-lg border px-2 py-1 text-xs font-semibold ${statusClasses(
              call.status
            )}`}
          >
            {String(data.status ?? call.status)}
          </span>
        </div>
        <div className="rounded-md border border-zinc-100 bg-zinc-50 p-3">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
            <div>
              <dt className="text-[10px] font-bold text-zinc-400 uppercase">
                Transaction ID
              </dt>
              <dd className="mt-0.5 font-mono text-xs font-semibold text-zinc-950">
                {String(
                  data.transaction_id ?? call.input?.transaction_id ?? 'n/a'
                )}
              </dd>
            </div>
            <div>
              <dt className="text-[10px] font-bold text-zinc-400 uppercase">
                Amount
              </dt>
              <dd className="mt-0.5 font-bold text-zinc-950">
                {String(data.currency ?? 'USD')} {String(data.amount ?? '0.00')}
              </dd>
            </div>
            <div>
              <dt className="text-[10px] font-bold text-zinc-400 uppercase">
                Payment Method
              </dt>
              <dd className="mt-0.5 font-semibold text-zinc-700 italic">
                {String(data.payment_method ?? 'Unknown')}
              </dd>
            </div>
            <div>
              <dt className="text-[10px] font-bold text-zinc-400 uppercase">
                Gateway Resp
              </dt>
              <dd
                className={`mt-0.5 font-bold ${
                  data.status === 'SUCCESS'
                    ? 'text-emerald-600'
                    : 'text-rose-600'
                }`}
              >
                {String(data.status ?? 'PENDING')}
              </dd>
            </div>
          </dl>
        </div>
        <div className="mt-3 flex w-fit items-center gap-2 rounded border border-zinc-100 bg-white px-2 py-1 text-[10px] text-zinc-400">
          <div className="h-1.5 w-1.5 rounded-full bg-zinc-300" />
          <span>Authenticated via Billing MCP</span>
        </div>
      </section>
    );
  }

  if (call.tool === 'get_ride_route_deviation') {
    const score = Number(data.deviation_score ?? 0);
    const percent = Math.min(Math.max(score, 0), 1) * 100;

    return (
      <section className="mt-3 rounded-lg border border-zinc-200 bg-white p-3 shadow-sm transition-all hover:shadow-md">
        <div className="mb-3 flex items-center justify-between gap-3 border-b border-zinc-100 pb-2">
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 animate-pulse rounded-full bg-cyan-500" />
            <h3 className="text-sm font-semibold text-zinc-950">
              Route Telemetry Analysis
            </h3>
          </div>
          <span
            className={`rounded-lg border px-2 py-1 text-xs font-semibold ${statusClasses(
              call.status
            )}`}
          >
            {String(data.status ?? call.status)}
          </span>
        </div>
        <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3">
          <div className="relative h-24 overflow-hidden rounded-md border border-zinc-100 bg-white shadow-inner">
            <div
              className="absolute inset-0 opacity-5"
              style={{
                backgroundImage: 'radial-gradient(#000 1px, transparent 1px)',
                backgroundSize: '20px 20px',
              }}
            />
            <div className="absolute top-1/2 left-4 h-1 w-[78%] -translate-y-1/2 bg-zinc-200" />
            <div
              className="absolute top-[52%] left-4 h-1.5 rounded-full bg-cyan-500/30 transition-all duration-1000"
              style={{ width: `${Math.max(percent, 12)}%` }}
            />
            <div className="absolute top-5 left-4 flex h-4 w-4 items-center justify-center rounded-full border-2 border-white bg-emerald-500 shadow-sm">
              <span className="text-[8px] font-bold text-white">A</span>
            </div>
            <div className="absolute right-5 bottom-5 flex h-4 w-4 items-center justify-center rounded-full border-2 border-white bg-rose-500 shadow-sm">
              <span className="text-[8px] font-bold text-white">B</span>
            </div>
            {score > 0.3 && (
              <div className="absolute top-[45%] left-1/3 h-6 w-1 rotate-45 animate-pulse rounded-full bg-amber-400" />
            )}
          </div>
          <div className="mt-3 flex items-center justify-between text-sm">
            <span className="font-medium text-zinc-600">
              GPS Deviation Score
            </span>
            <span
              className={`font-bold ${
                score > 0.5 ? 'text-rose-600' : 'text-emerald-600'
              }`}
            >
              {(score * 100).toFixed(1)}%
            </span>
          </div>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <div className="rounded border border-zinc-100 bg-zinc-50 p-2 text-center">
            <p className="text-[10px] font-bold text-zinc-400 uppercase">
              Ride ID
            </p>
            <p className="truncate text-xs font-semibold text-zinc-700">
              {String(data.ride_id ?? 'n/a')}
            </p>
          </div>
          <div className="rounded border border-zinc-100 bg-zinc-50 p-2 text-center">
            <p className="text-[10px] font-bold text-zinc-400 uppercase">
              Status
            </p>
            <p className="truncate text-xs font-semibold text-zinc-700">
              {String(data.anomaly_type ?? 'Normal')}
            </p>
          </div>
        </div>
        <p className="mt-3 text-xs leading-5 text-zinc-500 italic">
          {String(data.details ?? 'Route data processed via Telemetry MCP.')}
        </p>
      </section>
    );
  }

  return null;
}

const RESOLUTION_CONFIG: Record<
  string,
  { label: string; color: string; icon: string }
> = {
  ISSUE_REFUND: { label: 'Refund Approved', color: 'emerald', icon: '✓' },
  ESCALATE: { label: 'Escalated to Manager', color: 'rose', icon: '⬆' },
  REVIEW_CASE: { label: 'Under Review', color: 'amber', icon: '⏳' },
  NO_ACTION: { label: 'No Action Required', color: 'zinc', icon: '—' },
};

function ResolutionCard({
  resolution,
  status,
}: {
  resolution: Record<string, unknown>;
  status: string;
}) {
  const action = String(resolution.action ?? 'NO_ACTION');
  const amount = Number(resolution.amount ?? 0);
  const reason = String(resolution.reason ?? '');
  const config = RESOLUTION_CONFIG[action] ?? RESOLUTION_CONFIG.NO_ACTION;

  const colorMap: Record<string, string> = {
    emerald: 'border-emerald-300 bg-emerald-50/80',
    rose: 'border-rose-300 bg-rose-50/80',
    amber: 'border-amber-300 bg-amber-50/80',
    zinc: 'border-zinc-300 bg-zinc-50/80',
  };
  const badgeMap: Record<string, string> = {
    emerald: 'bg-emerald-100 text-emerald-800',
    rose: 'bg-rose-100 text-rose-800',
    amber: 'bg-amber-100 text-amber-800',
    zinc: 'bg-zinc-100 text-zinc-800',
  };

  return (
    <section
      className={`mt-3 rounded-lg border-2 p-4 transition-all ${colorMap[config.color]}`}
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-lg">{config.icon}</span>
          <h3 className="text-sm font-bold text-zinc-950">
            Resolution Decision
          </h3>
        </div>
        <span
          className={`rounded-full px-3 py-1 text-xs font-bold ${badgeMap[config.color]}`}
        >
          {config.label}
        </span>
      </div>
      {amount > 0 && (
        <div className="mb-3 rounded-md bg-white/60 p-3 text-center">
          <p className="text-[10px] font-bold tracking-wider text-zinc-400 uppercase">
            Refund Amount
          </p>
          <p className="mt-1 text-2xl font-bold text-zinc-950">
            ${amount.toFixed(2)}
          </p>
        </div>
      )}
      <p className="text-sm leading-relaxed text-zinc-700">{reason}</p>
      <div className="mt-3 flex items-center gap-2 text-[10px] text-zinc-400">
        <div
          className={`h-1.5 w-1.5 rounded-full ${status === 'resolved' ? 'bg-emerald-400' : status === 'needs_human' ? 'bg-rose-400' : 'bg-amber-400'}`}
        />
        <span>Status: {status}</span>
      </div>
    </section>
  );
}

function AgentActivity({
  isStreaming,
  latestStatus,
  toolCalls,
  resolutionStatus,
}: {
  isStreaming: boolean;
  latestStatus?: Record<string, unknown>;
  toolCalls: ToolCall[];
  resolutionStatus: string;
}) {
  const hasToolQuery = toolCalls.some((call) => call.status === 'querying');
  const currentNode = String(latestStatus?.node ?? 'idle');

  const finalStatus = isStreaming ? 'in_progress' : resolutionStatus;

  const steps = [
    {
      label: 'Thinking',
      status:
        isStreaming && currentNode === 'router' ? 'in_progress' : 'resolved',
      detail: 'Router is classifying the customer message.',
    },
    {
      label: 'Querying Database',
      status: hasToolQuery
        ? 'querying'
        : isStreaming
          ? 'in_progress'
          : 'resolved',
      detail: 'Specialist agents call billing or telemetry MCP tools.',
    },
    {
      label: 'Policy Check',
      status:
        isStreaming && currentNode === 'guardrail'
          ? 'querying'
          : (finalStatus as AgentStatus),
      detail: `Current node: ${currentNode}`,
    },
  ];

  return (
    <div className="space-y-2">
      {steps.map((step) => (
        <div
          className={`flex items-start gap-3 rounded-lg border p-3 transition-colors ${
            step.status === 'in_progress' || step.status === 'querying'
              ? 'border-cyan-200 bg-cyan-50/50'
              : step.status === 'needs_human'
                ? 'border-rose-200 bg-rose-50/50'
                : 'border-zinc-200 bg-white'
          }`}
          key={step.label}
        >
          <span
            className={`mt-1 h-2.5 w-2.5 rounded-full ${
              step.status === 'in_progress' || step.status === 'querying'
                ? 'animate-pulse-soft bg-cyan-500'
                : step.status === 'needs_human'
                  ? 'bg-rose-500'
                  : 'bg-emerald-500'
            }`}
          />
          <div className="flex-1">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-semibold text-zinc-950">
                {step.label}
              </p>
              <div className="flex items-center gap-1.5">
                {(step.status === 'in_progress' ||
                  step.status === 'querying') && <ThinkingDots />}
                <span
                  className={`rounded-lg border px-2 py-0.5 text-xs font-semibold ${statusClasses(
                    step.status as AgentStatus
                  )}`}
                >
                  {step.status}
                </span>
              </div>
            </div>
            <p className="mt-1 text-sm leading-5 text-zinc-600">
              {step.detail}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}

function LiveContextPanel({
  context,
  status,
}: {
  context: Record<string, unknown>;
  status: string;
}) {
  const [showJson, setShowJson] = useState(false);
  const intent = String(context.intent ?? '—');
  const urgency = Number(context.urgency ?? 0);
  const currentNode = String(context.current_node ?? context.last_node ?? '—');
  const resolution = getRecord(context.resolution);
  const jsonText = useMemo(() => JSON.stringify(context, null, 2), [context]);

  return (
    <section className="rounded-lg border border-zinc-200 bg-white">
      <div className="border-b border-zinc-200 p-4">
        <h2 className="text-base font-semibold text-zinc-950">Live Context</h2>
      </div>
      <div className="grid grid-cols-3 border-b border-zinc-200 text-center">
        <div className="p-3">
          <p className="text-[10px] font-bold text-zinc-400 uppercase">
            Intent
          </p>
          <p className="mt-1 text-sm font-bold text-zinc-950">{intent}</p>
        </div>
        <div className="border-x border-zinc-200 p-3">
          <p className="text-[10px] font-bold text-zinc-400 uppercase">Node</p>
          <p className="mt-1 text-sm font-bold text-zinc-950 capitalize">
            {currentNode}
          </p>
        </div>
        <div className="p-3">
          <p className="text-[10px] font-bold text-zinc-400 uppercase">
            Urgency
          </p>
          <p
            className={`mt-1 text-sm font-bold ${urgency >= 4 ? 'text-rose-600' : urgency >= 3 ? 'text-amber-600' : 'text-zinc-950'}`}
          >
            {urgency}/5
          </p>
        </div>
      </div>

      {/* Resolution section */}
      {resolution && (
        <div className="border-b border-zinc-200 p-4">
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="text-[10px] font-bold text-zinc-400 uppercase">
              Resolution
            </p>
            <span
              className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold ${statusClasses(status as AgentStatus)}`}
            >
              {status}
            </span>
          </div>
          <div className="space-y-2 rounded-md bg-zinc-50 p-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-zinc-500">Action</span>
              <span className="font-bold text-zinc-950">
                {String(resolution.action ?? '—')}
              </span>
            </div>
            {Number(resolution.amount ?? 0) > 0 && (
              <div className="flex items-center justify-between text-sm">
                <span className="text-zinc-500">Amount</span>
                <span className="font-bold text-emerald-700">
                  ${Number(resolution.amount).toFixed(2)}
                </span>
              </div>
            )}
            <p className="text-xs leading-5 text-zinc-600 italic">
              {String(resolution.reason ?? '')}
            </p>
          </div>
        </div>
      )}

      {/* Collapsible JSON */}
      <div className="p-4">
        <button
          type="button"
          onClick={() => setShowJson(!showJson)}
          className="flex items-center gap-2 text-xs font-medium text-zinc-400 transition-colors hover:text-zinc-600"
        >
          <span
            className={`transition-transform ${showJson ? 'rotate-90' : ''}`}
          >
            ▶
          </span>
          Raw JSON
        </button>
        {showJson && (
          <pre className="mt-2 max-h-48 overflow-auto rounded-md bg-zinc-50 p-3 font-mono text-[11px] leading-5 text-zinc-600">
            {jsonText}
          </pre>
        )}
      </div>
    </section>
  );
}

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const [draft, setDraft] = useState('');
  const [activeTicketId, setActiveTicketId] = useState(tickets[0].id);

  // Multi-turn conversation state
  const [conversationId, setConversationId] = useState('');
  const [extractedEntities, setExtractedEntities] = useState<
    Record<string, unknown>
  >({});
  const [messageHistory, setMessageHistory] = useState<
    Array<{ type: string; content: string }>
  >([]);

  const { error, events, isStreaming, latestStatus, startStream, tokenText } =
    useAgentStream();
  const cleanText = tokenText.replace(/\n+/g, ' ');
  const activeTicket =
    tickets.find((t) => t.id === activeTicketId) || tickets[0];

  const streamedToolCalls: ToolCall[] = useMemo(
    () =>
      events
        .filter((event) => event.type === 'tool_invocation')
        .map((event) => ({
          id: `stream-${event.id}`,
          tool: String(event.data.tool_name ?? 'tool_invocation'),
          status: String(event.data.status ?? 'querying') as AgentStatus,
          detail: JSON.stringify(event.data.input ?? event.data),
          input: getRecord(event.data.input) ?? undefined,
          result: getRecord(event.data.result) ?? undefined,
        })),
    [events]
  );

  const doneEvent = [...events]
    .reverse()
    .find((event) => event.type === 'done');
  const liveContext =
    (doneEvent?.data.gathered_context as Record<string, unknown> | undefined) ??
    {};
  const liveResolution = getRecord(liveContext.resolution);
  const liveStatus = String(doneEvent?.data.resolution_status ?? '');

  const visibleToolCalls = [...streamedToolCalls, ...toolCalls];
  const streamedEvidence = streamedToolCalls.filter((call) => call.result);
  const evidenceToolCalls =
    streamedEvidence.length > 0
      ? streamedEvidence
      : toolCallsFromContext(liveContext);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = draft.trim();

    if (!trimmed) {
      return;
    }

    const nextId = messages.length + 1;
    const now = new Date().toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    });
    setMessages((current) => [
      ...current,
      {
        id: nextId,
        author: 'customer',
        body: trimmed,
        time: now,
      },
    ]);
    setToolCalls([]);
    setDraft('');

    const finalDoneData = await startStream({
      message: trimmed,
      conversation_id: conversationId,
      previous_messages: messageHistory,
      extracted_entities: extractedEntities,
    });

    // After stream completes, update the conversation state from the returned data
    if (finalDoneData) {
      // Update conversation ID
      if (finalDoneData.conversation_id) {
        setConversationId(finalDoneData.conversation_id);
      }
      // Update extracted entities
      if (finalDoneData.extracted_entities) {
        setExtractedEntities(finalDoneData.extracted_entities);
      }
      // Add the agent response to message history for next turn
      const lastMsg = finalDoneData.raw.messages as
        | Array<{ type: string; content: string }>
        | undefined;
      if (lastMsg && lastMsg.length > 0) {
        // Build updated history: add last human message + agent response
        const agentMsg = lastMsg[lastMsg.length - 1];
        setMessageHistory((current) => [
          ...current,
          { type: 'human', content: trimmed },
          { type: agentMsg.type, content: agentMsg.content },
        ]);

        // Add agent message to visible chat
        setMessages((current) => [
          ...current,
          {
            id: current.length + 1,
            author: 'agent',
            body: String(agentMsg.content),
            time: new Date().toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
            }),
          },
        ]);
      }
    }
  }

  return (
    <main className="min-h-screen bg-[#f7f8fa] text-zinc-950">
      <div className="mx-auto flex min-h-screen w-full max-w-7xl flex-col px-4 py-4 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-3 border-b border-zinc-200 pb-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs font-semibold tracking-[0.18em] text-zinc-500 uppercase">
              AssistFlow
            </p>
            <h1 className="mt-1 text-2xl font-semibold text-zinc-950">
              Support Console
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span
              className={`rounded-lg border px-3 py-1.5 font-medium ${isStreaming ? 'border-cyan-200 bg-cyan-50 text-cyan-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700'}`}
            >
              {isStreaming ? 'Streaming' : 'MCP ready'}
            </span>
            {liveStatus && (
              <span
                className={`rounded-lg border px-3 py-1.5 font-medium ${statusClasses(liveStatus as AgentStatus)}`}
              >
                {liveStatus}
              </span>
            )}
            {Object.keys(extractedEntities).length > 0 && (
              <span className="rounded-lg border border-violet-200 bg-violet-50 px-3 py-1.5 font-medium text-violet-700">
                {Object.keys(extractedEntities).length} entities tracked
              </span>
            )}
          </div>
        </header>

        <div className="grid flex-1 gap-4 py-4 lg:grid-cols-[minmax(0,1.35fr)_minmax(360px,0.8fr)]">
          <section className="flex min-h-[calc(100vh-120px)] flex-col overflow-hidden rounded-lg border border-zinc-200 bg-white">
            <div className="flex flex-col gap-3 border-b border-zinc-200 p-4 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-sm font-medium text-zinc-500">
                  Active ticket {activeTicket.id}
                </p>
                <h2 className="mt-1 text-lg font-semibold text-zinc-950">
                  {activeTicket.issue}
                </h2>
              </div>
              <div className="flex flex-wrap gap-2">
                <span className="rounded-lg border border-cyan-200 bg-cyan-50 px-2.5 py-1 text-xs font-semibold text-cyan-700">
                  {activeTicket.intent}
                </span>
                <span className="rounded-lg border border-rose-200 bg-rose-50 px-2.5 py-1 text-xs font-semibold text-rose-700">
                  Urgency {activeTicket.urgency}
                </span>
              </div>
            </div>

            <div className="grid min-h-0 flex-1 md:grid-cols-[220px_minmax(0,1fr)]">
              <aside className="border-b border-zinc-200 bg-zinc-50 p-3 md:border-r md:border-b-0">
                <div className="space-y-2">
                  {tickets.map((ticket) => (
                    <button
                      className={`w-full rounded-lg border p-3 text-left transition hover:bg-zinc-50 ${
                        activeTicketId === ticket.id
                          ? 'border-cyan-500 bg-white ring-2 ring-cyan-100'
                          : 'border-zinc-200 bg-white hover:border-zinc-300'
                      }`}
                      key={ticket.id}
                      onClick={() => setActiveTicketId(ticket.id)}
                      type="button"
                    >
                      <span
                        className={`block text-xs font-semibold ${
                          activeTicketId === ticket.id
                            ? 'text-cyan-600'
                            : 'text-zinc-500'
                        }`}
                      >
                        {ticket.id}
                      </span>
                      <span className="mt-1 block text-sm font-semibold text-zinc-950">
                        {ticket.customer}
                      </span>
                      <span className="mt-1 block text-xs text-zinc-600">
                        {ticket.issue}
                      </span>
                    </button>
                  ))}
                </div>
              </aside>

              <div className="flex min-h-0 min-w-0 flex-col">
                <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
                  {messages.length === 0 && !isStreaming && (
                    <div className="flex h-full items-center justify-center">
                      <div className="text-center">
                        <p className="text-lg font-semibold text-zinc-300">
                          No messages yet
                        </p>
                        <p className="mt-1 text-sm text-zinc-400">
                          Send a message to start a support session
                        </p>
                      </div>
                    </div>
                  )}

                  {messages.map((message) => (
                    <article
                      className={
                        message.author === 'agent'
                          ? 'ml-auto max-w-[82%] rounded-lg border border-cyan-200 bg-cyan-50 p-4'
                          : 'max-w-[82%] rounded-lg border border-zinc-200 bg-white p-4'
                      }
                      key={message.id}
                    >
                      <div className="mb-2 flex items-center justify-between gap-3 text-xs font-semibold text-zinc-500">
                        <span>
                          {message.author === 'agent'
                            ? 'AssistFlow Agent'
                            : activeTicket.customer}
                        </span>
                        <time>{message.time}</time>
                      </div>
                      <div className="text-sm leading-6 text-zinc-800">
                        <div className="prose prose-sm wax-m-none">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {message.body}
                          </ReactMarkdown>
                        </div>
                      </div>
                    </article>
                  ))}

                  {/* Active Streaming / Result Message */}
                  {(isStreaming || tokenText || error) && (
                    <article className="ml-auto max-w-[82%] rounded-lg border border-cyan-200 bg-cyan-50 p-4 shadow-sm ring-1 ring-cyan-100">
                      <div className="mb-2 flex items-center justify-between gap-3 text-xs font-semibold text-zinc-500">
                        <span className="flex items-center gap-2">
                          AssistFlow {isStreaming ? 'Mind' : 'Agent'}
                        </span>
                        <span className="flex items-center gap-1.5 rounded-full bg-cyan-100/50 px-2 py-0.5 text-cyan-700">
                          {isStreaming && <ThinkingDots />}
                          {isStreaming ? 'Processing' : 'Response'}
                        </span>
                      </div>
                      <div className="space-y-4">
                        <p className="text-sm leading-6 break-words whitespace-pre-wrap text-zinc-800">
                          {error ?? cleanText}
                          {isStreaming && !tokenText && (
                            <span className="animate-pulse-soft block text-zinc-500 italic">
                              Analyzing request and fetching data...
                            </span>
                          )}
                        </p>
                        <div className="space-y-2">
                          {evidenceToolCalls.map((call) => (
                            <ToolEvidence call={call} key={call.id} />
                          ))}
                        </div>
                        {!isStreaming && liveResolution && (
                          <ResolutionCard
                            resolution={liveResolution}
                            status={liveStatus}
                          />
                        )}
                      </div>
                    </article>
                  )}
                </div>

                <form
                  className="border-t border-zinc-200 bg-white p-4"
                  onSubmit={handleSubmit}
                >
                  <label className="sr-only" htmlFor="message">
                    Customer message
                  </label>
                  <div className="flex flex-col gap-3 sm:flex-row">
                    <textarea
                      className="min-h-20 flex-1 resize-none rounded-lg border border-zinc-300 px-3 py-2 text-sm leading-6 transition outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100"
                      id="message"
                      onChange={(event) => setDraft(event.target.value)}
                      placeholder="Type a customer update or internal note..."
                      value={draft}
                    />
                    <button
                      className="h-11 rounded-lg bg-zinc-950 px-4 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:bg-zinc-300"
                      disabled={!draft.trim() || isStreaming}
                      type="submit"
                    >
                      {isStreaming ? 'Processing...' : 'Send'}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </section>

          <aside className="flex min-h-[calc(100vh-120px)] flex-col gap-4">
            <LiveContextPanel context={liveContext} status={liveStatus} />

            <section className="rounded-lg border border-zinc-200 bg-zinc-50 p-4">
              <div className="mb-3">
                <h2 className="text-base font-semibold text-zinc-950">
                  Agent Activity
                </h2>
              </div>
              <AgentActivity
                isStreaming={isStreaming}
                latestStatus={latestStatus}
                toolCalls={visibleToolCalls}
                resolutionStatus={liveStatus || 'resolved'}
              />
            </section>

            <section className="flex min-h-0 flex-1 flex-col rounded-lg border border-zinc-200 bg-white">
              <div className="border-b border-zinc-200 p-4">
                <h2 className="text-base font-semibold text-zinc-950">
                  Tool Calls
                </h2>
              </div>
              <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
                {visibleToolCalls.length === 0 && (
                  <p className="text-sm text-zinc-400 italic">
                    No tool calls yet
                  </p>
                )}
                {visibleToolCalls.map((call) => (
                  <article
                    className="rounded-lg border border-zinc-200 p-3"
                    key={call.id}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <h3 className="text-sm font-semibold text-zinc-950">
                        {call.tool}
                      </h3>
                      <span
                        className={`rounded-lg border px-2 py-1 text-xs font-semibold ${statusClasses(
                          call.status
                        )}`}
                      >
                        {call.status}
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-5 text-zinc-600">
                      {call.detail}
                    </p>
                  </article>
                ))}
              </div>
            </section>
          </aside>
        </div>
      </div>
    </main>
  );
}
