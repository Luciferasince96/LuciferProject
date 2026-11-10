import { useState } from 'react';

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `Request failed (${response.status})`);
  return data;
}

function SenderList({ title, senders, empty }) {
  return <section className="card"><h2>{title}</h2>{senders.length ?
    <ul>{senders.map((item) => <li key={item.address}><span>{item.address}</span><strong>{item.count}</strong></li>)}</ul> :
    <p className="muted">{empty}</p>}</section>;
}

export default function App() {
  const [dashboard, setDashboard] = useState(null);
  const [selected, setSelected] = useState(null);
  const [thread, setThread] = useState(null);
  const [to, setTo] = useState('');
  const [cc, setCc] = useState('');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [instructions, setInstructions] = useState('');
  const [summary, setSummary] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function perform(action) {
    setBusy(true); setError(''); setNotice('');
    try { await action(); } catch (exception) { setError(exception.message); }
    finally { setBusy(false); }
  }
  function loadDashboard() {
    perform(async () => { setDashboard(await api('/api/dashboard')); setSummary(''); });
  }
  function openMessage(message) {
    perform(async () => {
      const result = await api(`/api/thread/${message.folder}/${message.uid}`);
      setSelected(message); setThread(result); setTo(result.reply_to); setCc('');
      setSubject(result.reply_subject); setBody(''); setInstructions('');
    });
  }
  function generateDraft() {
    if (!window.confirm('Send the selected email and matched thread content to OpenAI to generate a draft?')) return;
    perform(async () => {
      const result = await api('/api/draft', { method: 'POST', body: JSON.stringify({ folder: selected.folder, uid: selected.uid, instructions }) });
      setBody(result.draft); setNotice('Draft generated. Check the facts, recipients and wording before sending.');
    });
  }
  function summarise() {
    if (!window.confirm('Send the displayed unread email previews to OpenAI for summarisation?')) return;
    perform(async () => {
      const result = await api('/api/summarise', { method: 'POST', body: JSON.stringify({ messages: dashboard.unread.map(({ from, subject, preview }) => ({ from, subject, preview })) }) });
      setSummary(result.summary);
    });
  }
  function send(event) {
    event.preventDefault();
    if (!window.confirm(`Send this email to ${to}${cc ? `, cc ${cc}` : ''}?`)) return;
    perform(async () => {
      const result = await api('/api/send', { method: 'POST', body: JSON.stringify({ folder: selected.folder, uid: selected.uid, to, cc, subject, body }) });
      setNotice(`${result.message} ${result.warning || ''}`); setBody('');
    });
  }
  return <main>
    <header><div><p className="eyebrow">LOCAL PROTOTYPE</p><h1>My email manager</h1><p>Review your Yahoo inbox and prepare replies.</p></div>
      <button disabled={busy} onClick={loadDashboard}>{busy ? 'Working…' : 'Load / refresh inbox'}</button></header>
    <p className="security">Local use only. This prototype has no sign-in; do not publish it on the internet.</p>
    {error && <div role="alert" className="alert error">{error}</div>}
    {notice && <div role="status" className="alert success">{notice}</div>}
    {!dashboard && <section className="card"><h2>Get started</h2><p>Start the backend, configure your Yahoo app password, then select Load / refresh inbox.</p></section>}
    {dashboard && <>
      <div className="metrics"><section className="card"><p>Unread in Inbox</p><strong className="metric">{dashboard.unread_count}</strong><small>Showing up to 20 unread messages below</small></section>
        <section className="card"><p>Inbox analysed</p><strong className="metric">{dashboard.inbox_sample_size}</strong><small>Latest 100 messages at most</small></section>
        <section className="card"><p>Spam analysed</p><strong className="metric">{dashboard.spam_sample_size}</strong><small>{dashboard.spam_folder_found ? 'Latest 100 messages at most' : 'Spam folder not found'}</small></section></div>
      <div className="columns"><SenderList title="Top inbox senders" senders={dashboard.top_senders} empty="No senders found in the sample." />
        <SenderList title="Top spam-folder senders" senders={dashboard.top_spam_senders} empty={dashboard.spam_folder_found ? 'No senders found in the sample.' : 'Yahoo spam folder could not be detected.'} /></div>
      <section className="card"><div className="row"><h2>Unread messages</h2><button className="secondary" disabled={busy || !dashboard.unread.length} onClick={summarise}>AI summary of previews</button></div>
        {summary && <div className="summary"><strong>AI summary (preview-based)</strong><p className="preserve">{summary}</p></div>}
        {dashboard.unread.length ? dashboard.unread.map((message) => <button className="message" key={`${message.folder}-${message.uid}`} disabled={busy} onClick={() => openMessage(message)}>
          <span><strong>{message.subject}</strong><small>{message.from} · {message.date}</small><span className="preview">{message.preview || '[No text preview]'}</span></span><span>Open →</span></button>) : <p>No unread messages found.</p>}</section>
    </>}
    {thread && selected && <section className="card"><h2>Conversation and reply</h2><p className="muted">{thread.note} Message bodies and quoted history may be truncated. Viewing does not mark messages read.</p>
      {thread.messages.map((message) => <article className="thread" key={`${message.folder}-${message.uid}`}><strong>{message.subject}</strong><small>{message.from} · {message.date} · {message.folder}</small><p className="preserve">{message.body}</p></article>)}
      <h3>Prepare reply</h3><label>Optional drafting instructions<input value={instructions} onChange={(event) => setInstructions(event.target.value)} placeholder="e.g. Politely ask for more details" /></label>
      <button type="button" className="secondary" disabled={busy} onClick={generateDraft}>Generate AI draft</button>
      <form onSubmit={send}><label>To<input required value={to} onChange={(event) => setTo(event.target.value)} placeholder="person@example.com" /></label>
        <label>Cc<input value={cc} onChange={(event) => setCc(event.target.value)} placeholder="Optional; comma-separated" /></label>
        <label>Subject<input required value={subject} onChange={(event) => setSubject(event.target.value)} /></label>
        <label>Reply<textarea required rows="10" value={body} onChange={(event) => setBody(event.target.value)} /></label>
        <button disabled={busy} type="submit">Review and send</button></form></section>}
  </main>;
}
