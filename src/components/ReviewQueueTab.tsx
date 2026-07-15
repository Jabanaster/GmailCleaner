import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Trash2, Tag, XCircle, Inbox } from "lucide-react";
import type { EmailClassification } from "@/types";
import { CATEGORY_COLORS, CATEGORY_LABELS, CATEGORY_ICONS } from "@/lib/constants";

interface ReviewQueueTabProps {
  classifications: EmailClassification[];
}

export function ReviewQueueTab({ classifications }: ReviewQueueTabProps) {
  if (classifications.length === 0) {
    return (
      <Card className="border-border/60">
        <CardContent className="py-16 text-center text-muted-foreground">
          <Tag className="mx-auto mb-3 h-10 w-10 opacity-30" />
          <p className="text-sm font-medium">No classifications yet</p>
          <p className="text-xs mt-1">Run a scan to see processed emails here.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-border/60 shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          Recent Classifications
          <Badge variant="secondary" className="ml-auto">{classifications.length}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[520px] pr-3">
          <div className="space-y-2">
            {classifications.map((cls) => (
              <ClassificationRow key={cls.message_id} cls={cls} />
            ))}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}

function ClassificationRow({ cls }: { cls: EmailClassification }) {
  const colors = cls.is_crap
    ? { bg: "hsl(0 84% 95%)", text: "hsl(0 84% 40%)", bar: "hsl(0 84% 60%)" }
    : cls.category
      ? CATEGORY_COLORS[cls.category] || { bg: "hsl(220 50% 94%)", text: "hsl(220 50% 40%)", bar: "hsl(220 50% 55%)" }
      : null;

  const actionIcon = cls.action_taken === "trashed"
    ? <Trash2 className="h-3.5 w-3.5 text-destructive flex-shrink-0" />
    : cls.action_taken === "labeled"
      ? <Tag className="h-3.5 w-3.5 text-green-500 flex-shrink-0" />
      : cls.action_taken?.includes("failed")
        ? <XCircle className="h-3.5 w-3.5 text-destructive flex-shrink-0" />
        : <Inbox className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />;

  return (
    <div className="flex items-start gap-3 rounded-xl border border-border/50 p-3 hover:bg-muted/40 transition-colors duration-150">
      <div className="mt-0.5">{actionIcon}</div>
      <div className="flex-1 min-w-0">
        <p className="font-medium text-sm text-foreground truncate">{cls.subject || "(no subject)"}</p>
        <p className="text-xs text-muted-foreground truncate mt-0.5">{cls.sender}</p>
        <div className="mt-1.5 flex items-center gap-2 flex-wrap">
          {cls.is_crap ? (
            <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium" style={{ background: "hsl(0 84% 95%)", color: "hsl(0 84% 40%)" }}>
              🗑️ Junk
            </span>
          ) : cls.category && colors ? (
            <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium" style={{ background: colors.bg, color: colors.text }}>
              {CATEGORY_ICONS[cls.category] || "📧"} {CATEGORY_LABELS[cls.category] || cls.category}
            </span>
          ) : null}
          {cls.crap_reason && (
            <span className="text-xs text-muted-foreground">{cls.crap_reason}</span>
          )}
          {cls.confidence > 0 && (
            <span className="text-xs text-muted-foreground ml-auto">{Math.round(cls.confidence * 100)}%</span>
          )}
        </div>
      </div>
    </div>
  );
}
