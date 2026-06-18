'use client';

import { FormEvent, useMemo, useState } from 'react';
import { useAgentStream } from './hooks/useAgentStream';

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

const initialMessages: ChatMessage[] = [
  {
    id: 1,
    author: 'customer',
    body: 'I was charged twice for transaction_id txn_123 after my airport ride.',
    time: '09:41',
  },
  {
    id: 2,
    author: 'agent',
    body:
      'I found a billing intent, checked the transaction record, and queued ' +
      'the refund policy validation.',
    time: '09:42',
  },
];

const initialToolCalls: ToolCall[] = [
  {
    id: 'router',
    tool: 'RouterAgent',
    status: 'resolved',
    detail: 'Intent BILLING, urgency 3',
  },
  {
    id: 'billing',
    tool: 'verify_transaction_status',
    status: 'resolved',
    detail: 'txn_123 returned SUCCESS for $25.50',
    input: { transaction_id: 'txn_123' },
    result: {
      data: {
        transaction_id: 'txn_123',
        status: 'SUCCESS',
        amount: 25.5,
        currency: 'USD',
        payment_method: 'Credit Card',
      },
    },
  },
  {
    id: 'guardrail',
    tool: 'GuardrailNode',
    status: 'review',
    detail: 'Refund under policy limit',
  },
];

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

const contextSnapshot = {
  intent: 'BILLING',
  urgency: 3,
  current_node: 'guardrail',
  billing: {
    tool: 'verify_transaction_status',
    input: { transaction_id: 'txn_123' },
    result: {
      data: {
        transaction_id: 'txn_123',
        status: 'SUCCESS',
        amount: 25.5,
        currency: 'USD',
        payment_method: 'Credit Card',
      },
    },
  },
  resolution: {
    action: 'ISSUE_REFUND',
    amount: 12.5,
    reason: 'Duplicate charge detected.',
  },
};

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

function getToolData(result?: Record<string, unknown>): Record<string, unknown> {
  const data = getRecord(result?.data);
  return data ?? result ?? {};
}

function summarizeToolCall(call: ToolCall) {
  const data = getToolData(call.result);

  if (call.tool === 'verify_transaction_status') {
    return `${String(data.transaction_id ?? 'transaction')} returned ${String(
      data.status ?? call.status,
    )}`;
  }

  if (call.tool === 'get_ride_route_deviation') {
    return `${String(data.ride_id ?? 'ride')} deviation score ${String(
      data.deviation_score ?? 'pending',
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
      <section className="mt-3 rounded-lg border border-zinc-200 bg-white p-3">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold text-zinc-950">
            Transaction Evidence
          </h3>
          <span
            className={`rounded-lg border px-2 py-1 text-xs font-semibold ${statusClasses(
              call.status,
            )}`}
          >
            {String(data.status ?? call.status)}
          </span>
        </div>
        <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
          <div>
            <dt className="text-xs font-medium text-zinc-500">Transaction</dt>
            <dd className="mt-1 font-semibold text-zinc-950">
              {String(
                data.transaction_id ?? call.input?.transaction_id ?? 'n/a',
              )}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-zinc-500">Amount</dt>
            <dd className="mt-1 font-semibold text-zinc-950">
              {String(data.currency ?? 'USD')} {String(data.amount ?? '0.00')}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-zinc-500">Method</dt>
            <dd className="mt-1 font-semibold text-zinc-950">
              {String(data.payment_method ?? 'Unknown')}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-zinc-500">Decision Input</dt>
            <dd className="mt-1 font-semibold text-zinc-950">
              Refund policy check
            </dd>
          </div>
        </dl>
      </section>
    );
  }

  if (call.tool === 'get_ride_route_deviation') {
    const score = Number(data.deviation_score ?? 0);
    const percent = Math.min(Math.max(score, 0), 1) * 100;

    return (
      <section className="mt-3 rounded-lg border border-zinc-200 bg-white p-3">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold text-zinc-950">
            Route Telemetry
          </h3>
          <span
            className={`rounded-lg border px-2 py-1 text-xs font-semibold ${statusClasses(
              call.status,
            )}`}
          >
            {String(data.status ?? call.status)}
          </span>
        </div>
        <div className="mt-3 rounded-lg border border-zinc-200 bg-zinc-50 p-3">
          <div className="relative h-24 overflow-hidden rounded-md bg-white">
            <div className="absolute top-1/2 left-4 h-1 w-[78%] -translate-y-1/2 bg-zinc-300" />
            <div
              className="absolute top-[55%] left-4 h-1 rounded-full bg-cyan-500"
              style={{ width: `${Math.max(percent, 12)}%` }}
            />
            <div className="absolute top-5 left-4 h-3 w-3 rounded-full bg-emerald-500" />
            <div className="absolute right-5 bottom-5 h-3 w-3 rounded-full bg-rose-500" />
          </div>
          <div className="mt-3 flex items-center justify-between text-sm">
            <span className="font-medium text-zinc-600">Deviation score</span>
            <span className="font-semibold text-zinc-950">{score.toFixed(2)}</span>
          </div>
        </div>
        <p className="mt-3 text-sm leading-5 text-zinc-600">
          {String(data.details ?? 'Route data is ready for review.')}
        </p>
      </section>
    );
  }

  return null;
}

function AgentActivity({
  isStreaming,
  latestStatus,
  toolCalls,
}: {
  isStreaming: boolean;
  latestStatus?: Record<string, unknown>;
  toolCalls: ToolCall[];
}) {
  const hasToolQuery = toolCalls.some((call) => call.status === 'querying');
  const steps = [
    {
      label: 'Thinking',
      status: isStreaming ? 'in_progress' : 'resolved',
      detail: 'Router is classifying the customer message.',
    },
    {
      label: 'Querying Database',
      status: hasToolQuery ? 'querying' : 'resolved',
      detail: 'Specialist agents call billing or telemetry MCP tools.',
    },
    {
      label: 'Policy Check',
      status: String(latestStatus?.status ?? 'resolved') as AgentStatus,
      detail: `Current node: ${String(latestStatus?.node ?? 'guardrail')}`,
    },
  ];

  return (
    <div className="space-y-2">
      {steps.map((step) => (
        <div
          className="flex items-start gap-3 rounded-lg border border-zinc-200 bg-white p-3"
          key={step.label}
        >
          <span
            className={`mt-1 h-2.5 w-2.5 rounded-full ${
              step.status === 'in_progress' || step.status === 'querying'
                ? 'bg-cyan-500'
                : 'bg-emerald-500'
            }`}
          />
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-semibold text-zinc-950">{step.label}</p>
              <span
                className={`rounded-lg border px-2 py-0.5 text-xs font-semibold ${statusClasses(
                  step.status as AgentStatus,
                )}`}
              >
                {step.status}
              </span>
            </div>
            <p className="mt-1 text-sm leading-5 text-zinc-600">{step.detail}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function Home() {
  const [messages, setMessages] = useState(initialMessages);
  const [toolCalls, setToolCalls] = useState(initialToolCalls);
  const [draft, setDraft] = useState('');
  const {
    error,
    events,
    isStreaming,
    latestStatus,
    startStream,
    tokenText,
  } = useAgentStream();

  const activeTicket = tickets[0];
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
    [events],
  );
  const doneEvent = [...events].reverse().find((event) => event.type === 'done');
  const liveContext =
    (doneEvent?.data.gathered_context as Record<string, unknown> | undefined) ??
    contextSnapshot;
  const jsonContext = useMemo(
    () => JSON.stringify(liveContext, null, 2),
    [liveContext],
  );
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
    setMessages((current) => [
      ...current,
      {
        id: nextId,
        author: 'customer',
        body: trimmed,
        time: 'now',
      },
      {
        id: nextId + 1,
        author: 'agent',
        body:
          'RouterAgent is ready to classify this request and hand it to the ' +
          'correct specialist.',
        time: 'now',
      },
    ]);
    setToolCalls((current) => [
      {
        id: `pending-${nextId}`,
        tool: 'RouterAgent',
        status: 'querying',
        detail: 'Awaiting backend classification',
      },
      ...current,
    ]);
    setDraft('');
    await startStream({ message: trimmed });
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
            <span className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-1.5 font-medium text-emerald-700">
              {isStreaming ? 'Streaming' : 'MCP ready'}
            </span>
            <span className="rounded-lg border border-zinc-200 bg-white px-3 py-1.5 font-medium text-zinc-700">
              3 open tickets
            </span>
            <span className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-1.5 font-medium text-amber-700">
              1 needs review
            </span>
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
                      className="w-full rounded-lg border border-zinc-200 bg-white p-3 text-left transition hover:border-zinc-300 hover:bg-zinc-50"
                      key={ticket.id}
                      type="button"
                    >
                      <span className="block text-xs font-semibold text-zinc-500">
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

              <div className="flex min-h-0 flex-col">
                <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
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
                      <p className="text-sm leading-6 text-zinc-800">
                        {message.body}
                      </p>
                    </article>
                  ))}
                  {(tokenText || error) && (
                    <article className="ml-auto max-w-[82%] rounded-lg border border-cyan-200 bg-cyan-50 p-4">
                      <div className="mb-2 flex items-center justify-between gap-3 text-xs font-semibold text-zinc-500">
                        <span>AssistFlow Stream</span>
                        <span>{isStreaming ? 'live' : 'done'}</span>
                      </div>
                      <p className="whitespace-pre-line text-sm leading-6 text-zinc-800">
                        {error ?? tokenText}
                      </p>
                      {evidenceToolCalls.map((call) => (
                        <ToolEvidence call={call} key={call.id} />
                      ))}
                    </article>
                  )}
                  {!tokenText &&
                    !error &&
                    evidenceToolCalls.map((call) => (
                      <article
                        className="ml-auto max-w-[82%] rounded-lg border border-cyan-200 bg-cyan-50 p-4"
                        key={call.id}
                      >
                        <div className="mb-2 flex items-center justify-between gap-3 text-xs font-semibold text-zinc-500">
                          <span>AssistFlow Evidence</span>
                          <span>{call.tool}</span>
                        </div>
                        <ToolEvidence call={call} />
                      </article>
                    ))}
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
                      className="min-h-20 flex-1 resize-none rounded-lg border border-zinc-300 px-3 py-2 text-sm leading-6 outline-none transition focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100"
                      id="message"
                      onChange={(event) => setDraft(event.target.value)}
                      placeholder="Type a customer update or internal note..."
                      value={draft}
                    />
                    <button
                      className="h-11 rounded-lg bg-zinc-950 px-4 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:bg-zinc-300"
                      disabled={!draft.trim()}
                      type="submit"
                    >
                      Send
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </section>

          <aside className="flex min-h-[calc(100vh-120px)] flex-col gap-4">
            <section className="rounded-lg border border-zinc-200 bg-white">
              <div className="border-b border-zinc-200 p-4">
                <h2 className="text-base font-semibold text-zinc-950">
                  Live Context
                </h2>
              </div>
              <div className="grid grid-cols-3 border-b border-zinc-200 text-center">
                <div className="p-3">
                  <p className="text-xs font-medium text-zinc-500">Intent</p>
                  <p className="mt-1 text-sm font-semibold text-zinc-950">
                    Billing
                  </p>
                </div>
                <div className="border-x border-zinc-200 p-3">
                  <p className="text-xs font-medium text-zinc-500">Node</p>
                  <p className="mt-1 text-sm font-semibold text-zinc-950">
                    {String(latestStatus?.node ?? 'Guardrail')}
                  </p>
                </div>
                <div className="p-3">
                  <p className="text-xs font-medium text-zinc-500">Action</p>
                  <p className="mt-1 text-sm font-semibold text-zinc-950">
                    Refund
                  </p>
                </div>
              </div>
              <pre className="max-h-64 overflow-auto p-4 font-mono text-xs leading-5 text-zinc-700">
                {jsonContext}
              </pre>
            </section>

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
              />
            </section>

            <section className="flex min-h-0 flex-1 flex-col rounded-lg border border-zinc-200 bg-white">
              <div className="border-b border-zinc-200 p-4">
                <h2 className="text-base font-semibold text-zinc-950">
                  Tool Calls
                </h2>
              </div>
              <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
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
                          call.status,
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
