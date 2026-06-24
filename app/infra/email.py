import json
import urllib.request
import urllib.error
import asyncio
from app.core.config import settings
from app.core.logger import logger

class EmailSender:
    @staticmethod
    async def send_otp_email(to_email: str, otp: str) -> bool:
        if not settings.RESEND_API_KEY:
            logger.warning("RESEND_API_KEY is not set. Skipping email sending.")
            # During development without an API key, just log the OTP
            logger.info("MOCK EMAIL to %s: Your OTP is %s", to_email, otp)
            return True

        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "multAI-Backend/1.0"
        }

        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Bienvenue sur multAI !</h2>
            <p>Voici votre code de vérification :</p>
            <h1 style="background: #f4f4f4; padding: 10px; letter-spacing: 5px; text-align: center;">{otp}</h1>
            <p>Ce code est valide pendant 10 minutes.</p>
        </div>
        """

        data = {
            "from": settings.EMAIL_FROM,
            "to": [to_email],
            "subject": "Votre code de vérification multAI",
            "html": html_content
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers=headers,
            method="POST"
        )

        def _send() -> bool:
            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    res_body = response.read()
                    logger.info("Email sent via Resend. Response: %s", res_body)
                    return True
            except urllib.error.HTTPError as e:
                err_body = e.read()
                logger.error("Failed to send email via Resend: %s - %s", e.code, err_body)
                return False
            except Exception as e:
                logger.error("Error sending email: %s", str(e))
                return False

        return await asyncio.to_thread(_send)
