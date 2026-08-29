"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";

import type { GameExplanation } from "../game-terms";

type TooltipPosition = {
  left: number;
  top: number;
  side: "above" | "below";
};

export function GameTooltip({
  explanation,
  children,
  className = "",
  focusable = true,
}: {
  explanation: GameExplanation;
  children: ReactNode;
  className?: string;
  focusable?: boolean;
}) {
  const anchorRef = useRef<HTMLSpanElement | null>(null);
  const descriptionId = useId();
  const [visible, setVisible] = useState(false);
  const [position, setPosition] = useState<TooltipPosition | null>(null);

  useEffect(() => {
    if (!visible) return;
    const updatePosition = () => {
      const anchor = anchorRef.current;
      if (!anchor) return;
      const rect = anchor.getBoundingClientRect();
      const panelWidth = Math.min(286, window.innerWidth - 24);
      const left = Math.max(12, Math.min(
        rect.left + rect.width / 2 - panelWidth / 2,
        window.innerWidth - panelWidth - 12,
      ));
      const side = rect.top >= 170 ? "above" : "below";
      setPosition({
        left,
        top: side === "above" ? rect.top - 12 : rect.bottom + 12,
        side,
      });
    };
    updatePosition();
    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);
    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
    };
  }, [visible]);

  const hide = () => setVisible(false);

  return (
    <span
      ref={anchorRef}
      className={`game-tooltip-anchor ${className}`.trim()}
      role={focusable ? "button" : undefined}
      tabIndex={focusable ? 0 : undefined}
      aria-describedby={descriptionId}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={hide}
      onFocus={() => setVisible(true)}
      onBlur={hide}
      onClick={focusable ? () => setVisible(true) : undefined}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          hide();
        } else if (focusable && (event.key === "Enter" || event.key === " ")) {
          event.preventDefault();
          setVisible(true);
        }
      }}
    >
      {children}
      <span id={descriptionId} className="sr-only">
        {explanation.title}：{explanation.description} {explanation.detail ?? ""}
      </span>
      {visible && position && createPortal(
        <span
          role="tooltip"
          className={`game-tooltip-panel tooltip-${position.side}`}
          style={{ left: position.left, top: position.top }}
        >
          <strong>{explanation.title}</strong>
          <span>{explanation.description}</span>
          {explanation.detail && <small>{explanation.detail}</small>}
        </span>,
        document.body,
      )}
    </span>
  );
}
