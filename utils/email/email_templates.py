# Subject and body template for welcome email with temporary credentials
WELCOME_SUBJECT = "[Polit] Welcome — Your Temporary Credentials"
WELCOME_BODY = """Hello {full_name},

Username: {email}
Temporary password: {temp_password}

Please log in and change your password.
"""

# Subject and body template for notifying user about email update
EMAIL_UPDATED_SUBJECT = "Your Email has been Successfully Updated"
EMAIL_UPDATED_BODY = """Dear {full_name},

Your email has been updated by admin to {new_email}.
If this wasn't you, please contact support immediately.

Best regards,
Support Team
"""

# Subject and body template for sending temporary password notification
TEMP_PASSWORD_SUBJECT = "Temporary Password for Your Updated Account"
TEMP_PASSWORD_BODY = """Dear {full_name},

A temporary password has been generated for your account. Please use the following password to log in:

Temporary Password: {temp_password}

For security reasons, we recommend updating your password immediately after logging in.

Best regards,
Support Team
"""

# Subject and body template for notifying user of account deactivation
ACCOUNT_DEACTIVATED_SUBJECT = "Account Deactivated"
ACCOUNT_DEACTIVATED_BODY = """Dear {full_name},

We would like to inform you that your account has been deactivated by an administrator.
If you believe this was done in error or require further assistance, please contact our support team.

Sincerely,
Support Team
"""
