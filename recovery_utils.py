import json
from sqlalchemy import text

def generate_recovery_preview(user_email: str, batch_id_or_run_id: int, engine) -> dict | None:
    with engine.connect() as conn:
        # Find the batch matching the batch_id_or_run_id for that user_email
        batch = conn.execute(text("""
            SELECT id, scan_run_id, dry_run, status FROM operation_batches
            WHERE user_email = :email AND (id = :val OR scan_run_id = :val)
            LIMIT 1
        """), {"email": user_email, "val": batch_id_or_run_id}).fetchone()

        if not batch:
            return None

        batch_id, scan_run_id, dry_run, batch_status = batch
        dry_run = bool(dry_run)

        # Fetch action logs
        logs = conn.execute(text("""
            SELECT gmail_message_id, executed_action, category, confidence, pre_label_ids, error_message
            FROM email_action_logs
            WHERE operation_batch_id = :batch_id AND user_email = :email
        """), {"batch_id": batch_id, "email": user_email}).fetchall()

        per_message_preview = []
        total_actions = len(logs)
        recoverable_count = 0
        skipped_count = 0
        high_risk_count = 0
        warning_list = []

        has_trash_warning = False

        for row in logs:
            msg_id, executed_action, category, confidence, pre_labels_str, error_message = row
            confidence = float(confidence) if confidence is not None else 0.0

            pre_labels = []
            if pre_labels_str:
                try:
                    pre_labels = json.loads(pre_labels_str)
                except Exception:
                    pass

            planned_recovery_action = "none"
            recoverable = False
            risk_level = "low"
            reason = "No mutation occurred"

            # Check if there is an error/failed action
            if error_message:
                planned_recovery_action = "none"
                recoverable = False
                risk_level = "low"
                reason = f"Manual review required due to original action failure: {error_message}"
                skipped_count += 1
            elif executed_action == "labeled":
                planned_recovery_action = "remove_label"
                recoverable = True
                risk_level = "low"
                reason = "Will remove the added label."
                recoverable_count += 1
            elif executed_action == "trashed":
                planned_recovery_action = "untrash"
                recoverable = True
                risk_level = "high"
                reason = "Gmail automatically deletes messages in Trash after 30 days. Recovery might fail if the message is permanently deleted."
                recoverable_count += 1
                high_risk_count += 1
                has_trash_warning = True
            elif executed_action == "archived":
                if "INBOX" in pre_labels:
                    planned_recovery_action = "restore_inbox"
                else:
                    planned_recovery_action = "unarchive"
                recoverable = True
                risk_level = "low"
                reason = "Will restore the message back to the Inbox."
                recoverable_count += 1
            elif executed_action in ("preview", "no_mutation", "no_action"):
                planned_recovery_action = "none"
                recoverable = False
                risk_level = "low"
                reason = "No mutation occurred during the scan."
                skipped_count += 1
            else:
                # Default fallback
                planned_recovery_action = "none"
                recoverable = False
                risk_level = "low"
                reason = f"No planned recovery for executed action: {executed_action}"
                skipped_count += 1

            per_message_preview.append({
                "gmail_message_id": msg_id,
                "executed_action": executed_action,
                "planned_recovery_action": planned_recovery_action,
                "recoverable": recoverable,
                "risk_level": risk_level,
                "reason": reason,
                "category": category,
                "confidence": confidence
            })

        if has_trash_warning:
            warning_list.append("Gmail auto-deletes trash after 30 days. Recovery of permanently deleted items is not possible.")

        return {
            "operation_batch_id": batch_id,
            "scan_run_id": scan_run_id,
            "dry_run": dry_run,
            "batch_status": batch_status,
            "total_actions": total_actions,
            "recoverable_count": recoverable_count,
            "skipped_count": skipped_count,
            "high_risk_count": high_risk_count,
            "warning_list": warning_list,
            "per_message_preview": per_message_preview
        }


def execute_recovery(user_email: str, batch_id_or_run_id: int, confirm_execute: bool, handle_high_risk: bool, engine) -> dict | None:
    if not confirm_execute:
        return None

    preview = generate_recovery_preview(user_email, batch_id_or_run_id, engine)
    if not preview:
        return None

    batch_id = preview["operation_batch_id"]
    scan_run_id = preview["scan_run_id"]

    attempted = 0
    succeeded = 0
    skipped = 0
    failed = 0
    high_risk_skipped = 0

    import gmail_service as gs
    service = None

    for msg in preview["per_message_preview"]:
        msg_id = msg["gmail_message_id"]
        planned_recovery = msg["planned_recovery_action"]
        recoverable = msg["recoverable"]
        risk_level = msg["risk_level"]

        status = "skipped"
        err_msg = None

        if not recoverable:
            skipped += 1
            status = "skipped"
            _log_recovery_action(engine, batch_id, scan_run_id, user_email, msg_id, planned_recovery, status, err_msg)
            continue

        if risk_level == "high" and not handle_high_risk:
            high_risk_skipped += 1
            status = "high_risk_skipped"
            _log_recovery_action(engine, batch_id, scan_run_id, user_email, msg_id, planned_recovery, status, err_msg)
            continue

        if service is None:
            try:
                service = gs.build_gmail_service(user_email)
            except Exception as e:
                failed += 1
                status = "failed"
                err_msg = f"Failed to build Gmail service: {str(e)}"
                _log_recovery_action(engine, batch_id, scan_run_id, user_email, msg_id, planned_recovery, status, err_msg)
                continue

        attempted += 1

        try:
            if planned_recovery == "remove_label":
                label_id = gs.get_label_id(user_email, msg["category"])
                if label_id:
                    gs.retry_api_call(lambda: service.users().messages().modify(
                        userId="me", id=msg_id, body={"removeLabelIds": [label_id]}
                    ).execute())
                else:
                    raise ValueError(f"Label ID for category '{msg['category']}' not found in database.")
            elif planned_recovery == "untrash":
                gs.retry_api_call(lambda: service.users().messages().untrash(
                    userId="me", id=msg_id
                ).execute())
            elif planned_recovery in ("restore_inbox", "unarchive"):
                gs.retry_api_call(lambda: service.users().messages().modify(
                    userId="me", id=msg_id, body={"addLabelIds": ["INBOX"]}
                ).execute())
            
            succeeded += 1
            status = "success"
        except Exception as e:
            failed += 1
            status = "failed"
            err_msg = str(e)[:500]

        _log_recovery_action(engine, batch_id, scan_run_id, user_email, msg_id, planned_recovery, status, err_msg)

    return {
        "operation_batch_id": batch_id,
        "scan_run_id": scan_run_id,
        "attempted": attempted,
        "succeeded": succeeded,
        "skipped": skipped,
        "failed": failed,
        "high_risk_skipped": high_risk_skipped,
        "warnings": preview["warning_list"]
    }


def _log_recovery_action(engine, batch_id, scan_run_id, user_email, msg_id, action, status, error_message):
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO recovery_action_logs (
                operation_batch_id, scan_run_id, user_email, gmail_message_id,
                recovery_action, status, error_message
            ) VALUES (
                :batch_id, :run_id, :email, :msg_id, :action, :status, :error
            )
        """), {
            "batch_id": batch_id,
            "run_id": scan_run_id,
            "email": user_email,
            "msg_id": msg_id,
            "action": action,
            "status": status,
            "error": error_message
        })
        conn.commit()

