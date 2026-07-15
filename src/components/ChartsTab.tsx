import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { BarChart3 } from "lucide-react";
import type { CategoryBreakdown } from "@/types";
import { CATEGORY_COLORS, CATEGORY_LABELS, CATEGORY_ICONS } from "@/lib/constants";

interface ChartsTabProps {
  categories: CategoryBreakdown | null;
}

export function ChartsTab({ categories }: ChartsTabProps) {
  if (!categories || (categories.categories.length === 0 && categories.crap_count === 0)) {
    return (
      <Card className="border-border/60">
        <CardContent className="py-16 text-center text-muted-foreground">
          <BarChart3 className="mx-auto mb-3 h-10 w-10 opacity-30" />
          <p className="text-sm font-medium">No scan data yet</p>
          <p className="text-xs mt-1">Run a scan to see your email breakdown by category.</p>
        </CardContent>
      </Card>
    );
  }

  const allCats = [
    ...categories.categories.map((c) => ({ ...c, isCrap: false })),
    ...(categories.crap_count > 0 ? [{ category: "crap", count: categories.crap_count, isCrap: true }] : []),
  ];
  const total = allCats.reduce((sum, c) => sum + c.count, 0);
  const maxCount = Math.max(...allCats.map((c) => c.count), 1);

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card className="border-border/60 shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Category Breakdown</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {allCats.map((cat) => {
            const isCrap = cat.isCrap;
            const label = isCrap ? "Trashed (Junk)" : CATEGORY_LABELS[cat.category] || cat.category;
            const icon = isCrap ? "🗑️" : CATEGORY_ICONS[cat.category] || "📧";
            const colors = isCrap
              ? { bg: "hsl(0 84% 95%)", text: "hsl(0 84% 40%)", bar: "hsl(0 84% 60%)" }
              : CATEGORY_COLORS[cat.category] || { bg: "hsl(220 50% 94%)", text: "hsl(220 50% 40%)", bar: "hsl(220 50% 55%)" };
            const pct = (cat.count / maxCount) * 100;
            const share = total > 0 ? Math.round((cat.count / total) * 100) : 0;

            return (
              <div key={cat.category} className="space-y-1.5">
                <div className="flex items-center justify-between text-sm">
                  <span className="flex items-center gap-2 font-medium">
                    <span
                      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium"
                      style={{ background: colors.bg, color: colors.text }}
                    >
                      {icon} {label}
                    </span>
                  </span>
                  <span className="font-semibold text-foreground tabular-nums">
                    {cat.count}
                    <span className="ml-1 text-xs text-muted-foreground font-normal">({share}%)</span>
                  </span>
                </div>
                <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-700 ease-out"
                    style={{ width: `${pct}%`, background: colors.bar }}
                  />
                </div>
              </div>
            );
          })}
        </CardContent>
      </Card>

      <Card className="border-border/60 shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Summary</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between p-3 rounded-xl bg-muted/50 border border-border/50">
              <span className="text-sm font-medium text-muted-foreground">Total classified</span>
              <span className="text-xl font-bold text-foreground tabular-nums">{total.toLocaleString()}</span>
            </div>
            <div className="flex items-center justify-between p-3 rounded-xl bg-destructive/10 border border-destructive/20">
              <span className="text-sm font-medium text-destructive/80">🗑️ Junk trashed</span>
              <span className="text-xl font-bold text-destructive tabular-nums">{categories.crap_count.toLocaleString()}</span>
            </div>
            <div className="flex items-center justify-between p-3 rounded-xl bg-green-500/10 border border-green-500/20">
              <span className="text-sm font-medium text-green-700 dark:text-green-400">🏷️ Categories assigned</span>
              <span className="text-xl font-bold text-green-600 dark:text-green-400 tabular-nums">
                {categories.categories.reduce((s, c) => s + c.count, 0).toLocaleString()}
              </span>
            </div>
          </div>
          <Separator />
          <p className="text-xs text-muted-foreground">
            Classification by Gemini AI. Crap = promotional junk, spam, and low-value automated email.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
