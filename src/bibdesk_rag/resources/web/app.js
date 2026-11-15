"use strict";
const $ = id => document.getElementById(id);
const csrf = document.querySelector('meta[name="csrf-token"]').content;
let generation = 0;
let noticeTimer;
function notice(message) {
  $("notice").textContent = message;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => { $("notice").textContent = ""; }, 8000);
}
async function api(path, body) {
  let response, data;
  try {
    response = await fetch(path, {method: "POST", cache: "no-store", credentials: "same-origin",
      headers: {"Content-Type": "application/json", "X-CSRF-Token": csrf}, body: JSON.stringify(body)});
    data = await response.json();
  } catch (_) { throw new Error("Could not reach the local search server. Check that it is running and retry."); }
  if (!response.ok) throw new Error(data.error || "The request failed. Please retry.");
  return data;
}
function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function button(text, action) {
  const node = element("button", text); node.type = "button";
  node.addEventListener("click", async () => {
    node.disabled = true;
    try { await action(); } catch (error) { notice(error.message); }
    finally { node.disabled = false; }
  });
  return node;
}
async function copy(text) {
  try { await navigator.clipboard.writeText(text); notice("Copied to clipboard."); }
  catch (_) { notice("Could not copy. Check this browser’s clipboard permission."); }
}
async function openPDF(id, page) {
  notice("Opening in Skim… Page navigation may ask for macOS Automation permission.");
  const result = await api(`/api/attachments/${id}/open`, page ? {page} : {});
  notice(result.message);
}
function updateControls() {
  const semantic = $("mode").value === "semantic";
  const scope = $("scope").value;
  $("scope").disabled = semantic;
  const fields = {author: !semantic && scope === "metadata", year: !semantic && scope === "metadata",
    doi: !semantic && scope === "metadata", citekeys: !semantic,
    "metadata-query": !semantic && scope === "all", "per-paper": !semantic && scope !== "metadata"};
  for (const [id, enabled] of Object.entries(fields)) {
    $(id).disabled = !enabled; $(id + "-field").hidden = !enabled;
  }
  $("mode-note").textContent = semantic
    ? "Semantic searches Title and Abstract only. The first search may take longer while the local model loads. Scores are similarity, not confidence."
    : scope === "all" ? "Both searches metadata first, then selected papers’ indexed text."
    : scope === "metadata" ? "Search bibliography fields. DOI and citekey lookups use exact matching."
    : "Search extracted attachment text. Images without OCR are not searchable.";
}
$("mode").addEventListener("change", updateControls);
$("scope").addEventListener("change", updateControls);
function parameters() {
  const data = {query: $("query").value, mode: $("mode").value, top: Number($("top").value)};
  if (data.mode === "semantic") return data;
  data.scope = $("scope").value;
  for (const id of ["author", "year", "doi", "metadata-query"]) {
    if (!$(id).disabled && $(id).value.trim()) data[id.replace("-", "_")] = $(id).value.trim();
  }
  if (!$("citekeys").disabled && $("citekeys").value.trim()) {
    data.citekeys = $("citekeys").value.split(/\r?\n/).map(v => v.trim()).filter(Boolean);
  }
  if (data.citekeys && data.metadata_query) throw new Error("Choose Citekey or Metadata query, not both.");
  if (!$("per-paper").disabled) data.per_paper = Number($("per-paper").value);
  return data;
}
function renderCard(card, mode) {
  const p = card.paper;
  const node = element("article", undefined, "card");
  node.append(element("h2", p.title || "Untitled paper"));
  node.append(element("p", [p.author, p.year, p.journal || p.booktitle].filter(Boolean).join(" · "), "byline"));
  node.append(element("p", [p.citekey, p.doi].filter(Boolean).join(" · "), "identifiers"));
  const actions = element("div", undefined, "actions");
  actions.append(button("Copy citekey", () => copy(p.citekey)), button("Copy BibTeX", () => copy(p.bibtex)));
  if (card.doi_url && card.doi_url.startsWith("https://doi.org/10.")) {
    const link = element("a", "Open DOI", "doi-link"); link.href = card.doi_url;
    link.target = "_blank"; link.rel = "noopener noreferrer"; actions.append(link);
  }
  node.append(actions);
  for (const hit of card.hits) {
    const kind = mode === "semantic" ? "Semantic match" : hit.source_type === "metadata" ? "Metadata match" : "Full-text match";
    const excerpt = element("div", undefined, "excerpt");
    excerpt.append(element("span", kind, "badge"));
    if (mode === "semantic") {
      excerpt.append(element("span", `Similarity ${Number(hit.similarity_score).toFixed(3)}`, "badge"));
      if (hit.title_only) excerpt.append(element("span", "Title only · no abstract", "badge"));
    } else if (hit.chunk_id) {
      excerpt.append(element("p", hit.snippet || ""));
      const location = [hit.file_path, hit.member_path, hit.sheet_name,
        hit.page_start ? `PDF pages ${hit.page_start}–${hit.page_end}` : "",
        hit.row_start ? `Rows ${hit.row_start}–${hit.row_end}` : "", `Chunk ${hit.chunk_id}`].filter(Boolean);
      excerpt.append(element("div", location.join(" · "), "provenance"));
      if (hit.extraction_warning) excerpt.append(element("p", hit.extraction_warning, "warning hint"));
      const attachment = card.attachments.find(a => a.attachment_id === hit.attachment_id);
      if (hit.source_type === "pdf" && attachment && attachment.can_open) {
        excerpt.append(button(`Open page ${hit.page_start} in Skim`, () => openPDF(hit.attachment_id, hit.page_start)));
      }
    }
    node.append(excerpt);
  }
  const abstract = element("details", undefined, "abstract");
  abstract.append(element("summary", "Abstract"), element("p", p.abstract || "No abstract in the bibliography."));
  node.append(abstract);
  const attachments = element("div", undefined, "attachments");
  attachments.append(element("strong", "Attachments"));
  if (!card.attachments.length) attachments.append(element("p", "No linked attachments. Full text is unavailable."));
  for (const a of card.attachments) {
    const row = element("div", undefined, "attachment");
    const state = !a.exists ? "Missing file" : a.extraction_status === "ok" ? "Indexed" : `Extraction: ${a.extraction_status}`;
    row.append(element("span", `${a.name} · ${state}`));
    if (a.can_open) row.append(button("Open in Skim", () => openPDF(a.attachment_id)));
    if (a.error_message) row.title = a.error_message;
    attachments.append(row);
  }
  node.append(attachments); return node;
}
async function search(event) {
  if (event) event.preventDefault();
  const current = ++generation;
  $("results").replaceChildren();
  $("search-state").textContent = $("mode").value === "semantic" ? "Searching… Loading the local model if needed." : "Searching…";
  $("results").setAttribute("aria-busy", "true");
  try {
    const result = await api("/api/search", parameters());
    if (current !== generation) return;
    $("search-state").textContent = result.hit_count
      ? `${result.paper_count} ${result.paper_count === 1 ? "paper" : "papers"} · ${result.hit_count} returned matches` : "No results found.";
    for (const card of result.papers) $("results").append(renderCard(card, result.mode));
  } catch (error) {
    if (current === generation) $("search-state").textContent = `Search failed. ${error.message}`;
  } finally {
    if (current === generation) $("results").setAttribute("aria-busy", "false");
  }
}
$("search-form").addEventListener("submit", search);
async function initialize() {
  updateControls();
  const request = new URLSearchParams(location.hash.slice(1)).get("request");
  if (location.hash) history.replaceState(null, "", location.pathname);
  const statusRequest = api("/api/status", {}).then(info => {
    const counts = info.status.counts;
    const updated = info.status.settings.last_indexed;
    const updatedText = updated ? new Date(Number(updated) * 1000).toLocaleString() : "Not indexed";
    $("library-state").textContent = `Library: ${info.library}\nConfiguration: ${info.configuration}\nIndex: ${info.database}\n${counts.papers} papers · ${counts.attachments} attachments · ${counts.chunks} text chunks\nLast indexed: ${updatedText}\nSemantic search: ${info.semantic_enabled ? "enabled" : "not configured — use bibdesk-rag --setup"}`;
  }).catch(error => { $("library-state").textContent = `Index unavailable. ${error.message}`; });
  if (request) {
    try {
      const initial = await api("/api/initial", {request_id: request});
      $("query").value = initial.query;
      if (initial.query.trim()) await search();
    } catch (error) { $("search-state").textContent = error.message; }
  }
  await statusRequest;
}
initialize();
