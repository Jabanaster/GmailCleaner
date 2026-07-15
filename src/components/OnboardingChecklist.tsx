import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, AlertCircle, HelpCircle, Shield, Trash2, RotateCcw } from "lucide-react";

interface OnboardingChecklistProps {
  gmailConnected: boolean;
  hasActiveDevices: boolean;
}

export function OnboardingChecklist({
  gmailConnected,
  hasActiveDevices,
}: OnboardingChecklistProps) {
  return (
    <Card className="border-border/60 shadow-sm overflow-hidden mb-6">
      <div className="h-1 bg-gradient-to-r from-blue-500 to-indigo-500" />
      <CardHeader className="pb-3 pt-4">
        <CardTitle className="text-base font-bold flex items-center gap-2">
          <Shield className="h-4.5 w-4.5 text-blue-500" />
          Safety & Setup Checklist
        </CardTitle>
        <CardDescription className="text-xs">
          Verify your configuration and review the built-in guardrails before running scans.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-3">
          {/* Item 1: Gmail Connection */}
          <div className="flex items-start gap-3 p-2.5 rounded-xl bg-muted/40 border border-border/40">
            {gmailConnected ? (
              <CheckCircle2 className="h-5 w-5 text-green-500 shrink-0 mt-0.5" />
            ) : (
              <AlertCircle className="h-5 w-5 text-amber-500 shrink-0 mt-0.5" />
            )}
            <div className="space-y-0.5">
              <div className="text-xs font-bold flex items-center gap-2">
                Gmail Dashboard Connection
                <Badge variant={gmailConnected ? "default" : "outline"} className={`text-[9px] py-0 px-1.5 ${gmailConnected ? "bg-green-600 text-white hover:bg-green-600/80" : "text-amber-600 border-amber-300"}`}>
                  {gmailConnected ? "Connected" : "Action Required"}
                </Badge>
              </div>
              <p className="text-[11px] text-muted-foreground">
                {gmailConnected
                  ? "Your Gmail account is securely linked to the dashboard via OAuth."
                  : "Link your Gmail account using OAuth. Click the disconnect or connect options to manage credentials."}
              </p>
            </div>
          </div>

          {/* Item 2: Extension Status */}
          <div className="flex items-start gap-3 p-2.5 rounded-xl bg-muted/40 border border-border/40">
            {hasActiveDevices ? (
              <CheckCircle2 className="h-5 w-5 text-green-500 shrink-0 mt-0.5" />
            ) : (
              <HelpCircle className="h-5 w-5 text-amber-500 shrink-0 mt-0.5" />
            )}
            <div className="space-y-0.5">
              <div className="text-xs font-bold flex items-center gap-2">
                Browser Extension Pairing
                <Badge variant={hasActiveDevices ? "default" : "outline"} className={`text-[9px] py-0 px-1.5 ${hasActiveDevices ? "bg-green-600 text-white hover:bg-green-600/80" : ""}`}>
                  {hasActiveDevices ? "Paired" : "Optional"}
                </Badge>
              </div>
              <p className="text-[11px] text-muted-foreground">
                {hasActiveDevices
                  ? "At least one extension device is successfully paired for scan synchronization."
                  : "Pair the companion Chrome extension to automatically analyze messages on page load. Use the 'Pair Extension' button above."}
              </p>
            </div>
          </div>

          {/* Item 3: Dry-Run Safety */}
          <div className="flex items-start gap-3 p-2.5 rounded-xl bg-muted/40 border border-border/40">
            <CheckCircle2 className="h-5 w-5 text-green-500 shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <div className="text-xs font-bold flex items-center gap-2">
                Dry-Run Safety
                <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400 text-[9px] py-0 px-1.5">
                  Enforced
                </Badge>
              </div>
              <p className="text-[11px] text-muted-foreground">
                Dry-run mode is fully read-only. <strong>No live mutations</strong> (label additions, inbox removals, or trashing) occur in your Gmail mailbox during a dry-run.
              </p>
            </div>
          </div>

          {/* Item 4: Trash & Recovery Warning */}
          <div className="flex items-start gap-3 p-2.5 rounded-xl bg-muted/40 border border-border/40">
            <Trash2 className="h-5 w-5 text-amber-500 shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <div className="text-xs font-bold flex items-center gap-2">
                Gmail Trash Policy
              </div>
              <p className="text-[11px] text-muted-foreground">
                Gmail automatically deletes items in the Trash folder after 30 days. Recovery is impossible once permanently deleted by Gmail.
              </p>
            </div>
          </div>

          {/* Item 5: Recovery Option */}
          <div className="flex items-start gap-3 p-2.5 rounded-xl bg-muted/40 border border-border/40">
            <RotateCcw className="h-5 w-5 text-indigo-500 shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <div className="text-xs font-bold flex items-center gap-2">
                Recovery / Undo Available
              </div>
              <p className="text-[11px] text-muted-foreground">
                All full-run operations are logged. You can review and reverse label changes or restore trashed messages using the <strong>Recovery Tab</strong>.
              </p>
            </div>
          </div>
        </div>

        {/* Required next action */}
        <div className="p-3 rounded-xl bg-blue-50 border border-blue-100 text-blue-900 dark:bg-blue-950/20 dark:border-blue-900/40 dark:text-blue-400">
          <div className="text-xs font-bold">Recommended Next Action:</div>
          <p className="text-[11px] mt-0.5">
            {!gmailConnected
              ? "Click connect to authorize Gmail credentials using OAuth."
              : "Perform a 'Preview Scan (Dry Run)' first to inspect how the classifier categorizes your emails without making any modifications."}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
