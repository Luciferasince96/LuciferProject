"""Small, local-only Yahoo IMAP/SMTP client. All IMAP IDs are folder-specific UIDs."""
import email
import imaplib
import re
import smtplib
import ssl
from collections import Counter
from contextlib import contextmanager
from email import policy
from email.message import EmailMessage
from email.utils import getaddresses, parseaddr
from html.parser import HTMLParser

from .settings import settings

MAX_SAMPLE = 100
MAX_BODY = 12000

class TextFromHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('style', 'script'):
            self.hidden += 1
        elif tag in ('p', 'br', 'div', 'li', 'tr'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('style', 'script') and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)

def text_body(message):
    part = message.get_body(preferencelist=('plain', 'html'))
    if part is None:
        return '[No readable message body]'
    try:
        text = part.get_content()
    except (LookupError, UnicodeError, AttributeError):
        payload = part.get_payload(decode=True) or b''
        text = payload.decode('utf-8', errors='replace')
    if not isinstance(text, str):
        return '[No readable message body]'
    if part.get_content_type() == 'text/html':
        parser = TextFromHTML()
        parser.feed(text)
        text = ''.join(parser.parts)
    return text.strip()[:MAX_BODY]

def ids_from(value):
    return set(re.findall(r'<[^<>\s]+@[^<>\s]+>', str(value or '')))

def metadata(message, folder, uid):
    address = parseaddr(str(message.get('From', '')))[1]
    return {
        'uid': str(uid), 'folder': folder,
        'from': str(message.get('From', '')),
        'sender_address': address,
        'subject': str(message.get('Subject', '(No subject)')),
        'date': str(message.get('Date', '')),
    }

@contextmanager
def connection():
    if not settings.yahoo_email or not settings.yahoo_password or settings.yahoo_password.startswith('replace_'):
        raise ValueError('Set YAHOO_EMAIL and YAHOO_APP_PASSWORD in backend/.env first.')
    client = imaplib.IMAP4_SSL('imap.mail.yahoo.com', 993, ssl_context=ssl.create_default_context(), timeout=30)
    try:
        client.login(settings.yahoo_email, settings.yahoo_password)
        yield client
    finally:
        try:
            client.logout()
        except Exception:
            pass

def folders(client):
    status, lines = client.list()
    if status != 'OK':
        raise RuntimeError('Could not list Yahoo folders.')
    result = {'inbox': 'INBOX'}
    for raw in lines or []:
        if not raw:
            continue
        line = raw.decode('utf-8', errors='replace')
        # Yahoo commonly exposes special-use flags such as \\Junk and \\Sent.
        match = re.match(r'^\((.*?)\)\s+(?:"[^"]*"|NIL)\s+(.*)$', line)
        if not match:
            continue
        flags, mailbox = match.groups()
        name = mailbox.strip().strip('"')
        if '\\Junk' in flags or name.lower() in ('bulk mail', 'spam', 'junk'):
            result['spam'] = name
        if '\\Sent' in flags or name.lower() in ('sent', 'sent messages'):
            result['sent'] = name
    return result

def select(client, mailbox):
    # Quote mailbox names with spaces before handing them to imaplib.
    escaped = mailbox.replace('\\', '\\\\').replace('"', '\\"')
    status, _ = client.select('"' + escaped + '"', readonly=True)
    if status != 'OK':
        raise RuntimeError('Could not open mailbox ' + mailbox)

def search(client, criterion='ALL'):
    status, data = client.uid('search', None, criterion)
    if status != 'OK':
        raise RuntimeError('Could not search mailbox.')
    return (data[0] or b'').split()

def fetch(client, uid, headers_only=False):
    query = '(BODY.PEEK[HEADER])' if headers_only else '(BODY.PEEK[])'
    status, response = client.uid('fetch', str(uid), query)
    if status != 'OK':
        raise RuntimeError('Could not fetch message.')
    for item in response:
        if isinstance(item, tuple) and isinstance(item[1], bytes):
            return email.message_from_bytes(item[1], policy=policy.default)
    raise ValueError('Message not found; it may have been moved or deleted. Refresh and try again.')

def dashboard():
    with connection() as client:
        names = folders(client)
        select(client, names['inbox'])
        all_ids = search(client)
        unread_ids = search(client, 'UNSEEN')
        counts = Counter()
        for uid in reversed(all_ids[-MAX_SAMPLE:]):
            item = fetch(client, uid.decode(), True)
            sender = parseaddr(str(item.get('From', '')))[1].lower()
            if sender:
                counts[sender] += 1
        unread = []
        for uid in reversed(unread_ids[-20:]):
            msg = fetch(client, uid.decode())
            item = metadata(msg, 'inbox', uid.decode())
            item['preview'] = ' '.join(text_body(msg).split())[:240]
            unread.append(item)
        spam_counts = Counter()
        spam_sample = 0
        if 'spam' in names:
            select(client, names['spam'])
            spam_ids = search(client)
            spam_sample = min(len(spam_ids), MAX_SAMPLE)
            for uid in reversed(spam_ids[-MAX_SAMPLE:]):
                msg = fetch(client, uid.decode(), True)
                sender = parseaddr(str(msg.get('From', '')))[1].lower()
                if sender:
                    spam_counts[sender] += 1
        return {
            'unread_count': len(unread_ids), 'inbox_sample_size': min(len(all_ids), MAX_SAMPLE),
            'spam_sample_size': spam_sample, 'spam_folder_found': 'spam' in names,
            'unread': unread,
            'top_senders': [{'address': a, 'count': n} for a, n in counts.most_common(10)],
            'top_spam_senders': [{'address': a, 'count': n} for a, n in spam_counts.most_common(10)],
        }

def get_thread(folder, uid):
    if folder not in ('inbox', 'spam', 'sent') or not str(uid).isdigit():
        raise ValueError('Invalid folder or message ID.')
    with connection() as client:
        names = folders(client)
        if folder not in names:
            raise ValueError('Folder not found.')
        select(client, names[folder])
        selected = fetch(client, uid)
        # Build a graph from recent message headers and link standard thread IDs.
        # This is deliberately bounded; old, moved or malformed messages may be absent.
        records = []
        for key in ('inbox', 'sent'):
            if key not in names:
                continue
            select(client, names[key])
            for item_uid in search(client)[-MAX_SAMPLE:]:
                item_uid = item_uid.decode()
                msg = fetch(client, item_uid, True)
                linked = ids_from(msg.get('Message-ID')) | ids_from(msg.get('References')) | ids_from(msg.get('In-Reply-To'))
                records.append((key, item_uid, msg, linked))
        linked_ids = ids_from(selected.get('Message-ID')) | ids_from(selected.get('References')) | ids_from(selected.get('In-Reply-To'))
        chosen = set()
        changed = True
        while changed and linked_ids:
            changed = False
            for key, item_uid, msg, refs in records:
                identity = (key, item_uid)
                if identity not in chosen and refs & linked_ids:
                    chosen.add(identity)
                    linked_ids |= refs
                    changed = True
        chosen.add((folder, str(uid)))
        # Retain the selected message and cap at ten recent graph matches.
        others = [r for r in records if (r[0], r[1]) in chosen and (r[0], r[1]) != (folder, str(uid))]
        others = others[-9:]
        messages = []
        for key, item_uid, _, _ in others:
            select(client, names[key])
            msg = fetch(client, item_uid)
            messages.append({**metadata(msg, key, item_uid), 'body': text_body(msg)})
        messages.append({**metadata(selected, folder, uid), 'body': text_body(selected)})
        reply_to = parseaddr(str(selected.get('Reply-To') or selected.get('From', '')))[1]
        original_subject = str(selected.get('Subject', '(No subject)'))
        subject = original_subject if original_subject.lower().startswith('re:') else 'Re: ' + original_subject
        return {'messages': messages, 'reply_to': reply_to, 'reply_subject': subject,
                'note': 'Related messages are best-effort matches from the latest 100 Inbox and 100 Sent messages (up to 10 total). Older or moved messages may be missing.'}

def send_reply(folder, uid, recipients, cc, subject, body):
    if folder not in ('inbox', 'spam', 'sent') or not str(uid).isdigit():
        raise ValueError('Invalid folder or message ID.')
    all_addresses = getaddresses([recipients, cc])
    if not recipients.strip() or not all_addresses or any(not addr or '@' not in addr or '\n' in addr or '\r' in addr for _, addr in all_addresses):
        raise ValueError('Provide valid To and Cc email addresses.')
    if not body.strip() or not subject.strip():
        raise ValueError('Subject and body cannot be empty.')
    if any(char in recipients + cc + subject for char in ('\r', '\n')):
        raise ValueError('Header fields cannot contain line breaks.')
    with connection() as client:
        names = folders(client)
        if folder not in names:
            raise ValueError('Folder not found.')
        select(client, names[folder])
        original = fetch(client, uid, True)
        message = EmailMessage()
        message['From'] = settings.yahoo_email
        message['To'] = recipients
        if cc.strip():
            message['Cc'] = cc
        message['Subject'] = subject
        original_id = str(original.get('Message-ID', '')).strip()
        if original_id and ids_from(original_id):
            message['In-Reply-To'] = original_id
            references = str(original.get('References', '')).strip()
            message['References'] = (references + ' ' + original_id).strip()
        message.set_content(body)
        with smtplib.SMTP_SSL('smtp.mail.yahoo.com', 465, context=ssl.create_default_context(), timeout=30) as smtp:
            smtp.login(settings.yahoo_email, settings.yahoo_password)
            refused = smtp.send_message(message)
        # SMTP acceptance is the send event. Do not throw after this: retry could duplicate mail.
        warning = ''
        if refused:
            warning = 'Some recipients were refused: ' + ', '.join(refused.keys()) + '. Check before retrying.'
        if 'sent' in names:
            try:
                status, _ = client.append('"' + names['sent'].replace('"', '\\"') + '"', '\\Seen', None, message.as_bytes())
                if status != 'OK':
                    warning += ' Sent, but a Sent-folder copy could not be saved.'
            except Exception:
                warning += ' Sent, but a Sent-folder copy could not be saved.'
        else:
            warning += ' Sent, but the Sent folder was not found; check Yahoo before retrying.'
        return {'message': 'Yahoo accepted the message for delivery.', 'warning': warning.strip()}
