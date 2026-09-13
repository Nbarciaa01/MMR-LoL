const state = { view: "home", platform: "EUW1", config: null, champions: null, homeHero: null };
const content = document.querySelector("#content");
const title = document.querySelector("#view-title");
const description = document.querySelector("#view-description");
const settingsDialog = document.querySelector("#settings-dialog");
const playerFields = document.querySelector("#player-fields");
const settingsMessage = document.querySelector("#settings-message");
const playerCount = document.querySelector("#player-count");
let activeContentRequest = null;
let contentRequestId = 0;

const viewCopy = {
  home: ["MMRQ Challenge", "El grupo MMR, en una sola vista."],
  ranking: ["Ranking SoloQ", "Clasificación oficial, LP y rendimiento del grupo."],
  live: ["En partida", "Estado actual del grupo y composiciones detectadas."],
  builds: ["Builds por campeón", "Consulta las builds de cada campeón en Lolalytics."],
};

const homeHeroes = [
  ["home-hero-ahri-base.jpg", "Ahri"],
  ["home-hero-ashe-base.jpg", "Ashe"],
  ["home-hero-diana-base.jpg", "Diana"],
  ["home-hero-irelia-base.jpg", "Irelia"],
  ["home-hero-jhin-base.jpg", "Jhin"],
  ["home-hero-kaisa-base.jpg", "Kai'Sa"],
  ["home-hero-katarina-base.jpg", "Katarina"],
  ["home-hero-leblanc-base.jpg", "LeBlanc"],
  ["home-hero-morgana-base.jpg", "Morgana"],
  ["home-hero-syndra-base.jpg", "Syndra"],
  ["home-hero-vayne-base.jpg", "Vayne"],
  ["home-hero-yasuo-base.jpg", "Yasuo"],
  ["home-hero-yone-base.jpg", "Yone"],
  ["home-hero-zyra-base.jpg", "Zyra"],
];

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
  })[char]);
}

function loading(label = "Cargando datos…") {
  content.innerHTML = `<div class="loading"><span></span><p>${escapeHtml(label)}</p></div>`;
}

function showError(message) {
  content.innerHTML = `<div class="empty-state"><strong>No se pudieron cargar los datos</strong><p>${escapeHtml(message)}</p></div>`;
}

function pickHomeHero() {
  let stored = null;
  try {
    stored = sessionStorage.getItem("mmrlol-home-hero");
  } catch {
    // Storage can be unavailable in strict privacy modes.
  }
  const savedHero = homeHeroes.find(([file]) => file === stored);
  if (savedHero) return savedHero;

  const hero = homeHeroes[Math.floor(Math.random() * homeHeroes.length)] || homeHeroes[0];
  try {
    sessionStorage.setItem("mmrlol-home-hero", hero[0]);
  } catch {
    // Keep the selected in-memory hero when persistence is unavailable.
  }
  return hero;
}

state.homeHero = pickHomeHero();
document.documentElement.style.setProperty("--session-hero", `url('/assets/${state.homeHero[0]}')`);

function renderHome() {
  const [, champion] = state.homeHero;
  content.innerHTML = `<div class="home-shell">
    <section class="home-intro">
      <div class="home-intro-brand"><div class="home-logo"><img src="/assets/mmr-logo-app.png" alt=""></div><div><p class="eyebrow">Proyecto del grupo MMR</p><h1>MMRQ Challenge</h1><strong>Rangos, LP diarios y partidas activas en una sola vista.</strong><p>Una aplicación creada para nuestro grupo de amigos y construida alrededor de nuestros Riot IDs.</p></div></div>
      <aside><p class="eyebrow">Entre amigos</p><h2>SoloQ, live y builds</h2><p>Seguimiento directo de las cuentas del grupo MMR con datos oficiales de Riot y consultas rápidas para cada partida.</p></aside>
    </section>
    <section class="home-hero">
      <div class="home-hero-badges"><span>League of Legends</span><span>${escapeHtml(champion)}</span></div>
      <div class="home-hero-copy"><p class="eyebrow">El reto del grupo MMR</p><h2>MMRQ<br>Challenge</h2><p>Nuestros rangos, LP y cada partida de hoy.</p><button class="home-primary" data-target="ranking">Ver jugadores</button></div>
      <nav class="home-actions" aria-label="Accesos directos">
        <button data-target="ranking"><span class="home-action-number">01</span><strong>Ranking</strong><small>SoloQ y LP de hoy</small></button>
        <button data-target="builds"><span class="home-action-number">02</span><strong>Builds</strong><small>Lolalytics</small></button>
        <button data-target="live"><span class="home-action-number">03</span><strong>En partida</strong><small>Live</small></button>
      </nav>
    </section>
  </div>`;
  content.querySelectorAll("[data-target]").forEach(button => button.addEventListener("click", () => navigateTo(button.dataset.target)));
}

async function getJson(url, options = {}) {
  const response = await fetch(url, options);
  let payload;
  try { payload = await response.json(); } catch { payload = {}; }
  if (!response.ok) throw new Error(payload.detail || `Error HTTP ${response.status}`);
  return payload;
}

function startContentRequest() {
  activeContentRequest?.controller.abort();
  const request = { id: ++contentRequestId, controller: new AbortController() };
  activeContentRequest = request;
  return request;
}

function isCurrentContentRequest(request) {
  return activeContentRequest === request && !request.controller.signal.aborted;
}

function finishContentRequest(request) {
  if (activeContentRequest === request) activeContentRequest = null;
}

async function putJson(url, body, token) {
  const response = await fetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  let payload;
  try { payload = await response.json(); } catch { payload = {}; }
  if (!response.ok) throw new Error(payload.detail || `Error HTTP ${response.status}`);
  return payload;
}

function playerIdentity(player) {
  const icon = player.profile_icon_url
    ? `<img src="${escapeHtml(player.profile_icon_url)}" alt="" loading="lazy">`
    : `<img src="/assets/mmr-logo-app.png" alt="">`;
  return `<div class="identity">${icon}<div><strong>${escapeHtml(player.game_name)}</strong><span>#${escapeHtml(player.tag_line)}</span></div></div>`;
}

function championIconUrl(championId) {
  return state.champions?.find(champion => champion.id === Number(championId))?.icon_url || "/assets/mmr-logo-app.png";
}

function renderRanking(data) {
  const rows = data.players.map((result, index) => {
    if (!result.ok) return `<div class="error-row">${escapeHtml(result.riot_id)} · ${escapeHtml(result.error)}</div>`;
    const p = result.player;
    const rank = p.soloq?.display_rank || "Sin clasificar";
    const winrate = p.global_winrate == null ? "—" : `${p.global_winrate}%`;
    const games = p.ranked_games == null ? "—" : p.ranked_games;
    const opggLink = p.opgg_url
      ? `<a class="opgg-link" href="${escapeHtml(p.opgg_url)}" target="_blank" rel="noopener noreferrer" title="Abrir ${escapeHtml(p.game_name)} en OP.GG" aria-label="Abrir ${escapeHtml(p.game_name)} en OP.GG"><img src="/static/assets/opgg-logo.svg" alt=""></a>`
      : `<span class="opgg-link is-disabled" aria-hidden="true"><img src="/static/assets/opgg-logo.svg" alt=""></span>`;
    return `<article class="player-row" data-position="${index + 1}" data-player-index="${index}">
      <div class="position">${index + 1}</div>
      ${playerIdentity(p)}
      <div class="rank">${escapeHtml(rank)}</div>
      <div class="recent-games" aria-label="Últimas cinco partidas SoloQ"><span class="row-label">Últimas 5 · SoloQ</span><div class="recent-strip" aria-busy="true">${'<span class="match-placeholder"></span>'.repeat(5)}</div></div>
      <div class="metric today-metric" title="Balance de LP desde las 00:00"><strong aria-busy="true">…</strong><span>Hoy</span></div>
      <div class="metric winrate"><strong>${winrate}</strong><span>Winrate</span></div>
      <div class="metric games"><strong>${games}</strong><span>Partidas</span></div>
      ${opggLink}
    </article>`;
  }).join("");
  content.innerHTML = `<div class="ranking-head"><span>#</span><span>Jugador</span><span>Rango</span><span>Últimas 5 · SoloQ</span><span>Hoy</span><span>WR</span><span>Partidas</span><span class="sr-only">OP.GG</span></div><div class="player-list">${rows || "<p>Sin jugadores configurados.</p>"}</div>`;
}

function renderRowActivity(row, activity) {
  const strip = row.querySelector(".recent-strip");
  strip.setAttribute("aria-busy", "false");
  strip.innerHTML = activity.recent_matches?.length
    ? activity.recent_matches.slice(0, 5).map(match => {
      const label = `${match.won ? "Victoria" : "Derrota"} · ${match.champion} · ${match.kills}/${match.deaths}/${match.assists} · ${match.played_at_iso ? new Date(match.played_at_iso).toLocaleString("es-ES") : ""}`;
      return `<span class="match-result ${match.won ? "win" : "loss"}" data-outcome="${match.won ? "W" : "L"}" tabindex="0" title="${escapeHtml(label)}" aria-label="${escapeHtml(label)}"><img src="${escapeHtml(championIconUrl(match.champion_id))}" alt="" loading="lazy"></span>`;
    }).join("")
    : `<span class="activity-empty" title="${escapeHtml(activity.matches_error || "")}">${activity.matches_error ? "No disponible" : "Sin partidas SoloQ"}</span>`;
  const metric = row.querySelector(".today-metric");
  const lp = activity.lp_change;
  metric.classList.toggle("positive", lp != null && lp > 0);
  metric.classList.toggle("negative", lp != null && lp < 0);
  metric.title = activity.today_error || activity.today_note || "Balance de LP desde las 00:00";
  const value = metric.querySelector("strong");
  value.textContent = lp == null ? "—" : `${lp > 0 ? "+" : ""}${lp} LP`;
  value.setAttribute("aria-busy", "false");
}

async function loadRankingActivity(data, request) {
  // Load one player at a time to avoid bursts against Riot's rate limits.
  for (const [index, result] of data.players.entries()) {
    if (!isCurrentContentRequest(request)) return;
    if (!result.ok) continue;
    const row = content.querySelector(`[data-player-index="${index}"]`);
    const params = new URLSearchParams({
      platform: state.platform, game_name: result.player.game_name, tag_line: result.player.tag_line,
    });
    try {
      const activity = await getJson(`/api/ranking/activity?${params}`, { signal: request.controller.signal });
      if (!isCurrentContentRequest(request)) return;
      renderRowActivity(row, activity);
    } catch (error) {
      if (!isCurrentContentRequest(request) || error.name === "AbortError") return;
      renderRowActivity(row, { recent_matches: null, lp_change: null, matches_error: error.message, today_error: error.message });
    }
  }
}

function renderLive(data) {
  const cards = data.players.map(result => {
    if (!result.ok) return `<article class="summary-card is-error"><h2>${escapeHtml(result.riot_id)}</h2><p>${escapeHtml(result.error)}</p></article>`;
    const s = result.summary;
    const riotId = `${s.game_name}#${s.tag_line}`;
    const teams = (s.participants || []).map(player => `<div class="live-player"><img src="${championIconUrl(player.champion_id)}" alt="" loading="lazy"><span>${escapeHtml(player.game_name)}${player.tag_line ? `#${escapeHtml(player.tag_line)}` : ""}</span><small>${escapeHtml(player.team_color)}</small></div>`).join("");
    return `<article class="summary-card live-card ${s.in_game ? "in-game" : "offline"}"><h2>${escapeHtml(riotId)}</h2><p>${escapeHtml(s.champion || "Esperando partida")}</p><div class="live-status ${s.in_game ? "online" : ""}">${s.in_game ? escapeHtml(s.status_text || "En partida") : escapeHtml(s.status_text || "Fuera de partida")}</div>${s.in_game ? `<div class="live-roster">${teams}</div>` : ""}</article>`;
  }).join("");
  content.innerHTML = `<div class="summary-grid">${cards}</div>`;
}

function renderChampions(champions) {
  content.innerHTML = `<div class="build-toolbar"><input id="champion-search" class="search" type="search" placeholder="Buscar campeón" autocomplete="off"></div><div id="champion-grid" class="champion-grid"></div>`;
  const grid = document.querySelector("#champion-grid");
  const draw = query => {
    const filtered = champions.filter(champion => champion.name.toLowerCase().includes(query.toLowerCase()));
    grid.innerHTML = filtered.map(champion => `<a class="champion" href="https://lolalytics.com/lol/${encodeURIComponent(champion.slug)}/build/" target="_blank" rel="noopener noreferrer" title="Ver builds en Lolalytics"><img src="${escapeHtml(champion.icon_url)}" alt="" loading="lazy"><strong>${escapeHtml(champion.name)}</strong></a>`).join("");
  };
  document.querySelector("#champion-search").addEventListener("input", event => draw(event.target.value));
  draw("");
}

async function loadView(force = false) {
  const request = startContentRequest();
  const view = state.view;
  const [nextTitle, nextDescription] = viewCopy[view];
  title.textContent = nextTitle;
  description.textContent = nextDescription;
  document.body.dataset.view = view;
  document.body.classList.toggle("is-home", view === "home");
  content.classList.toggle("home-content", view === "home");
  if (view === "home") {
    renderHome();
    finishContentRequest(request);
    return;
  }
  loading();
  try {
    const options = { signal: request.controller.signal };
    let data;
    if (view === "ranking") data = await getJson(`/api/ranking?platform=${state.platform}&force_refresh=${force}`, options);
    if (view === "live") data = await getJson(`/api/live?platform=${state.platform}`, options);
    if (view === "builds" && (!state.champions || force)) {
      data = await getJson(`/api/builds/champions?force_refresh=${force}`, options);
    }
    if (!isCurrentContentRequest(request)) return;
    if (view === "ranking") {
      renderRanking(data);
      await loadRankingActivity(data, request);
    }
    if (view === "live") renderLive(data);
    if (view === "builds") {
      if (data) state.champions = data.champions;
      renderChampions(state.champions);
    }
  } catch (error) {
    if (error.name !== "AbortError" && isCurrentContentRequest(request)) showError(error.message);
  } finally {
    finishContentRequest(request);
  }
}

async function initialise() {
  try {
    state.config = await getJson("/api/config");
    try { state.champions = (await getJson("/api/builds/champions")).champions; } catch { state.champions = null; }
    state.platform = state.config.default_platform;
    const requestedView = location.hash.slice(1) === "today" ? "ranking" : location.hash.slice(1);
    if (location.hash === "#today") history.replaceState(null, "", "#ranking");
    if (Object.hasOwn(viewCopy, requestedView)) state.view = requestedView;
    document.querySelectorAll(".tab").forEach(tab => tab.classList.toggle("is-active", tab.dataset.view === state.view));
    await loadView();
  } catch (error) { showError(error.message); }
}

function addPlayerField(player = { game_name: "", tag_line: "" }) {
  const row = document.createElement("div");
  row.className = "player-field";
  row.innerHTML = `<input class="game-name" type="text" value="${escapeHtml(player.game_name)}" placeholder="Nombre" required><span>#</span><input class="tag-line" type="text" value="${escapeHtml(player.tag_line)}" placeholder="Tag" required><button type="button" class="remove-player" title="Eliminar" aria-label="Eliminar jugador">×</button>`;
  row.querySelector(".remove-player").addEventListener("click", () => {
    if (playerFields.children.length > 1) {
      row.remove();
      updatePlayerCount();
    }
  });
  playerFields.append(row);
  updatePlayerCount();
}

function updatePlayerCount() {
  const count = playerFields.children.length;
  playerCount.textContent = `${count} ${count === 1 ? "jugador" : "jugadores"}`;
}

function setSettingsMessage(message = "", state = "") {
  settingsMessage.textContent = message;
  settingsMessage.dataset.state = state;
}

function openSettings() {
  setSettingsMessage(state.config.management_enabled ? "" : "Configura MMRLOL_ADMIN_TOKEN en el servidor para habilitar los cambios.", state.config.management_enabled ? "" : "error");
  document.querySelector("#admin-token").value = sessionStorage.getItem("mmrlol-admin-token") || "";
  const settingsPlatform = document.querySelector("#settings-platform");
  settingsPlatform.innerHTML = state.config.platforms.map(item => `<option value="${item}" ${item === state.platform ? "selected" : ""}>${item}</option>`).join("");
  playerFields.innerHTML = "";
  state.config.players.forEach(addPlayerField);
  settingsDialog.showModal();
}

async function saveSettings(event) {
  event.preventDefault();
  const token = document.querySelector("#admin-token").value;
  const players = [...playerFields.querySelectorAll(".player-field")].map(row => ({
    game_name: row.querySelector(".game-name").value,
    tag_line: row.querySelector(".tag-line").value,
  }));
  setSettingsMessage("Validando Riot IDs y guardando cambios…");
  try {
    await putJson("/api/config", {
      default_platform: document.querySelector("#settings-platform").value,
      players,
    }, token);
    sessionStorage.setItem("mmrlol-admin-token", token);
    state.config = await getJson("/api/config");
    state.platform = state.config.default_platform;
    settingsDialog.close();
    await loadView(true);
  } catch (error) { setSettingsMessage(error.message, "error"); }
}

function navigateTo(view) {
  if (!Object.hasOwn(viewCopy, view)) return;
  document.querySelectorAll(".tab").forEach(tab => tab.classList.toggle("is-active", tab.dataset.view === view));
  state.view = view;
  location.hash = state.view;
  loadView();
}

document.querySelectorAll(".tab").forEach(button => button.addEventListener("click", () => navigateTo(button.dataset.view)));
window.addEventListener("hashchange", () => {
  const view = location.hash.slice(1) === "today" ? "ranking" : location.hash.slice(1);
  if (location.hash === "#today") history.replaceState(null, "", "#ranking");
  if (Object.hasOwn(viewCopy, view) && view !== state.view) navigateTo(view);
});
document.querySelector("#refresh").addEventListener("click", () => loadView(true));
document.querySelector("#settings").addEventListener("click", openSettings);
document.querySelector("#add-player").addEventListener("click", () => addPlayerField());
document.querySelectorAll("[data-dialog-close]").forEach(button => button.addEventListener("click", () => settingsDialog.close()));
document.querySelector("#settings-form").addEventListener("submit", saveSettings);

initialise();
