'use client';

import { useCallback, useMemo, useState } from 'react';

export type AgentStreamEventType =
  | 'token'
  | 'agent_status_change'
  | 'tool_invocation'
  | 'done';

export type AgentStreamEvent = {
  id: number;
  type: AgentStreamEventType;
  data: Record<string, unknown>;
};

type StreamRequest = {
  message: string;
  gathered_context?: Record<string, unknown>;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') ?? 'http://localhost:8000';

function parseSseFrame(frame: string): Omit<AgentStreamEvent, 'id'> | null {
  const eventLine = frame
    .split('\n')
    .find((line) => line.startsWith('event:'));
  const dataLine = frame
    .split('\n')
    .find((line) => line.startsWith('data:'));

  if (!eventLine || !dataLine) {
    return null;
  }

  const type = eventLine.replace('event:', '').trim() as AgentStreamEventType;
  const rawData = dataLine.replace('data:', '').trim();

  if (!['token', 'agent_status_change', 'tool_invocation', 'done'].includes(type)) {
    return null;
  }

  return {
    type,
    data: JSON.parse(rawData) as Record<string, unknown>,
  };
}

export function useAgentStream() {
  const [events, setEvents] = useState<AgentStreamEvent[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const latestStatus = useMemo(
    () =>
      [...events]
        .reverse()
        .find((event) => event.type === 'agent_status_change')?.data,
    [events],
  );

  const tokenText = useMemo(
    () =>
      events
        .filter((event) => event.type === 'token')
        .map((event) => String(event.data.content ?? ''))
        .join('\n'),
    [events],
  );

  const startStream = useCallback(async (request: StreamRequest) => {
    setEvents([]);
    setError(null);
    setIsStreaming(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/agents/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        },
        body: JSON.stringify({
          message: request.message,
          gathered_context: request.gathered_context ?? {},
        }),
      });

      if (!response.ok || !response.body) {
        throw new Error('Agent stream failed to start.');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        const frames = buffer.split('\n\n');
        buffer = frames.pop() ?? '';

        frames.forEach((frame) => {
          const parsed = parseSseFrame(frame);
          if (!parsed) {
            return;
          }

          setEvents((current) => [
            ...current,
            {
              id: current.length + 1,
              ...parsed,
            },
          ]);
        });

        if (done) {
          break;
        }
      }
    } catch (streamError) {
      setError(
        streamError instanceof Error
          ? streamError.message
          : 'Agent stream failed.',
      );
    } finally {
      setIsStreaming(false);
    }
  }, []);

  return {
    error,
    events,
    isStreaming,
    latestStatus,
    startStream,
    tokenText,
  };
}
