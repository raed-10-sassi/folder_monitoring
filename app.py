import os
import time
from flask import Flask, render_template
from waitress import serve
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

app = Flask(__name__)

# Folder paths to monitor
FOLDERS_TO_MONITOR = [
    ("NUTRIMIX", r"\\10.88.1.237\d\DATA\NUTRIMIX\TRANSFER\OUT"),
    ("SNA_ALM", r"\\10.40.1.237\d\SNA\transfer"),
    ("GLO", r"\\10.88.1.236\eregest"),
    ("CMV_SNA", r"\\10.40.1.237\d\SNACMV\TRANSFER"),
    ("Cedria", r"\\10.40.1.162\eregest"),
    ("Sidi el heni", r"\\10.43.1.20\mfgpro\EREGEST"),
    
    
]

# SMTP Email Configuration
SMTP_SERVER = "192.168.160.169"  # SMTP server address
SMTP_PORT = 25  # SMTP port
FROM_EMAIL = "raed.sassi@sna.com.tn"  # Sender email
#TO_EMAIL = "raed.sassi@sna.com.tn, sassi.raed10@gmail.com"  # Recipient email
TO_EMAIL = ["Jouda Rebai/SNA/POULINA"]
TO_EMAILS = ", ".join(TO_EMAIL)

EMAIL_SUBJECT = "Folder Monitoring Status"

# Email sending interval (in seconds)
EMAIL_RESEND_INTERVAL = 30 * 60  # 30 minutes

# Dictionary to track last email sent time for each folder
last_email_sent_time = {folder_name: 0 for folder_name, _ in FOLDERS_TO_MONITOR}

# Track if the summary email has been sent today
summary_email_sent_today = False


def send_email_alert(subject, body):
    """
    Send an email alert with the specified subject and body.
    """
    try:
        msg = MIMEMultipart()
        msg['From'] = FROM_EMAIL
        msg['To'] = TO_EMAILS
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.ehlo()  # Say hello to the server
            smtp.sendmail(FROM_EMAIL, TO_EMAIL, msg.as_string())  # Send the email
        
        print(f"Email sent successfully: {subject}")
    except Exception as e:
        print(f"Error sending email: {e}")


# Track the previous state of each folder
previous_state = {folder_name: None for folder_name, _ in FOLDERS_TO_MONITOR}

def monitor_folder(folder_name, folder_path):
    """
    Checks the status of a folder and returns an HTML row for the table.
    Determines progress based on the highest number found in copy files.
    """
    global last_email_sent_time, last_known_state

    highest_copy_number = 0
    mfg_dat_count = 0  # Counter for 'mfg' files with '.dat' extension

    try:
        for filename in os.listdir(folder_path):
            # Check if filename starts with 'copy' and contains a number
            match = re.search(r'copy(\d+)', filename, re.IGNORECASE)
            if match:
                file_number = int(match.group(1))
                highest_copy_number = max(highest_copy_number, file_number)

            # Count 'mfg.dat' files to check if the transfer stopped
            if 'mfg' in filename.lower() and filename.lower().endswith('.dat'):
                mfg_dat_count += 1

        # Check if transfer is stopped
        if mfg_dat_count > 2:
            state = "<span class='error'><strong>Données non reçues(MFG)</strong></span>"

            # Send alert email if needed
            if last_known_state[folder_name] != "stopped":
                send_email_alert(
                    f"⚠️ Alert: Transfer Stopped for {folder_name}",
                    f"The transfer has stopped for the site: {folder_name}. Please check the system."
                )
                last_known_state[folder_name] = "stopped"

        else:
            state = "<span class='success'><strong>transfert en cours</strong></span>"

            # Send email if transfer resumes
            if last_known_state[folder_name] == "stopped":
                send_email_alert(
                    f"✅ Transfer Resumed for {folder_name}",
                    f"The transfer has resumed for the site: {folder_name}. No action is needed."
                )
            
            last_known_state[folder_name] = "running"

        # Return table row with highest copy number as progress
        return f"""
            <tr>
                <td><strong>{folder_name}</strong></td>
                <td>{state}</td>
                <td>{highest_copy_number}</td>
            </tr>
        """

    except Exception as e:
        return f"""
            <tr>
                <td><strong>{folder_name}</strong></td>
                <td class="warning">Erreur: {str(e)}</td>
                <td>-</td>
            </tr>
        """



def send_summary_email():
    """
    Send a summary email if all sites are working well.
    """
    current_time = datetime.now()
    global summary_email_sent_today

    # Define the target time
    target_hour = 11
    target_minute = 5

    # Check if the current time matches the target time
    if (current_time.hour == target_hour and current_time.minute == target_minute and not summary_email_sent_today):
        all_working_message = "The transfer is working well for the following sites:\n\n"
        for folder_name, _ in FOLDERS_TO_MONITOR:
            all_working_message += f"- Transfer working well in the site: {folder_name}\n"

        send_email_alert("Daily Transfer Status", all_working_message)
        summary_email_sent_today = True  # Prevent further emails today
    elif current_time.hour != target_hour or current_time.minute != target_minute:
        # Reset daily flag if it's not the target time
        summary_email_sent_today = False



@app.route("/")
def home():
    return render_template("index.html")


@app.route("/status")
def status():
    """
    Continuously monitor folders and return status as HTML.
    """
    all_sites_working = True
    html_content = ""
    for folder_name, folder_path in FOLDERS_TO_MONITOR:
        status_row = monitor_folder(folder_name, folder_path)
        html_content += status_row

        # If the row indicates an issue (using specific criteria), set working to False
        if "error" in status_row or "warning" in status_row:
            all_sites_working = False

    # If all sites are working well, send a daily summary email at 15:00
    if all_sites_working:
        send_summary_email()

    return html_content



if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)
