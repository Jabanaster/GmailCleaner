import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Shield, RefreshCw, KeyRound, Monitor, ShieldOff } from "lucide-react";
import type { DeviceSession } from "@/types";

interface DevicesTabProps {
  devices: DeviceSession[];
  onRevoke: (id: string) => void;
  onCreateCode: () => void;
  onRefresh: () => void;
}

export function DevicesTab({
  devices,
  onRevoke,
  onCreateCode,
  onRefresh,
}: DevicesTabProps) {
  const activeDevices = devices.filter((d) => !d.revoked);
  const revokedDevices = devices.filter((d) => d.revoked);

  return (
    <div className="space-y-4">
      <Card className="border-border/60 shadow-sm">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2 text-base">
              <Shield className="h-4 w-4 text-primary" />
              Paired Extension Devices
              {activeDevices.length > 0 && (
                <Badge className="gradient-primary text-white border-0">{activeDevices.length}</Badge>
              )}
            </CardTitle>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={onRefresh} className="h-7 text-xs gap-1">
                <RefreshCw className="h-3 w-3" /> Refresh
              </Button>
              <Button size="sm" onClick={onCreateCode} className="h-7 text-xs gradient-primary text-white border-0 shadow gap-1.5">
                <KeyRound className="h-3 w-3" /> New Pairing Code
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {activeDevices.length === 0 ? (
            <div className="py-10 text-center text-muted-foreground">
              <Monitor className="mx-auto mb-3 h-10 w-10 opacity-30" />
              <p className="text-sm font-medium">No paired devices</p>
              <p className="text-xs mt-1 max-w-xs mx-auto">
                Generate a pairing code and enter it in the extension Options page to link a device.
              </p>
              <Button variant="outline" size="sm" className="mt-4 gap-1.5" onClick={onCreateCode}>
                <KeyRound className="h-3.5 w-3.5" /> Generate Pairing Code
              </Button>
            </div>
          ) : (
            <div className="space-y-2">
              {activeDevices.map((device) => (
                <DeviceRow key={device.id} device={device} onRevoke={onRevoke} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {revokedDevices.length > 0 && (
        <Card className="border-border/60 shadow-sm opacity-70">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base text-muted-foreground">
              <ShieldOff className="h-4 w-4" />
              Revoked Devices
              <Badge variant="secondary" className="text-xs">{revokedDevices.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {revokedDevices.map((device) => (
                <DeviceRow key={device.id} device={device} onRevoke={onRevoke} />
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function DeviceRow({ device, onRevoke }: { device: DeviceSession; onRevoke: (id: string) => void }) {
  const lastSeen = device.last_seen_at ? new Date(device.last_seen_at) : null;
  const created = device.created_at ? new Date(device.created_at) : null;
  const minutesAgo = lastSeen ? Math.round((Date.now() - lastSeen.getTime()) / 60000) : null;

  const freshLabel = minutesAgo !== null
    ? minutesAgo < 2 ? "Just now" : minutesAgo < 60 ? `${minutesAgo}m ago` : `${Math.round(minutesAgo / 60)}h ago`
    : null;

  return (
    <div className={`flex items-center gap-3 rounded-xl border p-3.5 transition-colors ${device.revoked ? "border-border/30 bg-muted/20" : "border-border/60 hover:bg-muted/30"}`}>
      <div className={`flex h-9 w-9 items-center justify-center rounded-xl ${device.revoked ? "bg-muted" : "bg-primary/10"}`}>
        <Monitor className={`h-4 w-4 ${device.revoked ? "text-muted-foreground" : "text-primary"}`} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className={`font-medium text-sm truncate ${device.revoked ? "text-muted-foreground" : "text-foreground"}`}>
            {device.device_name}
          </p>
          {device.revoked ? (
            <Badge variant="outline" className="text-xs text-muted-foreground shrink-0">Revoked</Badge>
          ) : (
            <Badge className="text-xs bg-green-500/15 text-green-700 dark:text-green-400 border-green-500/20 shrink-0">Active</Badge>
          )}
        </div>
        <div className="flex items-center gap-2 mt-0.5 text-xs text-muted-foreground">
          {device.extension_version && <span>v{device.extension_version}</span>}
          {created && <span>Paired {created.toLocaleDateString()}</span>}
          {freshLabel && <span>· Seen {freshLabel}</span>}
        </div>
      </div>
      {!device.revoked && (
        <Button
          variant="outline"
          size="sm"
          className="h-7 text-xs text-destructive border-destructive/30 hover:bg-destructive/10 hover:text-destructive shrink-0"
          onClick={() => onRevoke(device.id)}
        >
          <ShieldOff className="mr-1 h-3 w-3" /> Revoke
        </Button>
      )}
    </div>
  );
}
