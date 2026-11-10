import asyncio
import json
from datetime import datetime

from celery import shared_task
from app.redis_client import redis_client
from app.utils.email_utils import send_email
from app.socketio_server import sio
from app.config import settings


@shared_task(name="app.tasks.email_tasks.send_email_task")
def send_email_task(subject, message, recipient_list):
    send_email(subject, message, recipient_list)
    return True


@shared_task(name="app.tasks.email_tasks.send_new_login_alert_task")
def send_new_login_alert_task(
    user_email, user_id, userId, device_name, ip_address, platform, reset_token
):
    print("sentttttttttt")
    reset_link = (
        f"{settings.DOMAIN_URL}/api/users/secure-password-change-template/"
        f"{user_id}/{reset_token}/"
    )
    subject = f"New Login Detected - {userId}"
    message = f"""
Hello {userId},

We detected a login to your account.

Device: {device_name}
IP Address: {ip_address or "Unknown"}
Platform: {platform}
Time: {datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")}

If this was NOT you, open this link within 3 minutes to secure your account:
{reset_link}

This link expires in 3 minutes.

Best regards,
Your Team
"""
    send_email_task.delay(subject, message, [user_email])
    return True


@shared_task(name="app.tasks.email_tasks.send_password_changed_email_task")
def send_password_changed_email_task(user_email, user_name):
    subject = "Password Changed Successfully"
    message = f"""
Hello {user_name},

Your password has been successfully changed.
You have been logged out from all devices for security reasons.

If this was NOT you, please contact support immediately.

Best regards,
Your Team
"""
    send_email_task.delay(subject, message, [user_email])
    return True


@shared_task(name="app.tasks.email_tasks.send_forgot_password_email_task")
def send_forgot_password_email_task(subject, message, recipient_list):
    send_email(subject, message, recipient_list)
    return True


@shared_task(name="app.tasks.email_tasks.send_logout_notification_task")
def send_logout_notification_task(user_id, device_id, message):
    room = f"user_{user_id}_{device_id}"
    asyncio.run(sio.emit(
        "logout_notification",
        {"type": "LOGOUT", "message": message, "action": "redirect_login"},
        room=room,
    ))
    return True


@shared_task(name="app.tasks.email_tasks.logout_all_devices_task")
def logout_all_devices_task(user_id, excluded_device_id=None):
    key = f"sessions-for-user-{user_id}"
    all_tokens = redis_client.hgetall(key)
    redis_client.delete(key)

    for _, token_data_str in all_tokens.items():
        try:
            token_data = json.loads(token_data_str)
        except (TypeError, json.JSONDecodeError):
            continue
        device_id = token_data.get("device_id")
        if excluded_device_id and str(device_id) == str(excluded_device_id):
            continue
        if device_id:
            send_logout_notification_task.delay(
                str(user_id), str(device_id),
                "Your account password was changed. You have been logged out.",
            )
    return len(all_tokens)
