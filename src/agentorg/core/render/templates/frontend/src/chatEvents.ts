import type { RunEvent } from './api';

// What a chat surface does with each kind of run stream event.
export interface ChatSink {
  appendText: (text: string) => void;
  toolStarted: (name: string) => void;
  toolFinished: () => void;
  approvalRequested: (approvalId: string, tool: string) => void;
  approvalDecided: () => void;
  finish: (status: string, output: unknown, failureReason: unknown) => void;
}

export function applyRunEvent(name: string, data: RunEvent, sink: ChatSink): void {
  if (name === 'text' && typeof data.text === 'string') sink.appendText(data.text);
  else if (name === 'tool_call' && typeof data.name === 'string') sink.toolStarted(data.name);
  else if (name === 'tool_result') sink.toolFinished();
  else if (name === 'approval_requested') sink.approvalRequested(String(data.approval_id), String(data.tool));
  else if (name === 'approval_decided') sink.approvalDecided();
  else if (name === 'end') sink.finish(String(data.status), data.output, data.failure_reason);
}

// The text shown when a run ends: its output when nothing streamed, plus the failure or refusal reason.
export function finalText(streamed: string, status: string, output: unknown, failureReason: unknown): string {
  const outputText = typeof output === 'string' ? output : output == null ? '' : '```json\n' + JSON.stringify(output, null, 2) + '\n```';
  if (status === 'refused') return outputText;
  const body = streamed || outputText;
  return status === 'failed' ? `${body}\n\n_Run failed: ${String(failureReason ?? 'error')}_` : body;
}
