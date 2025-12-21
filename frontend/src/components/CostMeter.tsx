/**
 * Cost meter component displaying running LLM costs.
 */

'use client';

import { useEffect, useState } from 'react';

export interface CostMeterProps {
  /** Total cost accumulated */
  totalCost: number;
  /** Optional className for styling */
  className?: string;
}

export function CostMeter({ totalCost, className = '' }: CostMeterProps) {
  const [displayCost, setDisplayCost] = useState(totalCost);

  // Animate cost changes
  useEffect(() => {
    if (displayCost === totalCost) return;

    const diff = totalCost - displayCost;
    const steps = 20;
    const stepValue = diff / steps;
    let currentStep = 0;

    const interval = setInterval(() => {
      currentStep++;
      if (currentStep >= steps) {
        setDisplayCost(totalCost);
        clearInterval(interval);
      } else {
        setDisplayCost((prev) => prev + stepValue);
      }
    }, 20);

    return () => clearInterval(interval);
  }, [totalCost, displayCost]);

  // Format cost as dollars with appropriate precision
  const formatCost = (cost: number): string => {
    if (cost < 0.01) {
      return `$${cost.toFixed(4)}`;
    }
    if (cost < 1) {
      return `$${cost.toFixed(3)}`;
    }
    return `$${cost.toFixed(2)}`;
  };

  // Color based on cost
  const getCostColor = (): string => {
    if (totalCost < 0.01) return 'text-green-600 dark:text-green-400';
    if (totalCost < 0.1) return 'text-yellow-600 dark:text-yellow-400';
    return 'text-orange-600 dark:text-orange-400';
  };

  return (
    <div
      className={`flex items-center gap-2 px-3 py-1.5 bg-zinc-100 dark:bg-zinc-800 rounded-full text-sm ${className}`}
      data-testid="cost-meter"
      title="Total cost this session (resets on page reload)"
    >
      <span className="text-zinc-500 dark:text-zinc-400">This Session:</span>
      <span className={`font-mono font-medium ${getCostColor()}`}>
        {formatCost(displayCost)}
      </span>
    </div>
  );
}
