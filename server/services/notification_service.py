"""
Notification Service - Push notification, email alerts, webhook.
Cảnh báo khi có sự kiện quan trọng.
"""

import asyncio
import logging
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Notification:
    """Một notification."""
    type: str  # info, warning, critical
    title: str
    message: str
    client_id: Optional[str] = None
    timestamp: float = 0
    data: Optional[dict] = None


class NotificationService:
    """
    Service gửi notification qua nhiều kênh:
    - Push notification (WebSocket)
    - Email (SMTP)
    - Webhook (HTTP POST)
    - Console log
    - Desktop notification
    """
    
    def __init__(self):
        self.history: List[Notification] = []
        self.max_history = 500
        self.webhook_urls: List[str] = []
        self.email_config: Optional[dict] = None
        self._callbacks: Dict[str, List[Callable]] = {}
    
    def configure_email(self, smtp_host: str, smtp_port: int,
                        username: str, password: str,
                        from_addr: str, to_addrs: List[str]):
        """Cấu hình email notification."""
        self.email_config = {
            'smtp_host': smtp_host,
            'smtp_port': smtp_port,
            'username': username,
            'password': password,
            'from_addr': from_addr,
            'to_addrs': to_addrs,
        }
        logger.info(f"Email notification configured: {smtp_host}:{smtp_port}")
    
    def add_webhook(self, url: str):
        """Thêm webhook URL."""
        if url not in self.webhook_urls:
            self.webhook_urls.append(url)
            logger.info(f"Webhook added: {url}")
    
    def remove_webhook(self, url: str):
        """Xóa webhook URL."""
        self.webhook_urls = [u for u in self.webhook_urls if u != url]
    
    async def send(self, notification: Notification):
        """Gửi notification qua tất cả kênh đã cấu hình."""
        notification.timestamp = notification.timestamp or time.time()
        
        # Lưu history
        self.history.append(notification)
        if len(self.history) > self.max_history:
            self.history.pop(0)
        
        logger.info(f"Notification: [{notification.type}] {notification.title}: "
                   f"{notification.message[:100]}")
        
        # Gửi qua các kênh
        tasks = []
        
        # Email (chỉ cho critical)
        if notification.type == 'critical' and self.email_config:
            tasks.append(self._send_email(notification))
        
        # Webhook
        for url in self.webhook_urls:
            tasks.append(self._send_webhook(url, notification))
        
        # Trigger callbacks
        self._trigger('notification', notification)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def send_info(self, title: str, message: str,
                        client_id: Optional[str] = None):
        """Gửi info notification."""
        await self.send(Notification('info', title, message, client_id))
    
    async def send_warning(self, title: str, message: str,
                           client_id: Optional[str] = None):
        """Gửi warning notification."""
        await self.send(Notification('warning', title, message, client_id))
    
    async def send_critical(self, title: str, message: str,
                            client_id: Optional[str] = None):
        """Gửi critical notification."""
        await self.send(Notification('critical', title, message, client_id))
    
    async def send_ai_alert(self, client_id: str, alert_type: str,
                            confidence: float, details: Optional[dict] = None):
        """Gửi cảnh báo AI detection."""
        title = f"AI Detection: {alert_type}"
        message = f"Client {client_id}: Phát hiện {alert_type} (confidence: {confidence:.1%})"
        
        level = 'critical' if confidence > 0.9 else 'warning' if confidence > 0.7 else 'info'
        
        await self.send(Notification(
            type=level,
            title=title,
            message=message,
            client_id=client_id,
            data={'alert_type': alert_type, 'confidence': confidence, **(details or {})},
        ))
    
    async def _send_email(self, notification: Notification):
        """Gửi email notification."""
        if not self.email_config:
            return
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_config['from_addr']
            msg['To'] = ', '.join(self.email_config['to_addrs'])
            msg['Subject'] = f"[{notification.type.upper()}] {notification.title}"
            
            body = f"""
            <h2>{notification.title}</h2>
            <p><strong>Type:</strong> {notification.type}</p>
            <p><strong>Message:</strong> {notification.message}</p>
            <p><strong>Time:</strong> {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(notification.timestamp))}</p>
            """
            
            if notification.client_id:
                body += f"<p><strong>Client:</strong> {notification.client_id}</p>"
            
            msg.attach(MIMEText(body, 'html'))
            
            with smtplib.SMTP(
                self.email_config['smtp_host'],
                self.email_config['smtp_port']
            ) as server:
                server.starttls()
                server.login(
                    self.email_config['username'],
                    self.email_config['password']
                )
                server.send_message(msg)
                
            logger.info(f"Email sent: {notification.title}")
            
        except Exception as e:
            logger.error(f"Email send failed: {e}")
    
    async def _send_webhook(self, url: str, notification: Notification):
        """Gửi webhook notification."""
        try:
            import aiohttp
            
            data = {
                'type': notification.type,
                'title': notification.title,
                'message': notification.message,
                'client_id': notification.client_id,
                'timestamp': notification.timestamp,
                'data': notification.data,
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, timeout=5) as response:
                    if response.status != 200:
                        logger.warning(f"Webhook failed ({response.status}): {url}")
                    
        except Exception as e:
            logger.error(f"Webhook error: {url} - {e}")
    
    def on(self, event: str, callback: Callable):
        """Đăng ký event listener."""
        if event not in self._callbacks:
            self._callbacks[event] = []
        self._callbacks[event].append(callback)
    
    def _trigger(self, event: str, *args, **kwargs):
        """Kích hoạt event."""
        for cb in self._callbacks.get(event, []):
            try:
                cb(*args, **kwargs)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def get_history(self, limit: int = 50,
                    type_filter: Optional[str] = None) -> List[dict]:
        """Lấy lịch sử notification."""
        notifications = self.history
        
        if type_filter:
            notifications = [n for n in notifications if n.type == type_filter]
        
        return [
            {
                'type': n.type,
                'title': n.title,
                'message': n.message,
                'client_id': n.client_id,
                'timestamp': n.timestamp,
                'time_str': time.strftime('%H:%M:%S', time.localtime(n.timestamp)),
            }
            for n in notifications[-limit:]
        ]
    
    def get_stats(self) -> dict:
        """Lấy thống kê notifications."""
        total = len(self.history)
        by_type = {}
        
        for n in self.history:
            by_type[n.type] = by_type.get(n.type, 0) + 1
        
        return {
            'total': total,
            'by_type': by_type,
            'email_configured': self.email_config is not None,
            'webhooks_count': len(self.webhook_urls),
        }