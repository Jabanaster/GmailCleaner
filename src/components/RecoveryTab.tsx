import { useState } from "react";
import { api } from "@/lib/api";
import type { RecoveryPreviewResponse, RecoveryExecuteResponse } from "@/types";
import { useToast } from "@/hooks/use-toast";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { AlertTriangle, ShieldAlert, CheckCircle, RefreshCw, Info } from "lucide-react";

export function RecoveryTab() {
  const [idType, setIdType] = useState<"batch" | "run">("batch");
  const [targetId, setTargetId] = useState<string>("");
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [preview, setPreview] = useState<RecoveryPreviewResponse | null>(null);
  
  const [handleHighRisk, setHandleHighRisk] = useState(false);
  const [confirmExecute, setConfirmExecute] = useState(false);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [executionResult, setExecutionResult] = useState<RecoveryExecuteResponse | null>(null);
  const { toast } = useToast();

  const handleFetchPreview = async () => {
    if (!targetId || isNaN(Number(targetId))) {
      toast({
        variant: "destructive",
        title: "Invalid ID",
        description: "Please enter a valid numeric ID.",
      });
      return;
    }

    setLoadingPreview(true);
    setPreview(null);
    setExecutionResult(null);
    setConfirmExecute(false);

    try {
      const idVal = Number(targetId);
      const res = await api.getRecoveryPreview(
        idType === "batch"
          ? { operation_batch_id: idVal }
          : { scan_run_id: idVal }
      );
      setPreview(res);
      toast({
        title: "Preview Loaded",
        description: `Successfully loaded preview for ${idType} ID ${idVal}.`,
      });
    } catch (err: any) {
      toast({
        variant: "destructive",
        title: "Error Loading Preview",
        description: err.message || "Failed to load recovery preview.",
      });
    } finally {
      setLoadingPreview(false);
    }
  };

  const handleExecuteRecovery = async () => {
    if (!preview) return;
    setShowConfirmModal(false);
    setExecuting(true);
    setExecutionResult(null);

    try {
      const res = await api.executeRecovery({
        operation_batch_id: preview.operation_batch_id,
        confirm_execute: true,
        handle_high_risk: handleHighRisk,
      });
      setExecutionResult(res);
      toast({
        title: "Recovery Executed",
        description: "Successfully processed the recovery actions.",
      });
      // Refresh preview to show updated state
      handleFetchPreview();
    } catch (err: any) {
      toast({
        variant: "destructive",
        title: "Execution Failed",
        description: err.message || "Failed to execute recovery.",
      });
    } finally {
      setExecuting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Configuration & Fetch Card */}
      <Card className="border-border/60 shadow-sm">
        <CardHeader className="pb-3 pt-4">
          <CardTitle className="text-base font-bold flex items-center gap-2">
            <RefreshCw className="h-4.5 w-4.5 text-primary animate-spin-slow" />
            Scan Recovery Engine
          </CardTitle>
          <CardDescription className="text-xs">
            Generate a preview and execute a recovery plan to undo past sorting or trashing operations.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col sm:flex-row gap-3 items-end">
            <div className="flex-1 space-y-1.5">
              <Label htmlFor="id-type" className="text-xs font-semibold">ID Type</Label>
              <Select value={idType} onValueChange={(val: any) => setIdType(val)}>
                <SelectTrigger id="id-type" className="h-9">
                  <SelectValue placeholder="Select ID Type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="batch">Operation Batch ID</SelectItem>
                  <SelectItem value="run">Scan Run ID</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex-[2] space-y-1.5">
              <Label htmlFor="target-id" className="text-xs font-semibold">Target ID</Label>
              <Input
                id="target-id"
                type="text"
                placeholder="e.g. 42"
                value={targetId}
                onChange={(e) => setTargetId(e.target.value)}
                className="h-9"
              />
            </div>
            <Button
              onClick={handleFetchPreview}
              disabled={loadingPreview || !targetId}
              className="gradient-primary text-white hover:opacity-90 h-9 shrink-0 px-5 shadow-sm"
            >
              {loadingPreview ? "Loading Preview..." : "Preview Recovery"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Safety Copy / Warning alert */}
      <Alert className="bg-blue-50 border-blue-200 text-blue-800 dark:bg-blue-950/20 dark:border-blue-900/50 dark:text-blue-400">
        <Info className="h-4 w-4" />
        <AlertTitle className="text-xs font-bold">Important Safety Notice</AlertTitle>
        <AlertDescription className="text-[11px] leading-relaxed mt-1">
          <ul className="list-disc pl-4 space-y-1">
            <li>Gmail Trash recovery depends on Gmail's native retention policies.</li>
            <li>Messages permanently deleted by Gmail (after 30 days in Trash) cannot be restored.</li>
            <li>Recovery operations only apply to actions executed and logged by GmailCleaner.</li>
            <li>Preview/no-mutation rows do not modify your mailbox and require no recovery.</li>
          </ul>
        </AlertDescription>
      </Alert>

      {/* Preview Section */}
      {preview && (
        <div className="space-y-6">
          {/* Summary Stats Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Card className="border-border/60">
              <CardContent className="pt-4 pb-3">
                <div className="text-[10px] text-muted-foreground uppercase font-semibold">Total Actions</div>
                <div className="text-2xl font-bold mt-1">{preview.total_actions}</div>
              </CardContent>
            </Card>
            <Card className="border-border/60">
              <CardContent className="pt-4 pb-3">
                <div className="text-[10px] text-muted-foreground uppercase font-semibold text-green-600">Recoverable</div>
                <div className="text-2xl font-bold mt-1 text-green-600">{preview.recoverable_count}</div>
              </CardContent>
            </Card>
            <Card className="border-border/60">
              <CardContent className="pt-4 pb-3">
                <div className="text-[10px] text-muted-foreground uppercase font-semibold text-amber-600">High Risk</div>
                <div className="text-2xl font-bold mt-1 text-amber-600">{preview.high_risk_count}</div>
              </CardContent>
            </Card>
            <Card className="border-border/60">
              <CardContent className="pt-4 pb-3">
                <div className="text-[10px] text-muted-foreground uppercase font-semibold text-muted-foreground">Skipped</div>
                <div className="text-2xl font-bold mt-1 text-muted-foreground">{preview.skipped_count}</div>
              </CardContent>
            </Card>
          </div>

          {/* Warnings List */}
          {preview.warning_list.length > 0 && (
            <Alert variant="destructive" className="bg-destructive/10 border-destructive/20 text-destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle className="text-xs font-bold">Trash Retention Warnings</AlertTitle>
              <AlertDescription className="text-xs mt-1">
                {preview.warning_list.map((warn, i) => (
                  <p key={i}>{warn}</p>
                ))}
              </AlertDescription>
            </Alert>
          )}

          {/* Per-Message Preview Table */}
          <Card className="border-border/60 shadow-sm overflow-hidden">
            <CardHeader className="pb-2 pt-3">
              <CardTitle className="text-sm font-semibold">Planned Recovery Operations</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="max-h-80 overflow-y-auto">
                <Table>
                  <TableHeader className="bg-muted/40 sticky top-0 z-10">
                    <TableRow>
                      <TableHead className="text-xs">Message ID</TableHead>
                      <TableHead className="text-xs">Category</TableHead>
                      <TableHead className="text-xs">Executed Action</TableHead>
                      <TableHead className="text-xs">Planned Recovery</TableHead>
                      <TableHead className="text-xs">Risk</TableHead>
                      <TableHead className="text-xs">Reason/Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {preview.per_message_preview.map((row) => (
                      <TableRow key={row.gmail_message_id}>
                        <TableCell className="font-mono text-[11px] py-2">{row.gmail_message_id}</TableCell>
                        <TableCell className="text-xs py-2">
                          {row.category ? (
                            <Badge variant="outline" className="capitalize text-[10px]">
                              {row.category}
                            </Badge>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </TableCell>
                        <TableCell className="capitalize text-xs py-2">{row.executed_action}</TableCell>
                        <TableCell className="font-mono text-xs text-primary py-2">{row.planned_recovery_action}</TableCell>
                        <TableCell className="py-2">
                          <Badge
                            className={`text-[9px] px-1.5 py-0.5 ${
                              row.risk_level === "high"
                                ? "bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-400"
                                : "bg-green-100 text-green-800 border-green-200 dark:bg-green-900/30 dark:text-green-400"
                            }`}
                          >
                            {row.risk_level}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground py-2">{row.reason}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>

          {/* Execution Controls Card */}
          <Card className="border-border/60 shadow-sm">
            <CardHeader className="pb-3 pt-4">
              <CardTitle className="text-sm font-semibold">Execute Recovery</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {preview.dry_run ? (
                <div className="text-xs text-muted-foreground italic">
                  This batch was run as a dry run. No messages were modified, so no recovery actions are required or possible.
                </div>
              ) : (
                <>
                  <div className="flex items-center space-x-2.5">
                    <Checkbox
                      id="high-risk"
                      checked={handleHighRisk}
                      onCheckedChange={(checked: boolean) => setHandleHighRisk(checked)}
                    />
                    <Label htmlFor="high-risk" className="text-xs leading-none font-semibold cursor-pointer">
                      Handle High-Risk Actions (e.g. untrash recoverable messages)
                    </Label>
                  </div>

                  <div className="flex items-center space-x-2.5">
                    <Checkbox
                      id="confirm-execute"
                      checked={confirmExecute}
                      onCheckedChange={(checked: boolean) => setConfirmExecute(checked)}
                    />
                    <Label htmlFor="confirm-execute" className="text-xs leading-none font-semibold cursor-pointer text-destructive">
                      I confirm that I want to proceed with executing this recovery plan.
                    </Label>
                  </div>

                  <Button
                    onClick={() => setShowConfirmModal(true)}
                    disabled={!confirmExecute || executing}
                    variant="destructive"
                    className="w-full sm:w-auto px-6"
                  >
                    {executing ? "Executing..." : "Execute Recovery"}
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Execution Results Display */}
      {executionResult && (
        <Card className="border-border/60 shadow-sm bg-green-50/10 dark:bg-green-950/5">
          <CardHeader className="pb-2 pt-3">
            <CardTitle className="text-sm font-bold flex items-center gap-2 text-green-600">
              <CheckCircle className="h-4.5 w-4.5" />
              Recovery Execution Complete
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              <div className="border border-border/50 rounded-lg p-2.5 bg-background">
                <div className="text-[10px] text-muted-foreground uppercase font-semibold">Attempted</div>
                <div className="text-lg font-bold mt-0.5">{executionResult.attempted}</div>
              </div>
              <div className="border border-border/50 rounded-lg p-2.5 bg-background">
                <div className="text-[10px] text-muted-foreground uppercase font-semibold text-green-600">Succeeded</div>
                <div className="text-lg font-bold mt-0.5 text-green-600">{executionResult.succeeded}</div>
              </div>
              <div className="border border-border/50 rounded-lg p-2.5 bg-background">
                <div className="text-[10px] text-muted-foreground uppercase font-semibold text-red-600">Failed</div>
                <div className="text-lg font-bold mt-0.5 text-red-600">{executionResult.failed}</div>
              </div>
              <div className="border border-border/50 rounded-lg p-2.5 bg-background">
                <div className="text-[10px] text-muted-foreground uppercase font-semibold text-amber-600">High Risk Skipped</div>
                <div className="text-lg font-bold mt-0.5 text-amber-600">{executionResult.high_risk_skipped}</div>
              </div>
              <div className="border border-border/50 rounded-lg p-2.5 bg-background">
                <div className="text-[10px] text-muted-foreground uppercase font-semibold">Skipped (No-Op)</div>
                <div className="text-lg font-bold mt-0.5">{executionResult.skipped}</div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Confirmation Modal */}
      <Dialog open={showConfirmModal} onOpenChange={setShowConfirmModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <ShieldAlert className="h-5 w-5" />
              Confirm Recovery Execution
            </DialogTitle>
            <DialogDescription className="text-xs pt-1">
              You are about to execute recovery actions on {preview?.recoverable_count} messages. This operation will modify your mailbox.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2 text-xs border-y border-border/50 my-2">
            <p>
              <strong>Target Batch:</strong> {preview?.operation_batch_id} (Scan Run: {preview?.scan_run_id})
            </p>
            <p>
              <strong>High Risk Recovery Allowed:</strong> {handleHighRisk ? "YES (untrashing allowed)" : "NO (untrashing will be skipped)"}
            </p>
            <p className="text-destructive font-semibold">
              Warning: Recovery will perform modify operations in your Gmail account. Once executed, recovery action logs are written permanently to the database.
            </p>
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setShowConfirmModal(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleExecuteRecovery}>
              Confirm & Execute
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
