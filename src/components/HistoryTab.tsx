import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { History, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import type { ScanHistory, ScanRun } from "@/types";

interface HistoryTabProps {
  history: ScanHistory | null;
}

export function HistoryTab({ history }: HistoryTabProps) {
  if (!history || history.history.length === 0) {
    return (
      <Card className="border-border/60">
        <CardContent className="py-16 text-center text-muted-foreground">
          <History className="mx-auto mb-3 h-10 w-10 opacity-30" />
          <p className="text-sm font-medium">No scan history yet</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-border/60 shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Scan History</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {history.history.map((run) => (
            <HistoryRow key={run.id} run={run} />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function HistoryRow({ run }: { run: ScanRun }) {
  const isCompleted = run.status === "completed";
  const isFailed = run.status === "failed";

  const statusIcon = isCompleted
    ? <CheckCircle2 className="h-4 w-4 text-green-500 flex-shrink-0" />
    : isFailed
      ? <XCircle className="h-4 w-4 text-destructive flex-shrink-0" />
      : <Loader2 className="h-4 w-4 animate-spin text-primary flex-shrink-0" />;

  const dateStr = run.started_at ? new Date(run.started_at).toLocaleString() : "—";

  return (
    <div className="flex items-start gap-3 rounded-xl border border-border/50 p-3.5">
      <div className="mt-0.5">{statusIcon}</div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium text-foreground">{dateStr}</span>
          <Badge
            variant={isCompleted ? "default" : isFailed ? "destructive" : "secondary"}
            className="text-xs"
          >
            {run.status}
          </Badge>
          {run.dry_run && (
            <Badge variant="outline" className="text-xs border-primary/30 text-primary bg-primary/5">
              preview
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-3 mt-1.5 text-xs text-muted-foreground">
          <span>{run.total_scanned} scanned</span>
          <span className="text-destructive font-medium">{run.total_trashed} trashed</span>
          <span className="text-green-600 dark:text-green-400 font-medium">{run.total_labeled} sorted</span>
        </div>
        {run.error_message && (
          <p className="text-xs text-destructive mt-1">{run.error_message}</p>
        )}
      </div>
    </div>
  );
}
