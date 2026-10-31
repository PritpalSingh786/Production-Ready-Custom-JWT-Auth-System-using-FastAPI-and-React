import json
import asyncio
from celery import shared_task
from app.redis_client import redis_client
from app.utils.email_utils import send_email
from app.socketio_server import sio

@shared_task(name="app.tasks.email_tasks.send_email_task")
def send_email_task(subject, message, recipient_list):
    print("Email task started")
    # Ab asyncio ki zaroorat nahi hai, direct call karo
    send_email(subject, message, recipient_list)
    print("Email sent successfully")
    return True

@shared_task(name="app.tasks.email_tasks.send_logout_notification_task")
def send_logout_notification_task(user_id, device_id, message):
    room = f"user_{user_id}_{device_id}"
    # SocketIO emit async function hai, isliye yahan asyncio.run rahega
    asyncio.run(
        sio.emit(
            "logout_notification",
            {"type": "LOGOUT", "message": message, "action": "redirect_login"},
            room=room,
        )
    )
    return True

@shared_task(name="app.tasks.email_tasks.logout_all_devices_task")
def logout_all_devices_task(user_id, excluded_device_id=None):
    user_tokens_key = f"hash-rt-for-user-{user_id}"
    all_tokens = redis_client.hgetall(user_tokens_key)
    redis_client.delete(user_tokens_key)

    for jti, token_data_str in all_tokens.items():
        token_data = json.loads(token_data_str)
        device_id = token_data.get("device_id")
        if excluded_device_id and device_id == excluded_device_id:
            continue
        if device_id:
            send_logout_notification_task.delay(
                user_id,
                device_id,
                "Your account password was changed. You have been logged out.",
            )
    return len(all_tokens)