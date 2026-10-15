"use strict";

const TZ = "Europe/Berlin";
const PADLET_STALE_HOURS = 3;   // stündlich geprüft – ab 3 h ohne Erfolg gilt es als veraltet
const WEBSITE_STALE_HOURS = 36; // täglich geprüft
const RECENT_DAYS = 14;         // so lange gelten Ausfall-Meldungen als aktuell

const ICONS = {
  phone: '<path d="M6.6 10.8a15.1 15.1 0 0 0 6.6 6.6l2.2-2.2c.3-.3.7-.4 1-.2 1.1.4 2.3.6 3.6.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1A17 17 0 0 1 3 4c0-.6.4-1 1-1h3.5c.6 0 1 .4 1 1 0 1.3.2 2.5.6 3.6.1.3 0 .7-.2 1z"/>',
  mail: '<path d="M4 5h16a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1zm8 7.2L4.8 7v10h14.4V7z"/>',
  sick: '<path d="M10 3h4v7h7v4h-7v7h-4v-7H3v-4h7z"/>',
  board: '<path d="M4 4h7v9H4zM13 4h7v5h-7zM13 11h7v9h-7zM4 15h7v5H4z"/>',
  check: '<path d="M12 2a10 10 0 1 1 0 20 10 10 0 0 1 0-20zm-1.2 13.6 6.4-6.4-1.4-1.4-5 5-2.2-2.2-1.4 1.4z"/>',
  warn: '<path d="M12 2 1 21h22zm1 15h-2v-2h2zm0-4h-2V9h2z"/>',
  web: '<path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm6.9 6h-3a15.7 15.7 0 0 0-1.4-3.6A8 8 0 0 1 18.9 8zM12 4c.8 1.2 1.5 2.5 1.9 4h-3.8c.4-1.5 1.1-2.8 1.9-4zM4.3 14a8 8 0 0 1 0-4h3.4a16.5 16.5 0 0 0 0 4zm.8 2h3a15.7 15.7 0 0 0 1.4 3.6A8 8 0 0 1 5.1 16zm3-8h-3a8 8 0 0 1 4.4-3.6C8.9 5.5 8.4 6.7 8.1 8zM12 20c-.8-1.2-1.5-2.5-1.9-4h3.8c-.4 1.5-1.1 2.8-1.9 4zm2.3-6H9.7a14.7 14.7 0 0 1 0-4h4.6a14.7 14.7 0 0 1 0 4zm.3 5.6c.6-1.1 1.1-2.3 1.4-3.6h3a8 8 0 0 1-4.4 3.6zm1.7-5.6a16.5 16.5 0 0 0 0-4h3.4a8 8 0 0 1 0 4z"/>',
  ext: '<path d="M14 3h7v7h-2V6.4l-9.3 9.3-1.4-1.4L17.6 5H14zM5 5h6v2H5v12h12v-6h2v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z"/>',
};
const icon = (name) => `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">${ICONS[name]}</svg>`;

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const $ = (id) => document.getElementById(id);

// --- Datum/Zeit in Berliner Zeit ------------------------------------------------
const ymd = (d) => new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(d); // YYYY-MM-DD
const override = new URLSearchParams(location.search).get("heute"); // Testhilfe: ?heute=2026-11-19
const NOW = override ? new Date(override + "T12:00:00") : new Date();
const TODAY = override || ymd(NOW);

const fmt = (d, opts) => new Intl.DateTimeFormat("de-DE", { timeZone: TZ, ...opts }).format(d);
const fmtTime = (iso) => fmt(new Date(iso), { hour: "2-digit", minute: "2-digit" });
const fmtDateTime = (iso) => fmt(new Date(iso), { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
const dayDiff = (a, b) => Math.round((Date.parse(a + "T12:00:00Z") - Date.parse(b + "T12:00:00Z")) / 864e5);
const hoursSince = (iso) => (Date.now() - Date.parse(iso)) / 36e5;

function relDay(iso) {
  const diff = dayDiff(TODAY, ymd(new Date(iso)));
  if (diff <= 0) return "heute, " + fmtTime(iso);
  if (diff === 1) return "gestern, " + fmtTime(iso);
  if (diff < 7) return "vor " + diff + " Tagen";
  return fmt(new Date(iso), { day: "numeric", month: "long", year: "numeric" });
}

function checkedText(iso) {
  if (!iso) return "unbekannt";
  return ymd(new Date(iso)) === ymd(new Date()) ? "heute " + fmtTime(iso) + " Uhr" : fmtDateTime(iso) + " Uhr";
}

async function getJSON(path) {
  try {
    const res = await fetch(path + "?t=" + Date.now(), { cache: "no-store" });
    if (!res.ok) throw new Error(res.status);
    return await res.json();
  } catch (e) {
    console.warn("Konnte " + path + " nicht laden", e);
    return null;
  }
}

// --- Render-Funktionen ----------------------------------------------------------
function renderQuick(web, padlet) {
  const c = (web && web.contact) || {};
  const tel = c.phone ? "tel:+49" + c.phone.replace(/\D/g, "").replace(/^0/, "") : null;
  const links = [
    tel && `<a href="${tel}">${icon("phone")}Sekretariat anrufen</a>`,
    c.sick_email && `<a href="mailto:${esc(c.sick_email)}?subject=${encodeURIComponent("Krankmeldung")}">${icon("sick")}Krank melden</a>`,
    `<a href="${esc((padlet && padlet.padlet_url) || "#")}" target="_blank" rel="noopener">${icon("board")}Padlet öffnen</a>`,
  ].filter(Boolean);
  $("quick").innerHTML = links.join("");
}

function noticeHTML(p, older) {
  const body = p.html ? `<div class="body">${p.html}</div>` : "";
  const att = p.attachment ? ` · PDF: ${esc(p.attachment.replace(/\.pdf$/i, "").replace(/_/g, " "))}` : "";
  return `<article class="notice${older ? " older" : ""}">
    <h3>${esc(p.title || "Ohne Titel")}</h3>
    <p class="meta">${esc(relDay(p.created_at))}${p.section ? " · " + esc(p.section) : ""}${att}</p>
    ${body}
    <a class="small" href="${esc(p.url)}" target="_blank" rel="noopener">Im Padlet ansehen</a>
  </article>`;
}

function renderAusfall(padlet, status) {
  const st = (status && status.padlet) || {};
  const chip = $("ausfall-chip");
  const box = $("ausfall-body");
  if (!padlet) {
    chip.className = "chip warn"; chip.textContent = "Keine Daten";
    box.innerHTML = `<div class="state warn">${icon("warn")}<p><strong>Daten konnten nicht geladen werden.</strong>Bitte direkt im <a href="https://padlet.com/veerchristina/padlet-schatzelberg-gs-eltern-7w4dic7m9gbtmex7" target="_blank" rel="noopener">Eltern-Padlet</a> nachsehen.</p></div>`;
    return;
  }

  const isRecent = (p) => p.created_at && dayDiff(TODAY, ymd(new Date(p.created_at))) <= RECENT_DAYS;
  const inSection = padlet.posts.filter((p) => padlet.ausfall_section && p.section === padlet.ausfall_section);
  const recent = inSection.filter(isRecent);
  const older = inSection.filter((p) => !isRecent(p));
  const elsewhere = padlet.posts.filter((p) => p.ausfall && !inSection.includes(p) && isRecent(p));
  const todayCount = recent.concat(elsewhere).filter((p) => ymd(new Date(p.created_at)) === TODAY).length;

  // Einzelne Fehlversuche sind normal – entscheidend ist das Alter des letzten Erfolgs
  const stale = !st.last_success || hoursSince(st.last_success) > PADLET_STALE_HOURS;
  let html = "";

  if (stale) {
    html += `<div class="state warn">${icon("warn")}<p><strong>Daten möglicherweise veraltet</strong>Letzter erfolgreicher Abruf: ${esc(checkedText(st.last_success))}. Im Zweifel bitte direkt im Padlet nachsehen.</p></div>`;
  }

  if (recent.length) {
    html += recent.map((p) => noticeHTML(p, false)).join("");
  } else {
    html += `<div class="state ok"${stale ? ' style="margin-top:10px"' : ""}>${icon("check")}<p><strong>Keine Ausfälle gemeldet</strong><span class="small muted">Spalte „${esc(padlet.ausfall_section || "Stundenausfall")}“ im Padlet · geprüft ${esc(checkedText(st.checked_at))}</span></p></div>`;
  }

  if (elsewhere.length) {
    html += `<p class="subhead">Weitere Hinweise zu Ausfällen</p>` + elsewhere.map((p) => noticeHTML(p, true)).join("");
  }
  if (older.length) {
    html += `<details class="group"><summary>Ältere Einträge (${older.length})</summary>${older.map((p) => noticeHTML(p, true)).join("")}</details>`;
  }
  if (padlet.source === "rss") {
    html += `<p class="small muted">Hinweis: Padlet-Spalten waren beim letzten Abruf nicht verfügbar; Ausfälle wurden über Stichworte erkannt.</p>`;
  }
  box.innerHTML = html;

  if (todayCount) { chip.className = "chip alert"; chip.textContent = todayCount + " neu heute"; }
  else if (recent.length) { chip.className = "chip alert"; chip.textContent = recent.length + " Meldung" + (recent.length > 1 ? "en" : ""); }
  else if (stale) { chip.className = "chip warn"; chip.textContent = "Veraltet"; }
  else { chip.className = "chip ok"; chip.textContent = elsewhere.length ? "Keine neuen Meldungen" : "Alles normal"; }
}

function renderTermine(web, padlet, status) {
  const box = $("termine-body");
  if (!web) { box.innerHTML = `<p class="muted">Termine konnten nicht geladen werden.</p>`; return; }
  const upcoming = web.events.filter((e) => !e.date || e.date >= TODAY).sort((a, b) => (a.date || "9").localeCompare(b.date || "9"));
  let html = "";
  if (!upcoming.length) {
    html += `<p class="muted">Aktuell sind auf der Schulwebsite keine kommenden Termine eingetragen.</p>`;
  } else {
    html += `<ul class="events">` + upcoming.map((e) => {
      const d = e.date ? new Date(e.date + "T12:00:00Z") : null;
      const diff = e.date ? dayDiff(e.date, TODAY) : null;
      const badge = diff === 0 ? `<span class="chip brand">Heute</span>` : diff === 1 ? `<span class="chip brand">Morgen</span>` : "";
      const when = d
        ? fmt(d, { weekday: "long" }) + (e.time ? ", " + e.time : "") + (diff > 1 ? " · in " + diff + " Tagen" : "")
        : e.date_text;
      const title = e.url ? `<a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.title)}</a>` : esc(e.title);
      return `<li class="event${diff === 0 ? " today" : ""}">
        <div class="datebox">${d ? `<span class="d">${fmt(d, { day: "numeric" })}</span><span class="m">${fmt(d, { month: "short" }).replace(".", "")}</span>` : "?"}</div>
        <div class="what"><div class="title">${title}${badge}</div><div class="when">${esc(when)}</div></div>
      </li>`;
    }).join("") + `</ul>`;
  }
  const plan = padlet && padlet.posts.find((p) => /termine/i.test(p.title));
  if (plan) html += `<p class="linkrow small">${icon("ext").replace("<svg", '<svg width="14" height="14"')} <a href="${esc(plan.url)}" target="_blank" rel="noopener">${esc(plan.title)} (PDF im Padlet)</a></p>`;
  const st = (status && status.website) || {};
  if (st.last_success && hoursSince(st.last_success) > WEBSITE_STALE_HOURS) {
    html += `<p class="small" style="color:var(--warn)">Schulwebsite zuletzt erfolgreich gelesen: ${esc(checkedText(st.last_success))}</p>`;
  }
  box.innerHTML = html;
}

function renderKontakt(web) {
  const box = $("kontakt-body");
  if (!web) { box.innerHTML = `<p class="muted">Kontaktdaten konnten nicht geladen werden.</p>`; return; }
  const c = web.contact;
  const tel = c.phone ? "tel:+49" + c.phone.replace(/\D/g, "").replace(/^0/, "") : null;
  let html = `<div class="contact-main">`;
  if (tel) html += `<a class="btn primary" href="${tel}">${icon("phone")}<span><span class="lbl">Sekretariat</span><span class="val">${esc(c.phone)}</span></span></a>`;
  if (c.email) html += `<a class="btn" href="mailto:${esc(c.email)}">${icon("mail")}<span><span class="lbl">E-Mail Sekretariat</span><span class="val">${esc(c.email)}</span></span></a>`;
  if (c.sick_email) html += `<a class="btn" href="mailto:${esc(c.sick_email)}?subject=${encodeURIComponent("Krankmeldung")}">${icon("sick")}<span><span class="lbl">Krankmeldung (Name, Klasse, voraussichtliche Dauer)</span><span class="val">${esc(c.sick_email)}</span></span></a>`;
  html += `</div>`;
  for (const g of web.contact_groups || []) {
    if (!g.people.length) continue;
    html += `<details class="group"><summary>${esc(g.label)}</summary><ul class="people">` +
      g.people.map((p) => `<li><span class="role">${esc(p.role)}</span>${esc(p.name)}<br><a href="mailto:${esc(p.email)}">${esc(p.email)}</a></li>`).join("") +
      `</ul></details>`;
  }
  html += `<p class="linkrow small"><a href="${esc(web.site_url)}" target="_blank" rel="noopener">Zur Schulwebsite</a></p>`;
  box.innerHTML = html;
}

function renderPadlet(padlet) {
  const box = $("padlet-body");
  if (!padlet) { box.innerHTML = `<p class="muted">Padlet konnte nicht geladen werden.</p>`; return; }
  const posts = padlet.posts.slice(0, 12);
  let html = posts.map((p) => {
    const isNew = p.created_at && dayDiff(TODAY, ymd(new Date(p.created_at))) <= 3;
    return `<details class="post">
      <summary><span><span class="t">${esc(p.title || "Ohne Titel")}</span><span class="s">${esc(p.section || "Padlet")} · ${esc(relDay(p.created_at))}</span></span>${isNew ? '<span class="chip brand">Neu</span>' : ""}</summary>
      <div class="body">${p.html || ""}${p.attachment ? `<p class="small muted">Anhang: ${esc(p.attachment)}</p>` : ""}
        <a class="open small" href="${esc(p.url)}" target="_blank" rel="noopener">Im Padlet öffnen</a></div>
    </details>`;
  }).join("");
  html += `<p class="linkrow small"><a href="${esc(padlet.padlet_url)}" target="_blank" rel="noopener">Ganzes Padlet öffnen</a></p>`;
  box.innerHTML = html;
}

function renderFoot(status) {
  const p = (status && status.padlet) || {};
  const w = (status && status.website) || {};
  $("foot").innerHTML = `
    <p>Padlet geprüft: ${esc(checkedText(p.checked_at))} (stündlich) · Website geprüft: ${esc(checkedText(w.checked_at))} (täglich)</p>
    <p>Inoffizielle Zusammenfassung öffentlicher Informationen. Maßgeblich sind die <a href="https://schaetzelberg-gs.de" target="_blank" rel="noopener">Schulwebsite</a> und das <a href="https://padlet.com/veerchristina/padlet-schatzelberg-gs-eltern-7w4dic7m9gbtmex7" target="_blank" rel="noopener">Eltern-Padlet</a>.</p>`;
}

async function main() {
  $("today").textContent = fmt(NOW, { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  const [padlet, web, status] = await Promise.all([
    getJSON("data/padlet.json"),
    getJSON("data/website.json"),
    getJSON("data/status.json"),
  ]);
  renderQuick(web, padlet);
  renderAusfall(padlet, status);
  renderTermine(web, padlet, status);
  renderKontakt(web);
  renderPadlet(padlet);
  renderFoot(status);
}

main();
// Beim Zurückkehren in die App (z. B. vom Homescreen) neu laden, wenn länger weg
let hiddenAt = 0;
document.addEventListener("visibilitychange", () => {
  if (document.hidden) hiddenAt = Date.now();
  else if (hiddenAt && Date.now() - hiddenAt > 15 * 60 * 1000) main();
});
