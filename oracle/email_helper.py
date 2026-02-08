"""
Email sending helper for Python using PHP mail() function.
This is needed because shared hosting doesn't support direct SMTP from Python.
"""

import json
import subprocess
import logging
import os

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, html_body: str = None, text_body: str = None, from_email: str = None) -> bool:
    """
    Send email using PHP mail() function via send_email.php.
    
    Args:
        to: Recipient email address
        subject: Email subject
        html_body: HTML body (optional)
        text_body: Plain text body (optional)
        from_email: From email address (optional, defaults to noreply@domain)
    
    Returns:
        True if email sent successfully, False otherwise
    """
    if not to or not subject:
        logger.error("Email 'to' and 'subject' are required")
        return False
    
    if not html_body and not text_body:
        logger.error("Either html_body or text_body must be provided")
        return False
    
    # Prepare data for PHP script
    email_data = {
        'to': to,
        'subject': subject,
        'html_body': html_body or '',
        'text_body': text_body or ''
    }
    
    if from_email:
        email_data['from'] = from_email
    
    try:
        # Get path to send_email.php (should be in project root)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        php_script = os.path.join(project_root, 'send_email.php')
        
        if not os.path.exists(php_script):
            logger.error(f"send_email.php not found at {php_script}")
            return False
        
        # Call PHP script with JSON data via stdin
        result = subprocess.run(
            ['php', php_script],
            input=json.dumps(email_data),
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            logger.info(f"Email sent successfully to {to}")
            return True
        else:
            logger.error(f"Failed to send email to {to}: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"Email sending timeout for {to}")
        return False
    except Exception as e:
        logger.error(f"Error sending email to {to}: {e}", exc_info=True)
        return False


def send_warning_email(subject: str, message: str) -> bool:
    """
    Send warning email to admin (ozeritski@gmail.com).
    
    Args:
        subject: Email subject
        message: Warning message
    
    Returns:
        True if sent successfully, False otherwise
    """
    admin_email = 'ozeritski@gmail.com'
    
    html_body = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            .warning {{ background-color: #fff3cd; border: 1px solid #ffc107; padding: 15px; border-radius: 5px; }}
            .message {{ margin-top: 15px; white-space: pre-wrap; }}
        </style>
    </head>
    <body>
        <div class="warning">
            <h2>⚠️ System Warning</h2>
            <div class="message">{message}</div>
        </div>
    </body>
    </html>
    """
    
    text_body = f"System Warning\n\n{message}"
    
    return send_email(
        to=admin_email,
        subject=f"[d.onl Warning] {subject}",
        html_body=html_body,
        text_body=text_body
    )

