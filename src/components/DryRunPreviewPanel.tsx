import type { EmailClassification } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { AlertCircle, CheckCircle } from "lucide-react";

interface DryRunPreviewPanelProps {
  classifications: EmailClassification[];
  isDryRun: boolean;
}

export function DryRunPreviewPanel({
  classifications,
  isDryRun,
}: DryRunPreviewPanelProps) {
  if (!classifications || classifications.length === 0) return null;

  return (
    <Card className="border-border/60 shadow-sm overflow-hidden mb-6">
      <CardHeader className="pb-3 pt-4 flex flex-row items-center justify-between">
        <div>
          <CardTitle className="text-base font-bold flex items-center gap-2">
            {isDryRun ? (
              <>
                <AlertCircle className="h-4.5 w-4.5 text-primary" />
                Dry-Run Classification Preview
              </>
            ) : (
              <>
                <CheckCircle className="h-4.5 w-4.5 text-green-500" />
                Last Scan Results
              </>
            )}
          </CardTitle>
          <p className="text-xs text-muted-foreground mt-0.5">
            {isDryRun
              ? "Showing proposed actions below. No real changes have been made in your inbox."
              : "Showing actions applied in your inbox during the last scan."}
          </p>
        </div>
        <Badge variant={isDryRun ? "outline" : "default"} className={isDryRun ? "border-primary/40 text-primary bg-primary/5 text-[10px]" : "bg-green-600 text-white text-[10px]"}>
          {isDryRun ? "Read-Only Preview" : "Live Run"}
        </Badge>
      </CardHeader>
      <CardContent className="p-0">
        <div className="max-h-80 overflow-y-auto">
          <Table>
            <TableHeader className="bg-muted/40 sticky top-0 z-10">
              <TableRow>
                <TableHead className="text-xs">Subject</TableHead>
                <TableHead className="text-xs">Sender</TableHead>
                <TableHead className="text-xs">Proposed Category</TableHead>
                <TableHead className="text-xs">Confidence</TableHead>
                <TableHead className="text-xs">Action Taken/Planned</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {classifications.map((item, idx) => (
                <TableRow key={idx}>
                  <TableCell className="text-xs font-semibold py-2 max-w-[200px] truncate">
                    {item.subject}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground py-2 max-w-[150px] truncate">
                    {item.sender}
                  </TableCell>
                  <TableCell className="py-2">
                    {item.category ? (
                      <Badge variant="secondary" className="capitalize text-[10px] py-0 px-1.5">
                        {item.category}
                      </Badge>
                    ) : (
                      <span className="text-muted-foreground text-xs">—</span>
                    )}
                  </TableCell>
                  <TableCell className="text-xs py-2 tabular-nums">
                    {Math.round(item.confidence * 100)}%
                  </TableCell>
                  <TableCell className="py-2">
                    <Badge
                      className={`text-[9px] px-1.5 py-0.5 ${
                        item.action_taken === "trashed" || item.action_taken === "trash"
                          ? "bg-red-100 text-red-800 border-red-200 dark:bg-red-950/30 dark:text-red-400"
                          : item.action_taken === "labeled" || item.action_taken === "label"
                          ? "bg-green-100 text-green-800 border-green-200 dark:bg-green-950/30 dark:text-green-400"
                          : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {isDryRun ? `preview (${item.action_taken})` : item.action_taken}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
