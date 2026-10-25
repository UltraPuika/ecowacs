import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { api, ApiError } from "./api";
import { Icon } from "./icons";
import { T } from "./lv";
import type { CommandResult } from "./types";

export interface Feedback {
  kind: "pending" | "ok" | "warn" | "error";
  text: string;
}

const KIND: Record<CommandResult["status"], Feedback["kind"]> = {
  confirmed: "ok",
  done: "ok",
  sent: "warn",
  failed: "error",
  rejected: "error",
};

/** Runs commands one at a time from this screen and reports honest feedback. */
export function useCommand() {
  const [busy, setBusy] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const busyRef = useRef(false);
  const timer = useRef<number | undefined>(undefined);

  const run = useCallback(async (name: string, params: Record<string, unknown> = {}) => {
    if (busyRef.current) return null; // ignore double taps
    busyRef.current = true;
    setBusy(name);
    setFeedback({ kind: "pending", text: T.sending });
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(
      () => setFeedback({ kind: "pending", text: T.waiting }),
      1500,
    );
    try {
      const result = await api.command(name, params);
      setFeedback({ kind: KIND[result.status], text: result.message });
      return result;
    } catch (err) {
      setFeedback({
        kind: "error",
        text: err instanceof ApiError ? err.message : "Neizdevās nosūtīt komandu.",
      });
      return null;
    } finally {
      window.clearTimeout(timer.current);
      busyRef.current = false;
      setBusy(null);
    }
  }, []);

  useEffect(() => () => window.clearTimeout(timer.current), []);
  return { run, busy, feedback, setFeedback };
}

export function FeedbackBox({ feedback }: { feedback: Feedback | null }) {
  if (!feedback) return null;
  return (
    <div className={`feedback feedback-${feedback.kind}`} role="status" aria-live="polite">
      {feedback.kind === "pending" ? (
        <span className="spinner" aria-hidden="true" />
      ) : (
        <Icon name={feedback.kind === "ok" ? "check" : "alert"} className="feedback-icon" />
      )}
      {feedback.text}
    </div>
  );
}

interface BigButtonProps {
  label: string;
  onClick: () => void;
  variant?: "primary" | "secondary" | "danger" | "plain";
  busy?: boolean;
  disabled?: boolean;
  /** Name of an icon from icons.tsx (decorative, aria-hidden). */
  icon?: string;
}

export function BigButton({ label, onClick, variant = "primary", busy, disabled, icon }: BigButtonProps) {
  return (
    <button
      type="button"
      className={`big-button big-${variant}`}
      onClick={onClick}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
    >
      {busy ? (
        <span className="spinner" aria-hidden="true" />
      ) : (
        icon && <Icon name={icon} className="big-button-icon" />
      )}
      <span>{label}</span>
    </button>
  );
}

interface ConfirmProps {
  title: string;
  text: string;
  confirmLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({ title, text, confirmLabel = T.yes, danger, onConfirm, onCancel }: ConfirmProps) {
  const ref = useRef<HTMLButtonElement>(null);
  useEffect(() => ref.current?.focus(), []);
  return (
    <div className="dialog-backdrop" role="presentation" onClick={onCancel}>
      <div
        className="dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="dialog-title">{title}</h2>
        <p>{text}</p>
        <div className="dialog-buttons">
          <button type="button" className="big-button big-secondary" ref={ref} onClick={onCancel}>
            {T.cancel}
          </button>
          <button
            type="button"
            className={`big-button ${danger ? "big-danger" : "big-primary"}`}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export function Card({ title, children, className = "" }: { title?: string; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {title && <h2>{title}</h2>}
      {children}
    </section>
  );
}

export function Toggle({
  label,
  help,
  checked,
  disabled,
  onChange,
}: {
  label: string;
  help?: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="toggle">
      <input
        type="checkbox"
        role="switch"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="toggle-text">
        <span className="toggle-label">{label}</span>
        {help && <span className="help">{help}</span>}
      </span>
    </label>
  );
}
