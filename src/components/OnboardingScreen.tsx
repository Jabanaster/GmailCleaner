import { Mail, Loader2, Shield, Sun, Moon, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

interface OnboardingScreenProps {
  oauthConfigured: boolean;
  connecting: boolean;
  onConnect: () => void;
  error: string | null;
  dark: boolean;
  onToggleDark: () => void;
}

export function OnboardingScreen({
  oauthConfigured,
  connecting,
  onConnect,
  error,
  dark,
  onToggleDark,
}: OnboardingScreenProps) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-background p-4">
      <Button variant="outline" size="icon" className="fixed top-4 right-4 h-8 w-8" onClick={onToggleDark}>
        {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      </Button>

      <div className="w-full max-w-md">
        {/* Brand mark */}
        <div className="mb-8 flex flex-col items-center gap-4">
          <div className="relative flex h-20 w-20 items-center justify-center rounded-3xl gradient-primary shadow-xl">
            <Mail className="h-9 w-9 text-white" />
            <div className="absolute -inset-1 rounded-3xl gradient-primary opacity-30 blur-md" />
          </div>
          <div className="text-center">
            <h1 className="text-3xl font-bold text-foreground">Gmail Cleaner</h1>
            <p className="mt-1 text-sm text-muted-foreground">AI-powered inbox sorting & cleanup</p>
          </div>
        </div>

        <Card className="border-border/60 shadow-lg">
          <CardContent className="pt-6 space-y-5">
            {error && (
              <div className="flex items-center gap-2 rounded-xl border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                <AlertTriangle className="h-4 w-4 flex-shrink-0" />
                {error}
              </div>
            )}

            {!oauthConfigured ? (
              <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-5 space-y-3">
                <h3 className="font-semibold text-amber-700 dark:text-amber-400 flex items-center gap-2">
                  <Shield className="h-4 w-4" />
                  Google OAuth Setup Required
                </h3>
                <ol className="text-sm text-muted-foreground list-decimal list-inside space-y-1.5">
                  <li>Go to Google Cloud Console → APIs &amp; Services → Credentials</li>
                  <li>Create an OAuth 2.0 Client ID (Web application)</li>
                  <li>Add the redirect URI below to Authorized redirect URIs</li>
                  <li>Enable the Gmail API for your project</li>
                  <li>Add <code className="text-xs rounded bg-muted px-1">GOOGLE_OAUTH_CLIENT_ID</code> and <code className="text-xs rounded bg-muted px-1">GOOGLE_OAUTH_CLIENT_SECRET</code> to .env</li>
                </ol>
                <Separator />
                <p className="text-xs text-muted-foreground">
                  Redirect URI:{" "}
                  <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                    {window.location.origin}/api/gmail/oauth/callback
                  </code>
                </p>
              </div>
            ) : (
              <Button
                onClick={onConnect}
                disabled={connecting}
                className="w-full gradient-primary text-white hover:opacity-90 transition-opacity shadow-md"
                size="lg"
              >
                {connecting ? (
                  <><Loader2 className="mr-2 h-5 w-5 animate-spin" /> Connecting…</>
                ) : (
                  <><Mail className="mr-2 h-5 w-5" /> Connect Gmail Account</>
                )}
              </Button>
            )}

            <div className="grid grid-cols-3 gap-2">
              <FeatureBadge icon="🗑️" label="Trash junk" />
              <FeatureBadge icon="🏷️" label="Sort categories" />
              <FeatureBadge icon="✨" label="AI-powered" />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function FeatureBadge({ icon, label }: { icon: string; label: string }) {
  return (
    <div className="flex flex-col items-center gap-1.5 rounded-xl border border-border bg-muted/40 p-3">
      <span className="text-xl leading-none">{icon}</span>
      <span className="text-xs text-muted-foreground font-medium">{label}</span>
    </div>
  );
}
