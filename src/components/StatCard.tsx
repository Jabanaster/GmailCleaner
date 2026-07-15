import React from "react";

interface StatCardProps {
  accent: string;
  icon: React.ReactNode;
  label: string;
  value: string | number;
  iconColor: string;
  glowClass: string;
}

export function StatCard({
  accent,
  icon,
  label,
  value,
  iconColor,
  glowClass,
}: StatCardProps) {
  return (
    <div className={`stat-card ${accent} group hover:${glowClass}`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{label}</p>
          <p className="mt-1.5 text-2xl font-bold text-foreground tabular-nums">{value}</p>
        </div>
        <div className={`rounded-xl p-2 bg-muted/60 ${iconColor} transition-transform group-hover:scale-110 duration-200`}>
          {icon}
        </div>
      </div>
    </div>
  );
}
