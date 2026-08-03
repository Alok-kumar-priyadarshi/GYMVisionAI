/**
 * The AI coach conversation.
 *
 * The conversation identifier is generated once per mounted session and sent
 * with every message, which is how the backend scopes conversation memory.
 */

import { useEffect, useRef, useState } from "react";

import { Button, Card, PageHeader, Spinner } from "@/components/ui";
import { useChat } from "@/hooks/queries";
import { ApiError } from "@/services/api/client";

interface Turn {
  id: string;
  role: "user" | "assistant";
  content: string;
}

const SUGGESTIONS = [
  "How do I improve my push-up form?",
  "Why does my plan include so many squats?",
  "How often should I train as a beginner?",
];

export default function CoachPage() {
  const [conversationId] = useState(() => crypto.randomUUID());
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const chat = useChat();
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, chat.isPending]);

  function send(message: string) {
    const trimmed = message.trim();
    if (!trimmed || chat.isPending) return;

    setError(null);
    setDraft("");
    setTurns((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "user", content: trimmed },
    ]);

    chat.mutate(
      { conversationId, message: trimmed },
      {
        onSuccess: (reply) =>
          setTurns((current) => [
            ...current,
            {
              id: crypto.randomUUID(),
              role: "assistant",
              content: reply.response,
            },
          ]),
        onError: (cause) =>
          setError(
            cause instanceof ApiError
              ? cause.message
              : "The coach is unavailable right now.",
          ),
      },
    );
  }

  return (
    <>
      <PageHeader
        title="Coach"
        subtitle="Ask about technique, your plan or anything fitness related."
      />

      <Card className="flex h-[65vh] flex-col p-0">
        <div
          role="log"
          aria-live="polite"
          aria-label="Conversation"
          className="flex-1 space-y-4 overflow-y-auto p-5"
        >
          {turns.length === 0 && (
            <div className="py-8 text-center">
              <p className="text-sm text-ink-muted">
                Ask anything about your training.
              </p>
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => send(suggestion)}
                    className="rounded-full border border-line bg-white px-3 py-1.5 text-xs text-ink-muted hover:bg-surface-muted"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {turns.map((turn) => (
            <div
              key={turn.id}
              className={turn.role === "user" ? "flex justify-end" : "flex"}
            >
              <p
                className={[
                  "max-w-[85%] whitespace-pre-line rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
                  turn.role === "user"
                    ? "bg-brand-600 text-white"
                    : "bg-surface-muted text-ink",
                ].join(" ")}
              >
                <span className="sr-only">
                  {turn.role === "user" ? "You said: " : "Coach said: "}
                </span>
                {turn.content}
              </p>
            </div>
          ))}

          {chat.isPending && (
            <p className="flex items-center gap-2 text-sm text-ink-muted">
              <Spinner size="sm" /> The coach is thinking…
            </p>
          )}

          {error && (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          )}

          <div ref={endRef} />
        </div>

        <form
          className="flex gap-2 border-t border-line p-4"
          onSubmit={(event) => {
            event.preventDefault();
            send(draft);
          }}
        >
          <label htmlFor="coach-message" className="sr-only">
            Message
          </label>
          <input
            id="coach-message"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Ask your coach…"
            maxLength={2000}
            autoComplete="off"
            className="flex-1 rounded-lg border border-line bg-white px-3 py-2 text-sm text-ink placeholder:text-ink-muted"
          />
          <Button type="submit" disabled={!draft.trim()} loading={chat.isPending}>
            Send
          </Button>
        </form>
      </Card>

      <p className="mt-4 text-center text-xs text-ink-muted">
        GymVision gives educational fitness guidance, not medical advice.
      </p>
    </>
  );
}
