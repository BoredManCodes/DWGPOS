"""
Name: DWG POS
Purpose: To capture MOTO payment information using PYQT5, and send it to CBA's "simplify" endpoint
Written: 28/7/2023
Author: Trent Buckley


Abstract:
    Present a clear and easy to understand UI when run, start by asking for description, price and then card details.
    Depending on payment authorisation present either failure or success message boxes,
        for both show the STAN if available otherwise AUTH
    While showing that dialog box ask if the user would like to print or email the receipt for the transaction
    Build Command: pyinstaller .\main.py -w -y --icon=pos.ico --name=POS --distpath=U:/POS/dist --version-file file_version_info.txt

Change Log:
    v0 -- 28/7/2023 - Initial Commit
    v1 -- 29/7/2023 - Added logging to event viewer
    v1.1 -- 30/7/2023 - Added logging of transactions
    v1.2 -- 2/8/2023 - Added recent transactions
    v1.3 -- 4/8/2023 - Fixed floating point error
    v1.4 -- 5/8/2023 - Added ability to email receipts
    v1.4.1 -- 7/8/2023 - Added logging for email receipts
    v1.4.2 -- 7/8/2023 - Added message to confirm email sent
    v1.4.3 -- 7/8/2023 - Added ability to press enter to progress through the program
    v1.4.4 -- 7/8/2023 - Stripped numbers from name when emailing receipt
    v1.5 -- 7/8/2023 - Added loader gif when loading recent transactions
    v1.5.1 -- 7/8/2023 - Changed amount label to include max amount
    v1.5.2 -- 7/8/2023 - Made the cursor move to the start of the line when pressing enter
    v1.5.3 -- 20/9/2023 - Added Luhn check for card number
    v1.5.4 -- 25/9/2023 - Apparently v1.5.2 missed the card number field
    v1.5.5 -- 03/10/2023 - I'm going crazy, I did the same thing again
    v1.9   -- 11/10/2023 - Big changes to the way the program works, now uses the Taurus database to lookup accounts and email addresses
    v2.0   -- 13/10/2023 - Make payments apply to the account automatically
    v2.0.1 -- 13/10/2023 - Added logging to event viewer regarding applying payments
    v2.0.2 -- 14/10/2023 - Fixed payments having been marked as fully applied
    v2.0.3 -- 18/10/2023 - Don't copy reference to clipboard if the payment was applied to an account
    v2.0.4 -- 18/10/2023 - Added logging of payments via pushover
    v2.0.5 -- 18/10/2023 - Added logging failures to text file
    v2.0.6 -- 30/10/2023 - If an invalid account is used, don't crash due to being unable to apply the payment
    v2.0.7 -- 30/10/2023 - Added What's New dialog
    v2.0.8 -- 30/10/2023 - Added a system for taking payments for new accounts
"""

import csv
import datetime
import os
import pyperclip
import simplify
import sys
import time
import decimal
import win32evtlog
import win32evtlogutil
import win32com.client as win32
from PyQt5.QtCore import QTimer, Qt, QSize
from PyQt5.QtGui import QIcon, QPixmap, QMovie
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QPushButton,
    QMessageBox,
    QLineEdit,
    QListWidget,
    QDialog,
    QStatusBar,
)
import psycopg2
import ctypes
import requests
import dotenv

# Debug mode
DEBUG = False

# load environment variables
dotenv.load_dotenv("U:/POS/.env")

# Create the application
basedir = os.path.dirname(__file__)
#################################################################################
VERSION_STRING = "2.0.8"
VERSION_TUPLE = (2, 0, 8, 0)
APP_NAME = f"DWG POS v{VERSION_STRING}"
WHAT_IS_NEW = """
Fixed a bug where the program would crash if an invalid account was used.
Added a system for taking payments for new accounts, use 00000 as the account number.
"""
#################################################################################

FILE_VERSION_INFO = f"""
# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
# filevers and prodvers should be always a tuple with four items: (1, 2, 3, 4)
# Set not needed items to zero 0.
filevers={VERSION_TUPLE},
prodvers={VERSION_TUPLE},
# Contains a bitmask that specifies the valid bits 'flags'r
mask=0x3f,
# Contains a bitmask that specifies the Boolean attributes of the file.
flags=0x0,
# The operating system for which this file was designed.
# 0x4 - NT and there is no need to change it.
OS=0x4,
# The general type of file.
# 0x1 - the file is an application.
fileType=0x1,
# The function of the file.
# 0x0 - the function is not defined for this fileType
subtype=0x0,
# Creation date and time stamp.
date=(0, 0)
),
  kids=[
StringFileInfo(
  [
  StringTable(
    u'040904B0',
    [StringStruct(u'CompanyName', u'Trent Buckley'),
    StringStruct(u'FileDescription', u'A Easy to use POS application'),
    StringStruct(u'FileVersion', u'{VERSION_STRING}'),
    StringStruct(u'InternalName', u'DWGPOS'),
    StringStruct(u'LegalCopyright', u'Copyright (c) Trent Buckley'),
    StringStruct(u'OriginalFilename', u'DWGPOS.exe'),
    StringStruct(u'ProductName', u'David Walsh Gas POS'),
    StringStruct(u'ProductVersion', u'{VERSION_STRING}')])
  ]), 
VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""

# save that string to a file called file_version_info.txt
with open(os.path.join(basedir, "file_version_info.txt"), "w") as f:
    f.write(FILE_VERSION_INFO)
# What's new, when opening check if the version is different to the last time it was opened
# if it is, show the what's new dialog
try:
    if os.path.exists(os.path.join(basedir, "version.txt")):  # If the file exists
        with open(os.path.join(basedir, "version.txt"), "r") as f:  # Read the version
            version = f.read()
        if version != VERSION_STRING:  # If the version is different
            with open(os.path.join(basedir, "version.txt"), "w") as f:  # Write the new version
                f.write(VERSION_STRING)
            ctypes.windll.user32.MessageBoxW(0, WHAT_IS_NEW,
                                             f"What's New in v{VERSION_STRING}")  # Show the what's new dialog
        else:
            print("Version is the same")
    else:  # If the file doesn't exist
        with open(os.path.join(basedir, "version.txt"), "w") as f:  # Write the new version
            f.write(VERSION_STRING)
        ctypes.windll.user32.MessageBoxW(0, WHAT_IS_NEW,
                                         f"What's New in v{VERSION_STRING}")  # Show the what's new dialog
except Exception as e:
    # Print the whole error message and stack trace
    print(e)
    ctypes.windll.user32.MessageBoxW(
        0,
        f"An error occurred when trying to show the what's new dialog\n\n{e}",
        "Error",
        0,
    )


EVT_ID = 7040
EVT_CATEG = 9876
EVT_STRS = [
    f"Started DWG POS at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}"
]
# Log start of program
win32evtlogutil.ReportEvent(
    APP_NAME,
    EVT_ID,
    eventCategory=EVT_CATEG,
    eventType=win32evtlog.EVENTLOG_INFORMATION_TYPE,
    strings=EVT_STRS,
)
if DEBUG:
    simplify.public_key = os.getenv("SANDBOX_PUBLIC_KEY")
    simplify.private_key = os.getenv("SANDBOX_PRIVATE_KEY")
else:
    simplify.public_key = os.getenv("LIVE_PUBLIC_KEY")
    simplify.private_key = os.getenv("LIVE_PRIVATE_KEY")

html_email = """

            <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
            <html xmlns="http://www.w3.org/1999/xhtml">
              <head>
                <meta name="viewport" content="width=device-width, initial-scale=1.0" />
                <meta name="x-apple-disable-message-reformatting" />
                <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
                <meta name="color-scheme" content="light dark" />
                <meta name="supported-color-schemes" content="light dark" />
                <title>David Walsh Gas Receipt</title>
                <style type="text/css" rel="stylesheet" media="all">
                /* Base ------------------------------ */

                @import url("https://fonts.googleapis.com/css?family=Nunito+Sans:400,700&display=swap");
                body {
                  width: 100% !important;
                  height: 100%;
                  margin: 0;
                  -webkit-text-size-adjust: none;
                }

                a {
                  color: #3869D4;
                }

                a img {
                  border: none;
                }

                td {
                  word-break: break-word;
                }

                .preheader {
                  display: none !important;
                  visibility: hidden;
                  mso-hide: all;
                  font-size: 1px;
                  line-height: 1px;
                  max-height: 0;
                  max-width: 0;
                  opacity: 0;
                  overflow: hidden;
                }
                /* Type ------------------------------ */

                body,
                td,
                th {
                  font-family: "Nunito Sans", Helvetica, Arial, sans-serif;
                }

                h1 {
                  margin-top: 0;
                  color: #333333;
                  font-size: 22px;
                  font-weight: bold;
                  text-align: left;
                }

                h2 {
                  margin-top: 0;
                  color: #333333;
                  font-size: 16px;
                  font-weight: bold;
                  text-align: left;
                }

                h3 {
                  margin-top: 0;
                  color: #333333;
                  font-size: 14px;
                  font-weight: bold;
                  text-align: left;
                }

                td,
                th {
                  font-size: 16px;
                }

                p,
                ul,
                ol,
                blockquote {
                  margin: .4em 0 1.1875em;
                  font-size: 16px;
                  line-height: 1.625;
                }

                p.sub {
                  font-size: 13px;
                }
                /* Utilities ------------------------------ */

                .align-right {
                  text-align: right;
                }

                .align-left {
                  text-align: left;
                }

                .align-center {
                  text-align: center;
                }

                .u-margin-bottom-none {
                  margin-bottom: 0;
                }
                /* Buttons ------------------------------ */

                .button {
                  background-color: #3869D4;
                  border-top: 10px solid #3869D4;
                  border-right: 18px solid #3869D4;
                  border-bottom: 10px solid #3869D4;
                  border-left: 18px solid #3869D4;
                  display: inline-block;
                  color: #FFF;
                  text-decoration: none;
                  border-radius: 3px;
                  box-shadow: 0 2px 3px rgba(0, 0, 0, 0.16);
                  -webkit-text-size-adjust: none;
                  box-sizing: border-box;
                }

                .button--green {
                  background-color: #22BC66;
                  border-top: 10px solid #22BC66;
                  border-right: 18px solid #22BC66;
                  border-bottom: 10px solid #22BC66;
                  border-left: 18px solid #22BC66;
                }

                .button--red {
                  background-color: #FF6136;
                  border-top: 10px solid #FF6136;
                  border-right: 18px solid #FF6136;
                  border-bottom: 10px solid #FF6136;
                  border-left: 18px solid #FF6136;
                }

                @media only screen and (max-width: 500px) {
                  .button {
                    width: 100% !important;
                    text-align: center !important;
                  }
                }
                /* Attribute list ------------------------------ */

                .attributes {
                  margin: 0 0 21px;
                }

                .attributes_content {
                  background-color: #F4F4F7;
                  padding: 16px;
                }

                .attributes_item {
                  padding: 0;
                }
                /* Related Items ------------------------------ */

                .related {
                  width: 100%;
                  margin: 0;
                  padding: 25px 0 0 0;
                  -premailer-width: 100%;
                  -premailer-cellpadding: 0;
                  -premailer-cellspacing: 0;
                }

                .related_item {
                  padding: 10px 0;
                  color: #CBCCCF;
                  font-size: 15px;
                  line-height: 18px;
                }

                .related_item-title {
                  display: block;
                  margin: .5em 0 0;
                }

                .related_item-thumb {
                  display: block;
                  padding-bottom: 10px;
                }

                .related_heading {
                  border-top: 1px solid #CBCCCF;
                  text-align: center;
                  padding: 25px 0 10px;
                }
                /* Discount Code ------------------------------ */

                .discount {
                  width: 100%;
                  margin: 0;
                  padding: 24px;
                  -premailer-width: 100%;
                  -premailer-cellpadding: 0;
                  -premailer-cellspacing: 0;
                  background-color: #F4F4F7;
                  border: 2px dashed #CBCCCF;
                }

                .discount_heading {
                  text-align: center;
                }

                .discount_body {
                  text-align: center;
                  font-size: 15px;
                }
                /* Social Icons ------------------------------ */

                .social {
                  width: auto;
                }

                .social td {
                  padding: 0;
                  width: auto;
                }

                .social_icon {
                  height: 20px;
                  margin: 0 8px 10px 8px;
                  padding: 0;
                }
                /* Data table ------------------------------ */

                .purchase {
                  width: 100%;
                  margin: 0;
                  padding: 35px 0;
                  -premailer-width: 100%;
                  -premailer-cellpadding: 0;
                  -premailer-cellspacing: 0;
                }

                .purchase_content {
                  width: 100%;
                  margin: 0;
                  padding: 25px 0 0 0;
                  -premailer-width: 100%;
                  -premailer-cellpadding: 0;
                  -premailer-cellspacing: 0;
                }

                .purchase_item {
                  padding: 10px 0;
                  color: #51545E;
                  font-size: 15px;
                  line-height: 18px;
                }

                .purchase_heading {
                  padding-bottom: 8px;
                  border-bottom: 1px solid #EAEAEC;
                }

                .purchase_heading p {
                  margin: 0;
                  color: #85878E;
                  font-size: 12px;
                }

                .purchase_footer {
                  padding-top: 15px;
                  border-top: 1px solid #EAEAEC;
                }

                .purchase_total {
                  margin: 0;
                  text-align: right;
                  font-weight: bold;
                  color: #333333;
                }

                .purchase_total--label {
                  padding: 0 15px 0 0;
                }

                body {
                  background-color: #F2F4F6;
                  color: #51545E;
                }

                p {
                  color: #51545E;
                }

                .email-wrapper {
                  width: 100%;
                  margin: 0;
                  padding: 0;
                  -premailer-width: 100%;
                  -premailer-cellpadding: 0;
                  -premailer-cellspacing: 0;
                  background-color: #F2F4F6;
                }

                .email-content {
                  width: 100%;
                  margin: 0;
                  padding: 0;
                  -premailer-width: 100%;
                  -premailer-cellpadding: 0;
                  -premailer-cellspacing: 0;
                }
                /* Masthead ----------------------- */

                .email-masthead {
                  padding: 25px 0;
                  text-align: center;
                }

                .email-masthead_logo {
                  width: 94px;
                }

                .email-masthead_name {
                  font-size: 16px;
                  font-weight: bold;
                  color: #A8AAAF;
                  text-decoration: none;
                  text-shadow: 0 1px 0 white;
                }
                /* Body ------------------------------ */

                .email-body {
                  width: 100%;
                  margin: 0;
                  padding: 0;
                  -premailer-width: 100%;
                  -premailer-cellpadding: 0;
                  -premailer-cellspacing: 0;
                }

                .email-body_inner {
                  width: 570px;
                  margin: 0 auto;
                  padding: 0;
                  -premailer-width: 570px;
                  -premailer-cellpadding: 0;
                  -premailer-cellspacing: 0;
                  background-color: #FFFFFF;
                }

                .email-footer {
                  width: 570px;
                  margin: 0 auto;
                  padding: 0;
                  -premailer-width: 570px;
                  -premailer-cellpadding: 0;
                  -premailer-cellspacing: 0;
                  text-align: center;
                }

                .email-footer p {
                  color: #A8AAAF;
                }

                .body-action {
                  width: 100%;
                  margin: 30px auto;
                  padding: 0;
                  -premailer-width: 100%;
                  -premailer-cellpadding: 0;
                  -premailer-cellspacing: 0;
                  text-align: center;
                }

                .body-sub {
                  margin-top: 25px;
                  padding-top: 25px;
                  border-top: 1px solid #EAEAEC;
                }

                .content-cell {
                  padding: 45px;
                }
                /*Media Queries ------------------------------ */

                @media only screen and (max-width: 600px) {
                  .email-body_inner,
                  .email-footer {
                    width: 100% !important;
                  }
                }

                @media (prefers-color-scheme: dark) {
                  body,
                  .email-body,
                  .email-body_inner,
                  .email-content,
                  .email-wrapper,
                  .email-masthead,
                  .email-footer {
                    background-color: #333333 !important;
                    color: #FFF !important;
                  }
                  p,
                  ul,
                  ol,
                  blockquote,
                  h1,
                  h2,
                  h3,
                  span,
                  .purchase_item {
                    color: #FFF !important;
                  }
                  .attributes_content,
                  .discount {
                    background-color: #222 !important;
                  }
                  .email-masthead_name {
                    text-shadow: none !important;
                  }
                }

                :root {
                  color-scheme: light dark;
                  supported-color-schemes: light dark;
                }
                </style>
                <!--[if mso]>
                <style type="text/css">
                  .f-fallback  {
                    font-family: Arial, sans-serif;
                  }
                </style>
              <![endif]-->
              </head>
              <body>
                <span class="preheader">This is a receipt for your recent purchase on {date}.</span>
                <table class="email-wrapper" width="100%" cellpadding="0" cellspacing="0" role="presentation">
                  <tr>
                    <td align="center">
                      <table class="email-content" width="100%" cellpadding="0" cellspacing="0" role="presentation">
                        <tr>
                          <td class="email-masthead">
                            <a href="https://davidwalshgas.com.au" class="f-fallback email-masthead_name">
                            <img src="https://davidwalshgas.com.au/DWG_logo.jpg" alt="David Walsh Gas" width="200" height="50" style="display: block; align: center;" />
                          </a>
                          </td>
                        </tr>
                        <!-- Email Body -->
                        <tr>
                          <td class="email-body" width="570" cellpadding="0" cellspacing="0">
                            <table class="email-body_inner" align="center" width="570" cellpadding="0" cellspacing="0" role="presentation">
                              <!-- Body content -->
                              <tr>
                                <td class="content-cell">
                                  <div class="f-fallback">
                                    <h1>Hi {name},</h1>
                                    <p>Thank you for choosing David Walsh Gas. This email is the receipt for your payment.</p>
                                    <p>This purchase will appear as "David Walsh Gas PTY LTD" on your bank statement.</p>
                                    <table class="purchase" width="100%" cellpadding="0" cellspacing="0" role="presentation">
                                      <tr>
                                        <td>
                                          <h3>Reference: {authCode}</h3></td>
                                        <td>
                                          <h3 class="align-right">{date}</h3></td>
                                      </tr>
                                      <tr>
                                        <td colspan="2">
                                          <table class="purchase_content" width="100%" cellpadding="0" cellspacing="0">
                                            <tr>
                                              <th class="purchase_heading" align="left">
                                                <p class="f-fallback">Description</p>
                                              </th>
                                              <th class="purchase_heading" align="right">
                                                <p class="f-fallback">Amount</p>
                                              </th>
                                            </tr>
                                            <tr>
                                              <td width="80%" class="purchase_item"><span class="f-fallback">EFTPOS Payment</span></td>
                                              <td class="align-right" width="20%" class="purchase_item"><span class="f-fallback">{amount}</span></td>
                                            </tr>
                                            <tr>
                                              <td width="80%" class="purchase_footer" valign="middle">
                                                <p class="f-fallback purchase_total purchase_total--label">Total</p>
                                              </td>
                                              <td width="20%" class="purchase_footer" valign="middle">
                                                <p class="f-fallback purchase_total">{amount}</p>
                                              </td>
                                            </tr>
                                          </table>
                                        </td>
                                      </tr>
                                    </table>
                                    <p>If you have any questions about this receipt, simply reply to this email or reach out to our <a href="tel:0358742246">Office</a> for help.</p>
                                    <p>Thank you,
                                      <br>The David Walsh Gas team</p>
                                    <!-- Action -->
                                  </div>
                                </td>
                              </tr>
                            </table>
                          </td>
                        </tr>
                        <tr>
                          <td>
                            <table class="email-footer" align="center" width="570" cellpadding="0" cellspacing="0" role="presentation">
                              <tr>
                                <td class="content-cell" align="center">
                                  <p class="f-fallback sub align-center">
                                    David Walsh Gas Pty Ltd
                                    <br>94 Deniliquin Street, Tocumwal, NSW, 2714
                                    <br>ABN: 62 003 477 352
                                  </p>
                                </td>
                              </tr>
                            </table>
                          </td>
                        </tr>
                      </table>
                    </td>
                  </tr>
                </table>
              </body>
            </html>
            
            """

# Create a set of response codes and their meanings
response_codes = {
    "APPROVED": "Success: The transaction was approved.",
    "DECLINED": "Error: The customer’s bank declined the transaction.\nNext Steps: The customer should use an "
    "alternate card and contact their bank.",
    "PICKUP_CARD": "Error: The customer’s bank declined the transaction because the card was reported lost or "
    "stolen.\nNext Steps: The customer should use an alternate card and contact their bank.",
    "HOT_CARD": "Error: The customer’s bank declined the transaction because the card was reported lost or "
    "stolen.\nNext Steps: The customer should use an alternate card and contact their bank.",
    "LOST_CARD_PICKUP": "Error: The customer’s bank declined the transaction because the card was reported lost or "
    "stolen.\nNext Steps: The customer should use an alternate card and contact their bank.",
    "SUSPECTED_FRAUD": "Error: The customer’s bank declined the transaction because it suspects fraud.\nNext Steps: "
    "The customer should contact their bank for more information.",
    "EXPIRED_CARD": "Error: The customer’s bank declined the transaction because the card is expired.\nNext Steps: "
    "The customer should use an alternate card. If the customer believes that the card is still "
    "valid, they should contact their bank.",
    "CVC_MISMATCH": "Error: The customer’s bank declined the transaction because the card’s security code (CVV) did "
    "not match.\nNext Steps: The customer should try again using the correct security code.",
    "INVALID_MERCHANT": "Error: The customer’s bank declined the transaction because they don’t allow transactions "
    "from us.\nNext Steps: The customer should contact their bank for more information.",
    "INVALID_CURRENCY": "Error: The customer’s bank declined the transaction because the card does not allow "
    "transactions in AUD.\nNext Steps: The customer should use an alternate card and contact "
    "their bank.",
    "CARD_TYPE_NOT_ENABLED": "Error: The customer’s bank declined the transaction because this type of payment is not "
    "allowed.\nNext Steps: The customer should use an alternate card and contact their bank.",
    "SYSTEM_ERROR": "Error: The customer’s bank declined the transaction due to a technical issue.\nNext Steps: The "
    "customer should try again later or pay using an alternate method.",
    "LIMIT_EXCEEDED": "Error: The customer’s bank declined the transaction because it will exceed the customer’s card "
    "limit.\nNext Steps: The customer should use an alternate card or try again tomorrow.",
    "MERCHANT_LOCKED_OR_CLOSED": "Error: The customer’s bank declined the transaction because the merchant’s account "
    "is locked or closed.\nNext Steps: The customer should use an alternate card and "
    "contact their bank.",
    "TOO_MANY_DECLINES": "Error: The customer’s bank declined the transaction due to too many recent transactions "
    "failing.\nNext Steps: The customer should use an alternate card or contact their bank.",
    "INVALID_CARD_NUMBER": "Error: The customer’s bank declined the transaction because the card number is "
    "invalid.\nNext Steps: The customer should check their card number and try again.",
    "DO_NOT_HONOUR": "Error: The customer’s bank declined the transaction but did not provide any more "
    "information.\nNext Steps: The customer should check the card details and try again.",
    "RESTRICTED_CARD": "Error: The customer’s bank declined the transaction because the card cannot be used for this "
    "type of transaction.\nNext Steps: The customer should use an alternate card and contact their"
    " bank.",
    "INSUFFICIENT_FUNDS": "Error: The customer’s bank declined the transaction due to insufficient funds in their "
    "account\nNext Steps: The customer should use an alternate card or transfer some funds.",
    "UNKNOWN": "Error: The customer’s bank declined the transaction for an unknown reason.\nNext Steps: The customer "
    "should try again or contact their bank.",
    "TOO_MANY_RETRIES": "Error: The customer’s bank declined the transaction due to too many recent transactions "
    "failing to process.\nNext Steps: The customer should use an alternate card or contact their "
    "bank.",
    "TIMED_OUT": "Error: The customer’s bank declined the transaction because it took too long to process.\nNext "
    "Steps: Retry the transaction. If this error persists, contact Trent.",
    "NOT_SUPPORTED": "Error: The customer’s bank declined the transaction because the card does not support this type "
    "of transaction.\nNext Steps: The customer should use an alternate card and contact their bank.",
    "CANCELLED": "Error: The customer’s bank declined the transaction because the customer cancelled the "
    "transaction.\nNext Steps: The customer should try again.",
    "BLOCKED": "Error: The customer’s bank declined the transaction because the card does not support this type "
    "of transaction.\nNext Steps: The customer should use an alternate card and contact their bank.",
    "SECURE_3D_AUTH_FAILED": "Error: The customer’s bank declined the transaction because the card has security "
    "requirements that prevent it from being used for this transaction.\nNext Steps: The "
    "customer should use an alternate card and contact their bank.",
    "OTHER": "Error: The customer’s bank declined the transaction for an unknown reason.\nNext Steps: The customer "
    "should contact their bank for more information.",
}


def get_display_name(EXTENDED_NAME_FORMAT: int):
    GetUserNameEx = ctypes.windll.secur32.GetUserNameExW
    data = EXTENDED_NAME_FORMAT

    size = ctypes.pointer(ctypes.c_ulong(0))
    GetUserNameEx(data, None, size)

    nameBuffer = ctypes.create_unicode_buffer(size.contents.value)
    GetUserNameEx(data, nameBuffer, size)
    return nameBuffer.value


def update_recent_transactions():
    # load the CSV from the C:/ drive
    global transactions
    transactions = []
    count = 0
    try:
        with open("U:/POS/transactions.csv", "r") as f:
            reader = csv.reader(f)
            for row in reader:
                # if the row is empty, skip it
                if not row:
                    continue
                transactions.append(row)
        transactions.reverse()
        # set the transaction list to a max length of 30
        transactions = transactions[:31]
        # clear the recent transactions list
        recentTransactionsList.clear()
        for i in transactions:
            if i[2] == "APPROVED":
                status = "✅"
            elif "DECLINED" in i[2]:
                status = "❌"
            else:
                status = "⚠️"
            recentTransactionsList.addItem(f"{count} {status} {i[0]} - {i[1]}")
            count += 1
            recentTransactionsLoaderLabel.hide()
            recentTransactionsLoader.stop()
    except FileNotFoundError:
        pass
    except BaseException as e:
        # Append the traceback to U:/POS/failed_payments.txt -- date - username - error
        error = "Error on line {}".format(sys.exc_info()[-1].tb_lineno), type(e).__name__, e
        with open("U:/POS/failed_payments.txt", "a") as f:
            f.write(
                f"{datetime.datetime.now()} - {get_display_name(3)} - {error}\n"
            )
        # print complete error with line number
        print(error)
        pass


def apply_payment(account, authCode, amount):
    try:
        try:
            if DEBUG:
                authCode = "TESTING"
            if account == "00000":
                message = f"Payment successful.\nReference: {authCode}"
                return (message)
            date = datetime.datetime.now().strftime("%Y-%m-%d")
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Connect to the database
            conn = psycopg2.connect(
                database=os.getenv("DATABASE_NAME"),
                user=os.getenv("DATABASE_USER"),
                password=os.getenv("DATABASE_PASS"),
                host=os.getenv("DATABASE_HOST"),
                port="5432",
            )
            print("connected")
            cur = conn.cursor()
            print("created cursor")
            amount = float(amount)
            print(account)
            if account.isnumeric():
                print("Is numeric")
                cur.execute(f"SELECT * FROM account WHERE acct = {account}")
                row = cur.fetchone()
                print(row)
            else:
                row = None
            if row is None:
                # Send this failure to pushover API
                message = f"Payment successful, but account {account} not found.\nReference: {authCode}"
                r = requests.post(
                    "https://api.pushover.net/1/messages.json",
                    data={
                        "token": os.getenv("PUSHOVER_FAILURE"),
                        "user": os.getenv("PUSHOVER_USER"),
                        "message": f"Account {account} not found. Reference: {authCode} Amount: {amount}\n"
                    },
                )
                return (message)
            else:
                # Get the current balance of their account
                original_balance = row[10]
                # Update the balance
                new_balance = float(original_balance) - float(amount)
                print(original_balance)
                print(new_balance)
                # Get the location key for this account
                cur.execute(f"SELECT * FROM location WHERE account = {row[0]}")
                location_key = cur.fetchone()[0] ## 5608
                cur.execute(
                    f"INSERT INTO public.transactiongroup (account, reference, postdate, trxdate, type, usr, "
                    f"time_stamp, amount, running_balance, reverse_transaction, open, invoiced, hidden, location_key, tank_key"
                    f") VALUES ('{account}'::integer, '{authCode}'::text, '{date}'::date, '{date}'::date, "
                    f"'1'::integer, '13'::integer, '{timestamp}'::timestamp without time zone, "
                    f"'-{amount}'::numeric, {new_balance}::numeric, false::boolean, '-{amount}'::numeric, false::boolean, false::boolean, "
                    f"'{location_key}'::integer, '0'::integer) returning transaction_group;"
                )
                trxid = cur.fetchone()[0]
                cur.execute(
                    f"INSERT INTO public.transaction (transaction_group, account, reference, postdate, trxdate, type, usr, "
                    f"time_stamp, amount, balance, reverse_transaction, location_key, tax_group, code"
                    f") VALUES ('{trxid}'::integer, '{account}'::integer, '{authCode}'::text, '{date}'::date, '{date}'::date, "
                    f"'1'::integer, '13'::integer, '{timestamp}'::timestamp without time zone, "
                    f"'{amount}'::numeric, {new_balance}::numeric, false::boolean, "
                    f"'{location_key}'::integer, '2'::integer, '2'::integer);"
                )
                # Update the account balance
                cur.execute(
                    f"UPDATE account SET balance = {new_balance} WHERE acct = {account}"
                )
                # Fetch the computer name
                computer = os.environ["COMPUTERNAME"]
                user = get_display_name(3)
                note = f"Payment applied by {user} on {computer}"
                # Add a note to the account
                cur.execute(
                    f"INSERT INTO transactiongroupnote (transaction_group, note) VALUES ('{trxid}'::integer, '{note}'::text);"
                )
                conn.commit()
                message = f"Payment successful and applied to account {account}.\nReference: {authCode}"
                # r = requests.post(
                #     "https://api.pushover.net/1/messages.json",
                #     data={
                #         "token": os.getenv("PUSHOVER_SUCCESS")
                #         "user": os.getenv("PUSHOVER_USER"),
                #         "message": message + "\n" + note,
                #     },
                # )
                return (message)
        except IndexError as e:
            # Append the traceback to U:/POS/failed_payments.txt -- date - username - error
            error = "Error on line {}".format(sys.exc_info()[-1].tb_lineno), type(e).__name__, e
            with open("U:/POS/failed_payments.txt", "a") as f:
                f.write(
                    f"{datetime.datetime.now()} - {get_display_name(3)} - {error}\n"
                )
            # print complete error with line number
            print(error)
            # Send this failure to pushover API
            message = f"Payment successful, but account {account} not found.\nReference: {authCode}"
            r = requests.post(
                "https://api.pushover.net/1/messages.json",
                data={
                    "token": os.getenv("PUSHOVER_FAILURE"),
                    "user": os.getenv("PUSHOVER_USER"),
                    "message": f"Account {account} not found. Reference: {authCode} Amount: {amount}\n"
                },
            )
            return (message)
    except BaseException as e:
        # Append the traceback to U:/POS/failed_payments.txt -- date - username - error
        error = "Error on line {}".format(sys.exc_info()[-1].tb_lineno), type(e).__name__, e
        with open("U:/POS/failed_payments.txt", "a") as f:
            f.write(
                f"{datetime.datetime.now()} - {get_display_name(3)} - {error}\n"
            )
        # print complete error with line number
        print(error)
        # Send this failure to pushover API
        message = f"Payment successful, but account {account} not found.\nReference: {authCode}"
        r = requests.post(
            "https://api.pushover.net/1/messages.json",
            data={
                "token": os.getenv("PUSHOVER_FAILURE"),
                "user": os.getenv("PUSHOVER_USER"),
                "message": f"Account {account} not found. Reference: {authCode} Amount: {amount}\n"
            },
        )
        return (message)

def process_payment():
    mbox = QMessageBox()
    mbox.setWindowTitle("Payment Status")
    mbox.setWindowIcon(QIcon("U:/POS/pos.ico"))
    try:
        amount = amountInput.text().strip("$")
        # Convert dollars to cents
        amount = decimal.Decimal(amount) * 100
        amount = int(amount)
        # if the amount is greater than 300,000 cents, then it is too large
        if amount > 300000:
            EVT_STRS = [
                f"Payment declined due to excessive amount. Amount was: ${amount / 100}"
            ]
            win32evtlogutil.ReportEvent(
                APP_NAME,
                EVT_ID,
                eventCategory=EVT_CATEG,
                eventType=win32evtlog.EVENTLOG_WARNING_TYPE,
                strings=EVT_STRS,
            )
            message = EVT_STRS[0]
            r = requests.post(
                "https://api.pushover.net/1/messages.json",
                data={
                    "token": os.getenv("PUSHOVER_FAILURE"),
                    "user": os.getenv("PUSHOVER_USER"),
                    "message": message,
                },
            )
            mbox.setText(
                "Error: This amount is too large. Please use the physical machine."
            )
            mbox.exec_()
            # save this transaction to the CSV
            with open("U:/POS/transactions.csv", "a") as f:
                writer = csv.writer(f)
                if customerInput.text() == "":
                    writer.writerow(
                        ["None", amountInput.text(), "DECLINED", int(time.time())]
                    )
                else:
                    writer.writerow(
                        [
                            customerInput.text(),
                            amountInput.text(),
                            "DECLINED",
                            int(time.time()),
                        ]
                    )
            return

        cardNumber = cardNumberInput.text().replace(" ", "")
        payment = simplify.Payment.create(
            {
                "card": {
                    "number": cardNumber,
                    "expMonth": cardExpiryInput.text().split("/")[0],
                    "expYear": cardExpiryInput.text().split("/")[1],
                    "cvc": cardCVCInput.text(),
                },
                "order": {"customerName": customerInput.text()},
                "amount": amount,  # NOTE THIS IS IN CENTS, NOT DOLLARS
                "description": customerInput.text(),
                "currency": "AUD",
            }
        )
        # Log process of payment
        EVT_STRS = [f"Processed payment:\n{payment}"]
        win32evtlogutil.ReportEvent(
            APP_NAME,
            EVT_ID,
            eventCategory=EVT_CATEG,
            eventType=win32evtlog.EVENTLOG_INFORMATION_TYPE,
            strings=EVT_STRS,
        )
        # Check payment status
        if payment.paymentStatus == "APPROVED":
            # save this transaction to the CSV
            with open("U:/POS/transactions.csv", "a") as f:
                writer = csv.writer(f)
                if customerInput.text() == "":
                    writer.writerow(
                        [
                            "None",
                            amountInput.text(),
                            "APPROVED",
                            int(time.time()),
                            payment.authCode,
                        ]
                    )
                else:
                    writer.writerow(
                        [
                            customerInput.text(),
                            amountInput.text(),
                            "APPROVED",
                            int(time.time()),
                            payment.authCode,
                        ]
                    )
            applied_payment = apply_payment(
                    customerInput.text().split(" ")[0], payment.authCode, amount / 100
                )
            if "applied to account" not in applied_payment:
                pyperclip.copy(payment.authCode)
            # applied_payment = f"Payment successful.\nReference: {payment.authCode}"
            mbox.setText(applied_payment)
            # Log if payment was applied
            EVT_STRS = [f"Applied payment:\n{applied_payment}"]
            win32evtlogutil.ReportEvent(
                APP_NAME,
                EVT_ID,
                eventCategory=EVT_CATEG,
                eventType=win32evtlog.EVENTLOG_INFORMATION_TYPE,
                strings=EVT_STRS,
            )
            # reset the input fields
            cardNumberInput.setText("")
            cardExpiryInput.setText("")
            cardCVCInput.setText("")
            customerInput.setText("")
            amountInput.setText("$")
            # reset the borders
            cardNumberInput.setStyleSheet("")
            customerInput.setStyleSheet("")
            # set the cursor back to the amount input
            customerInput.setFocus()

        elif payment.paymentStatus == "DECLINED":
            if payment.declineReason in response_codes:
                mbox.setText(response_codes[payment.declineReason])
                # save this transaction to the CSV
                with open("U:/POS/transactions.csv", "a") as f:
                    writer = csv.writer(f)
                    if customerInput.text() == "":
                        writer.writerow(
                            [
                                "None",
                                amountInput.text(),
                                f"DECLINED - {response_codes[payment.declineReason]}",
                                int(time.time()),
                            ]
                        )
                    else:
                        writer.writerow(
                            [
                                customerInput.text(),
                                amountInput.text(),
                                f"DECLINED - {response_codes[payment.declineReason]}",
                                int(time.time()),
                            ]
                        )
            else:
                mbox.setText(
                    f"Error: The payment status is unknown ({payment.paymentStatus})"
                )
                # save this transaction to the CSV
                message = f"Payment failed. Unknown error.\n{payment.paymentStatus}"
                r = requests.post(
                    "https://api.pushover.net/1/messages.json",
                    data={
                        "token": os.getenv("PUSHOVER_FAILURE"),
                        "user": os.getenv("PUSHOVER_USER"),
                        "message": message,
                    },
                )
                with open("U:/POS/transactions.csv", "a") as f:
                    writer = csv.writer(f)
                    if customerInput.text() == "":
                        writer.writerow(
                            ["None", amountInput.text(), "unknown", int(time.time())]
                        )
                    else:
                        writer.writerow(
                            [
                                customerInput.text(),
                                amountInput.text(),
                                "unknown",
                                int(time.time()),
                            ]
                        )
        else:
            mbox.setText(
                f"Error: The payment status is unknown ({payment.paymentStatus})"
            )
            # save this transaction to the CSV
            with open("U:/POS/transactions.csv", "a") as f:
                writer = csv.writer(f)
                if customerInput.text() == "":
                    writer.writerow(
                        ["None", amountInput.text(), "unknown", int(time.time())]
                    )
                else:
                    writer.writerow(
                        [
                            customerInput.text(),
                            amountInput.text(),
                            "unknown",
                            int(time.time()),
                        ]
                    )
    except simplify.BadRequestError as e:
        mbox.setText(response_codes["INVALID_CARD_NUMBER"])
        # save this transaction to the CSV
        with open("U:/POS/transactions.csv", "a") as f:
            writer = csv.writer(f)
            if customerInput.text() == "":
                writer.writerow(
                    [
                        "None",
                        amountInput.text(),
                        f"DECLINED - {response_codes['INVALID_CARD_NUMBER']}",
                        int(time.time()),
                    ]
                )
            else:
                writer.writerow(
                    [
                        customerInput.text(),
                        amountInput.text(),
                        f"DECLINED - {response_codes['INVALID_CARD_NUMBER']}",
                        int(time.time()),
                    ]
                )
        # Log error
        EVT_STRS = [f"Payment Failed: {e.message}"]
        win32evtlogutil.ReportEvent(
            APP_NAME,
            EVT_ID,
            eventCategory=EVT_CATEG,
            eventType=win32evtlog.EVENTLOG_ERROR_TYPE,
            strings=EVT_STRS,
        )
        message = EVT_STRS[0]
        r = requests.post(
            "https://api.pushover.net/1/messages.json",
            data={
                "token": os.getenv("PUSHOVER_FAILURE"),
                "user": os.getenv("PUSHOVER_USER"),
                "message": message,
            },
        )
    # catch programmingerror and undefinedcolumn
    except psycopg2.errors.UndefinedColumn as e:
        mbox.setText("The account number is invalid, please check the payment was successful in the recent transactions list.")
        # Append the traceback to U:/POS/failed_payments.txt -- date - username - error
        error = "Error on line {}".format(sys.exc_info()[-1].tb_lineno), type(e).__name__, e
        with open("U:/POS/failed_payments.txt", "a") as f:
            f.write(
                f"{datetime.datetime.now()} - {get_display_name(3)} - {error}\n"
            )
        cardNumberInput.setText("")
        cardExpiryInput.setText("")
        cardCVCInput.setText("")
        customerInput.setText("")
        amountInput.setText("$")
        cardNumberInput.setStyleSheet("")
        customerInput.setStyleSheet("")
        customerInput.setFocus()
    except psycopg2.errors.ProgrammingError as e:
        mbox.setText("The account number is invalid, please check the payment was successful in the recent transactions list.")
        # Append the traceback to U:/POS/failed_payments.txt -- date - username - error
        error = "Error on line {}".format(sys.exc_info()[-1].tb_lineno), type(e).__name__, e
        with open("U:/POS/failed_payments.txt", "a") as f:
            f.write(
                f"{datetime.datetime.now()} - {get_display_name(3)} - {error}\n"
            )
        cardNumberInput.setText("")
        cardExpiryInput.setText("")
        cardCVCInput.setText("")
        customerInput.setText("")
        amountInput.setText("$")
        cardNumberInput.setStyleSheet("")
        customerInput.setStyleSheet("")
        customerInput.setFocus()

    except BaseException as e:
        mbox.setText(
            "An error has occurred. Please check your inputs and try again.     "
        )
        # Log error
        EVT_STRS = [f"Payment Failed: {e}"]
        win32evtlogutil.ReportEvent(
            APP_NAME,
            EVT_ID,
            eventCategory=EVT_CATEG,
            eventType=win32evtlog.EVENTLOG_ERROR_TYPE,
            strings=EVT_STRS,
        )
        message = EVT_STRS[0]
        r = requests.post(
            "https://api.pushover.net/1/messages.json",
            data={
                "token": os.getenv("PUSHOVER_FAILURE"),
                "user": os.getenv("PUSHOVER_USER"),
                "message": message,
            },
        )
        # Append the traceback to U:/POS/failed_payments.txt -- date - username - error
        error = "Error on line {}".format(sys.exc_info()[-1].tb_lineno), type(e).__name__, e
        with open("U:/POS/failed_payments.txt", "a") as f:
            f.write(
                f"{datetime.datetime.now()} - {get_display_name(3)} - {error}\n"
            )
        # print complete error with line number
        print(error)
        pass
        mbox.setDetailedText(str(error))
    mbox.setStandardButtons(QMessageBox.Ok)
    mbox.exec_()


def get_email(name, amount, date, authCode):
    # show a dialog asking for the email address
    global emailDialog
    global emailInput
    global emailButton
    emailDialog = QDialog()
    emailDialog.setWindowTitle("Email Receipt")
    emailDialog.setWindowIcon(QIcon("U:/POS/pos.ico"))
    emailDialog.resize(300, 100)
    emailDialog.setFixedHeight(100)
    emailDialog.setFixedWidth(300)
    emailDialog.setWindowModality(Qt.ApplicationModal)
    emailDialog.setWindowFlags(Qt.WindowCloseButtonHint)
    emailInput = QLineEdit(emailDialog)
    emailInput.setPlaceholderText("Email Address")
    emailInput.setGeometry(10, 10, 280, 20)
    emailButton = QPushButton("Send", emailDialog)
    emailButton.setGeometry(10, 40, 280, 20)
    emailInput.returnPressed.connect(
        lambda: [
            email_receipt(name, amount, date, authCode, emailInput.text()),
            emailDialog.close(),
        ]
    )
    emailButton.clicked.connect(
        lambda: [
            email_receipt(name, amount, date, authCode, emailInput.text()),
            emailDialog.close(),
        ]
    )
    # Get the customer's email from the database and prefill the email input if it exists
    try:
        account = name.split(" ")[0]
        conn = psycopg2.connect(
            database=os.getenv("DATABASE_NAME"),
            user=os.getenv("DATABASE_USER"),
            password=os.getenv("DATABASE_PASS"),
            host=os.getenv("DATABASE_HOST"),
            port="5432",
        )
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM account WHERE acct = {account}")
        row = cur.fetchone()
        email = row[19]
        emailInput.setText(email)
    except IndexError:
        pass
    except psycopg2.errors.UndefinedColumn:
        # incase the account is invalid or somehow an inactive account that is missing the email column
        pass

    emailDialog.exec_()


def email_receipt(name, amount, date, authCode, email):
    try:
        if name.isnumeric():
            name = ""
        else:
            name = f" {name}"
            name = "".join([i for i in name if not i.isdigit()])
        email_content = (
            html_email.replace("{name}", name.strip("- "))
            .replace("{amount}", amount)
            .replace(
                "{date}", time.strftime("%d-%m-%Y %H:%M:%S", time.localtime(int(date)))
            )
            .replace("{authCode}", authCode)
        )
        outlook = win32.Dispatch("outlook.application")
        mail = outlook.CreateItem(0)
        mail.To = email
        mail.Subject = "David Walsh Gas EFTPOS receipt"
        mail.HTMLBody = email_content
        mail.Send()
        EVT_STRS = [
            f"Receipt sent to {email}, for {amount}, on {time.strftime('%d-%m-%Y %H:%M:%S', time.localtime(int(date)))}, with auth code {authCode}, for {name}"
        ]
        win32evtlogutil.ReportEvent(
            APP_NAME,
            EVT_ID,
            eventCategory=EVT_CATEG,
            eventType=win32evtlog.EVENTLOG_INFORMATION_TYPE,
            strings=EVT_STRS,
        )
        # show a dialog saying the email was sent then close after 1.5 seconds
        mbox = QMessageBox()
        mbox.setWindowTitle("Email Receipt")
        mbox.setWindowIcon(QIcon("U:/POS/pos.ico"))
        # show the email icon, centered
        mbox.setIconPixmap(
            QPixmap("U:/POS/email.png").scaledToWidth(50, Qt.SmoothTransformation)
        )
        mbox.setText("Email sent successfully!")
        mbox.setStandardButtons(QMessageBox.Ok)
        QTimer.singleShot(1500, mbox.close)
        mbox.exec_()

    except BaseException as e:
        # Append the traceback to U:/POS/failed_payments.txt -- date - username - error
        error = "Error on line {}".format(sys.exc_info()[-1].tb_lineno), type(e).__name__, e
        with open("U:/POS/failed_payments.txt", "a") as f:
            f.write(
                f"{datetime.datetime.now()} - {get_display_name(3)} - {error}\n"
            )
        # print complete error with line number
        print(error)
        pass


class ListWidget(QListWidget):
    def show_transaction_details(self, item):
        # show the transaction details from the CSV
        global transactionDetailsWindow
        global transactionDetailsList
        global transactionDetailsLabel
        global transactionDetailsLabel2
        global transactionDetailsLabel3
        global transactionDetailsLabel4
        global transactionDetailsLabel5
        global transactionDetailsLabel6
        try:
            transaction = transactions[int(item.text().split(" ")[0])]
            transactionDetailsWindow = QWidget()
            transactionDetailsWindow.resize(250, 200)
            transactionDetailsWindow.setFixedHeight(200)
            transactionDetailsWindow.setFixedWidth(250)
            transactionDetailsWindow.setWindowModality(Qt.ApplicationModal)
            transactionDetailsWindow.setWindowFlags(Qt.WindowCloseButtonHint)
            transactionDetailsWindow.setWindowTitle("Details")
            transactionDetailsWindow.setWindowIcon(QIcon("U:/POS/pos.ico"))

            transactionDetailsLabel2 = QLabel(transactionDetailsWindow)
            transactionDetailsLabel2.setText("Name:")
            transactionDetailsLabel2.move(10, 30)
            transactionDetailsLabel2.show()

            transactionDetailsCustomerName = QLabel(transactionDetailsWindow)
            transactionDetailsCustomerName.move(100, 30)
            transactionDetailsCustomerName.setText(transaction[0])
            transactionDetailsCustomerName.show()

            transactionDetailsLabel3 = QLabel(transactionDetailsWindow)
            transactionDetailsLabel3.setText("Amount:")
            transactionDetailsLabel3.move(10, 60)
            transactionDetailsLabel3.show()

            transactionDetialsAmount = QLabel(transactionDetailsWindow)
            transactionDetialsAmount.move(100, 60)
            transactionDetialsAmount.setText(transaction[1])
            transactionDetialsAmount.show()

            if transaction[2] == "APPROVED":
                status = f"✅ Approved"
                color = "green"
                transactionDetailsLabel5 = QLabel(transactionDetailsWindow)
                transactionDetailsLabel5.setText("Auth Code:")
                transactionDetailsLabel5.move(10, 120)
                transactionDetailsLabel5.show()

                transactionDetailsAuthCode = QLabel(transactionDetailsWindow)
                transactionDetailsAuthCode.move(100, 120)
                transactionDetailsAuthCode.setText(transaction[4])
                transactionDetailsAuthCode.show()

                transactionDetailsReceiptButton = QPushButton(transactionDetailsWindow)
                transactionDetailsReceiptButton.setText("Receipt")
                transactionDetailsReceiptButton.move(10, 170)
                transactionDetailsReceiptButton.show()
                transactionDetailsReceiptButton.clicked.connect(
                    lambda: get_email(
                        transaction[0], transaction[1], transaction[3], transaction[4]
                    )
                )

            elif "DECLINED" in transaction[2]:
                status = f"❌ Declined"
                color = "red"
            else:
                status = f"⚠️ Unknown"
                color = "orange"

            transactionDetailsLabel4 = QLabel(transactionDetailsWindow)
            transactionDetailsLabel4.setText("Status:")
            transactionDetailsLabel4.move(10, 90)
            transactionDetailsLabel4.show()

            transactionDetailsStatus = QLabel(transactionDetailsWindow)
            transactionDetailsStatus.move(100, 90)
            transactionDetailsStatus.setText(status)
            transactionDetailsStatus.setToolTip(transaction[2])
            transactionDetailsStatus.setStyleSheet(f"color: {color};")
            transactionDetailsStatus.show()

            transactionDetailsLabel6 = QLabel(transactionDetailsWindow)
            transactionDetailsLabel6.setText("When:")
            transactionDetailsLabel6.move(10, 150)
            transactionDetailsLabel6.show()

            transactionDetailsWhen = QLabel(transactionDetailsWindow)
            transactionDetailsWhen.move(100, 150)
            transactionDetailsWhen.setText(
                time.strftime(
                    "%d-%m-%Y %H:%M:%S", time.localtime(float(transaction[3]))
                )
            )
            transactionDetailsWhen.show()

            transactionDetailsWindow.show()

        except BaseException as e:
            # Append the traceback to U:/POS/failed_payments.txt -- date - username - error
            error = "Error on line {}".format(sys.exc_info()[-1].tb_lineno), type(e).__name__, e
            with open("U:/POS/failed_payments.txt", "a") as f:
                f.write(
                    f"{datetime.datetime.now()} - {get_display_name(3)} - {error}\n"
                )
            # print complete error with line number
            print(error)
            pass


def check_card(card_number):
    # Luhn's Algorithm, used to check if the card number is valid
    # https://en.wikipedia.org/wiki/Luhn_algorithm
    try:
        # Reverse the card number
        card_number = card_number.replace(" ", "")
        length = len(str(card_number))
        card_number = card_number[::-1]
        # Convert to a list of integers
        card_number = [int(i) for i in card_number]
        # Double every second digit
        card_number = [
            i * 2 if index % 2 == 1 else i for index, i in enumerate(card_number)
        ]
        # Subtract 9 from numbers over 9
        card_number = [i - 9 if i > 9 else i for i in card_number]
        # Sum all digits
        card_number = sum(card_number)
        # If the sum is divisible by 10, it is valid
        if card_number % 10 == 0 and length == 16:
            cardNumberInput.setStyleSheet("border: 2px solid green;")
            cardNumberInput.setToolTip("Card is valid")
            processButton.setEnabled(True)
        else:
            cardNumberInput.setStyleSheet("border: 2px solid red;")
            cardNumberInput.setToolTip("Card is invalid")
            processButton.setEnabled(False)
    except BaseException as e:
        # Append the traceback to U:/POS/failed_payments.txt -- date - username - error
        error = "Error on line {}".format(sys.exc_info()[-1].tb_lineno), type(e).__name__, e
        with open("U:/POS/failed_payments.txt", "a") as f:
            f.write(
                f"{datetime.datetime.now()} - {get_display_name(3)} - {error}\n"
            )
        # print complete error with line number
        print(error)
        pass


def check_account(account):
    # Take the account number from the customer input and check if it is valid,
    # if it is then set the input to green, if not then set it to red
    # Lookup the account via the database and append the name to the customer input
    try:
        if account == "00000":
            customerInput.setText("00000 - ")
        if account.startswith("00000 - "):
            customerInput.setStyleSheet("border: 2px solid green;")
            customerInput.setToolTip("Account doesn't exist")
            return
        if account.isnumeric():
            if len(account) == 5:
                conn = psycopg2.connect(
                    database=os.getenv("DATABASE_NAME"),
                    user=os.getenv("DATABASE_USER"),
                    password=os.getenv("DATABASE_PASS"),
                    host=os.getenv("DATABASE_HOST"),
                    port="5432",
                )
                cur = conn.cursor()
                cur.execute(f"SELECT * FROM account WHERE acct = {account}")
                row = cur.fetchone()
                if row is not None:
                    last_name = row[1]
                    first_name = row[2]
                    balance = row[10]
                    if balance is None:
                        balance = ""
                    if balance <= 0:
                        balance = ""
                    # If the account belongs to a business, the first name will be "None"
                    if first_name == None:
                        customerInput.setText(f"{account} - {last_name}")
                    else:
                        customerInput.setText(f"{account} - {first_name} {last_name}")
                    customerInput.setStyleSheet("border: 2px solid green;")
                    customerInput.setToolTip("Account is valid and active")
                    amountInput.setText(f"${balance}")
                    # Check if the account is active
                    if row[7] is True:
                        print("Account inactive")
                        # Display a confirmation message box
                        mbox = QMessageBox()
                        mbox.setWindowTitle("Account Inactive")
                        mbox.setWindowIcon(QIcon("U:/POS/pos.ico"))
                        mbox.setText(
                            "This account is inactive. Are you sure you want to continue?"
                        )
                        mbox.setStandardButtons(
                            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
                        )
                        mbox.setDefaultButton(QMessageBox.Cancel)
                        # Show the message box and check the result
                        if mbox.exec_() == QMessageBox.Yes:
                            customerInput.setStyleSheet("border: 2px solid orange;")
                            customerInput.setToolTip("Account is inactive")
                        elif mbox.exec_() == QMessageBox.No:
                            customerInput.setText("")
                            customerInput.setToolTip("")
                        else:
                            # Flash the window
                            mbox.setStyleSheet("border: 2px solid red;")
                            customerInput.setStyleSheet("border: 2px solid orange;")
                            customerInput.setToolTip("Account is inactive")
        else:
            customerInput.setStyleSheet("border: 2px solid red;")
            customerInput.setToolTip("Account is invalid")
    except BaseException as e:
        # Append the traceback to U:/POS/failed_payments.txt -- date - username - error
        error = "Error on line {}".format(sys.exc_info()[-1].tb_lineno), type(e).__name__, e
        with open("U:/POS/failed_payments.txt", "a") as f:
            f.write(
                f"{datetime.datetime.now()} - {get_display_name(3)} - {error}\n"
            )
        # print complete error with line number
        print(error)
        pass


def customer_search_dialog():  # A dialog to search for a customer, takes a name as input and returns the account number
    global customerSearchDialog
    global customerSearchInput
    global customerSearchList
    global customerSearchButton
    global customerSearchLabel

    customerSearchDialog = QDialog()
    customerSearchDialog.setWindowTitle("Customer Search")
    customerSearchDialog.setWindowIcon(QIcon("U:/POS/pos.ico"))
    customerSearchDialog.resize(300, 200)
    customerSearchDialog.setFixedHeight(200)
    customerSearchDialog.setFixedWidth(300)
    customerSearchDialog.setWindowModality(Qt.ApplicationModal)
    customerSearchDialog.setWindowFlags(Qt.WindowCloseButtonHint)
    customerSearchDialog.show()

    customerSearchLabel = QLabel(customerSearchDialog)
    customerSearchLabel.setText("Search for a customer:")
    customerSearchLabel.move(10, 10)
    customerSearchLabel.show()

    customerSearchInput = QLineEdit(customerSearchDialog)
    customerSearchInput.returnPressed.connect(customer_search)
    customerSearchInput.move(10, 30)
    customerSearchInput.show()

    customerSearchButton = QPushButton(customerSearchDialog)
    customerSearchButton.setText("Search")
    customerSearchButton.move(10, 60)
    customerSearchButton.show()
    customerSearchButton.clicked.connect(customer_search)

    customerSearchList = QListWidget(customerSearchDialog)
    customerSearchList.move(10, 90)
    customerSearchList.setFixedHeight(100)
    customerSearchList.itemDoubleClicked.connect(customer_search_select)
    customerSearchList.show()


def customer_search():
    # Search for a customer in the database
    try:
        customerSearchList.clear()
        conn = psycopg2.connect(
            database=os.getenv("DATABASE_NAME"),
            user=os.getenv("DATABASE_USER"),
            password=os.getenv("DATABASE_PASS"),
            host=os.getenv("DATABASE_HOST"),
            port="5432",
        )
        cur = conn.cursor()
        cur.execute(
            f"SELECT * FROM account WHERE LOWER(last) LIKE LOWER('%{customerSearchInput.text()}%') OR LOWER(first) LIKE LOWER('%{customerSearchInput.text()}%')"
        )
        rows = cur.fetchall()
        for row in rows:
            customerSearchList.addItem(f"{row[0]} - {row[2]} {row[1]}")
    except BaseException as e:
        # Append the traceback to U:/POS/failed_payments.txt -- date - username - error
        error = "Error on line {}".format(sys.exc_info()[-1].tb_lineno), type(e).__name__, e
        with open("U:/POS/failed_payments.txt", "a") as f:
            f.write(
                f"{datetime.datetime.now()} - {get_display_name(3)} - {error}\n"
            )
        # print complete error with line number
        print(error)
        pass


def customer_search_select():
    # Select a customer from the customer search dialog
    try:
        customerSearchDialog.close()
        customer = customerSearchList.currentItem().text()
        customer = customer.split(" - ")[0]
        customerInput.setText(customer)
        customerInput.setFocus()
        customerInput.setCursorPosition(0)
        customerInput.setStyleSheet("border: 2px solid green;")
    except BaseException as e:
        # Append the traceback to U:/POS/failed_payments.txt -- date - username - error
        error = "Error on line {}".format(sys.exc_info()[-1].tb_lineno), type(e).__name__, e
        with open("U:/POS/failed_payments.txt", "a") as f:
            f.write(
                f"{datetime.datetime.now()} - {get_display_name(3)} - {error}\n"
            )
        # print complete error with line number
        print(error)
        pass


if __name__ == "__main__":
    global amountInput
    global customerInput
    global cardNumberInput
    global cardExpiryInput
    global cardCVCInput
    global recentTransactionsList
    global recentTransactionsLoader
    global recentTransactionsLoaderLabel
    try:
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        w = QWidget()
        w.resize(450, 300)
        w.setWindowTitle(APP_NAME)
        w.setWindowIcon(QIcon("U:/POS/pos.ico"))
        w.setFixedHeight(300)
        w.setFixedWidth(450)

        customerLabel = QLabel(w)
        customerLabel.setText("Customer:")
        customerLabel.move(10, 10)
        customerLabel.show()

        customerSearchButton = QPushButton(w)
        customerSearchButton.setText("Search")
        customerSearchButton.clicked.connect(customer_search_dialog)
        customerSearchButton.move(80, 5)
        customerSearchButton.show()

        customerInput = QLineEdit(w)
        customerInput.setPlaceholderText("Use 00000 for new account")
        customerInput.cursorPositionChanged.connect(
            lambda: check_account(customerInput.text())
        )
        customerInput.returnPressed.connect(
            lambda: [amountInput.setFocus(), amountInput.setCursorPosition(1)]
        )
        customerInput.move(10, 30)
        customerInput.setFixedWidth(150)
        customerInput.show()

        amountLabel = QLabel(w)
        amountLabel.setText("Amount (max $3,000):")
        amountLabel.move(10, 60)
        amountLabel.show()

        amountInput = QLineEdit(w)
        amountInput.setPlaceholderText("$0")
        amountInput.setText("$")
        amountInput.returnPressed.connect(
            lambda: [cardNumberInput.setFocus(), cardNumberInput.setCursorPosition(0)]
        )
        amountInput.move(10, 80)
        amountInput.setFixedWidth(150)
        amountInput.show()

        cardNumberLabel = QLabel(w)
        cardNumberLabel.setText("Card Number:")
        cardNumberLabel.move(10, 110)
        cardNumberLabel.show()

        cardNumberInput = QLineEdit(w)
        cardNumberInput.setInputMask("9999 9999 9999 9999")
        cardNumberInput.cursorPositionChanged.connect(
            lambda: check_card(cardNumberInput.text())
        )
        cardNumberInput.returnPressed.connect(
            lambda: [
                check_card(cardNumberInput.text()),
                cardExpiryInput.setCursorPosition(0),
                cardExpiryInput.setFocus(),
            ]
        )
        cardNumberInput.move(10, 130)
        cardNumberInput.setFixedWidth(150)
        cardNumberInput.show()

        cardExpiryLabel = QLabel(w)
        cardExpiryLabel.setText("Expiry Date:")
        cardExpiryLabel.move(10, 160)
        cardExpiryLabel.show()

        cardExpiryInput = QLineEdit(w)
        cardExpiryInput.setPlaceholderText("MM/YY")
        cardExpiryInput.setInputMask("99/99")
        cardExpiryInput.cursorPositionChanged.connect(
            lambda: check_card(cardNumberInput.text())
        )
        cardExpiryInput.returnPressed.connect(
            lambda: [cardCVCInput.setFocus(), cardCVCInput.setCursorPosition(0)]
        )
        cardExpiryInput.move(10, 180)
        cardExpiryInput.setFixedWidth(150)
        cardExpiryInput.show()

        cardCVCLabel = QLabel(w)
        cardCVCLabel.setText("CVC:")
        cardCVCLabel.move(10, 210)
        cardCVCLabel.show()

        cardCVCInput = QLineEdit(w)
        cardCVCInput.setInputMask("999")
        cardCVCInput.move(10, 230)
        cardCVCInput.setFixedWidth(150)
        cardCVCInput.returnPressed.connect(lambda: [process_payment()])
        cardCVCInput.show()

        clearButton = QPushButton(w)
        clearButton.setText("Clear")
        clearButton.move(45, 260)
        clearButton.show()
        clearButton.clicked.connect(
            lambda: [
                cardNumberInput.setText(""),
                cardExpiryInput.setText(""),
                cardCVCInput.setText(""),
                customerInput.setText(""),
                amountInput.setText("$"),
                cardNumberInput.setStyleSheet(""),
                customerInput.setStyleSheet(""),
                customerInput.setFocus(),
            ]
        )

        processButton = QPushButton(w)
        processButton.setText("Process Payment")
        processButton.move(175, 260)
        processButton.show()
        processButton.autoDefault()
        processButton.setDefault(True)
        processButton.setEnabled(False)
        processButton.clicked.connect(lambda: [process_payment()])

        # Add a recent transactions list on the RHS
        recentTransactionsLabel = QLabel(w)
        recentTransactionsLabel.setText("Recent Transactions:")
        recentTransactionsLabel.move(175, 10)
        recentTransactionsLabel.show()

        recentTransactionsList = ListWidget(w)
        recentTransactionsList.move(175, 30)
        recentTransactionsList.resize(250, 200)
        recentTransactionsList.itemClicked.connect(
            recentTransactionsList.show_transaction_details
        )
        # add a gif when loading
        recentTransactionsLoaderLabel = QLabel(w)
        recentTransactionsLoaderLabel.move(175, 30)
        recentTransactionsLoaderLabel.resize(250, 200)
        recentTransactionsLoaderLabel.show()
        recentTransactionsLoader = QMovie("U:/POS/loader.gif")
        recentTransactionsLoader.setScaledSize(QSize(250, 200))
        recentTransactionsLoader.setSpeed(100)
        recentTransactionsLoader.start()
        recentTransactionsLoaderLabel.setMovie(recentTransactionsLoader)

        # Create a timer to update the recent transactions list
        timer = QTimer()
        timer.timeout.connect(update_recent_transactions)
        timer.start(3500)
        # if we are using the sandbox environment, display a red status bar saying so
        if "sbpb_" in simplify.public_key:
            statusBar = QStatusBar(w)
            statusBar.setStyleSheet("background-color: red; color: white;")
            statusBar.showMessage(
                "Sandbox Environment -- Not for normal use -- Payments are not real"
            )
            statusBar.move(0, 282)
            statusBar.setFixedWidth(450)
            statusBar.show()
        w.show()
        customerInput.setFocus()
        sys.exit(app.exec_())

    except BaseException as e:
        # if it's a system exit, don't show an error
        if type(e).__name__ != "SystemExit":
            # Append the traceback to U:/POS/failed_payments.txt -- date - username - error
            error = "Error on line {}".format(sys.exc_info()[-1].tb_lineno), type(e).__name__, e
            with open("U:/POS/failed_payments.txt", "a") as f:
                f.write(
                    f"{datetime.datetime.now()} - {get_display_name(3)} - {error}\n"
                )
            # print complete error with line number
            print(error)
            pass
