const $ = (id) => document.getElementById(id);

// Resolve API paths relative to where this page is actually served, so the
// app works whether it's loaded directly on :8042 or embedded under a
// sub-path by the desktop app.
const API_BASE = new URL(".", document.baseURI).href;

async function api(path, opts) {
  const url = new URL(path.replace(/^\//, ""), API_BASE).href;
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function refreshClubs() {
  const clubs = await api("/api/clubs");
  const ul = $("clubs");
  ul.replaceChildren();
  for (const club of clubs) {
    const li = document.createElement("li");
    li.textContent = club.name + " ";
    const btn = document.createElement("button");
    btn.textContent = "remove";
    btn.className = "remove";
    btn.onclick = async () => {
      await api(`/api/clubs/${club.team_id}`, { method: "DELETE" });
      refreshClubs();
    };
    li.appendChild(btn);
    ul.appendChild(li);
  }
  if (!clubs.length) {
    const li = document.createElement("li");
    li.textContent = "No clubs tracked yet.";
    ul.appendChild(li);
  }
}

async function loadLeagues() {
  const leagues = await api("/api/leagues");
  const sel = $("league");
  sel.replaceChildren(new Option("Pick a league…", ""));
  for (const l of leagues) sel.appendChild(new Option(l.name, l.slug));
}

$("league").onchange = async () => {
  const league = $("league").value;
  const teamSel = $("team");
  teamSel.disabled = true;
  $("add").disabled = true;
  if (!league) return;
  teamSel.replaceChildren(new Option("Loading…", ""));
  try {
    const teams = await api(`/api/leagues/${league}/teams`);
    teamSel.replaceChildren();
    for (const t of teams) teamSel.appendChild(new Option(t.name, t.id));
    teamSel.disabled = false;
    $("add").disabled = false;
  } catch (e) {
    teamSel.replaceChildren(new Option("Failed to load teams", ""));
    $("status").textContent = `Error: ${e.message}`;
  }
};

$("add").onclick = async () => {
  const teamSel = $("team");
  const body = {
    league: $("league").value,
    team_id: teamSel.value,
    name: teamSel.selectedOptions[0].textContent,
  };
  await api("/api/clubs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  $("status").textContent = `Added ${body.name} — generating its announcement audio…`;
  refreshClubs();
};

for (const btn of document.querySelectorAll("[data-test]")) {
  btn.onclick = async () => {
    await api(`/api/test/${btn.dataset.test}`, { method: "POST" });
    $("status").textContent = `Queued test: ${btn.dataset.test}`;
  };
}

async function init() {
  try {
    await loadLeagues();
    await refreshClubs();
  } catch (e) {
    $("status").textContent = `Could not reach the app backend: ${e.message}. Try reopening this page.`;
    $("status").classList.add("error");
  }
}

init();
