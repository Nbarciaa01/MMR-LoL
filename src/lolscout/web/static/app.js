const state = { view: "ranking", platform: "EUW1", config: null, champions: null };
const content = document.querySelector("#content");
const title = document.querySelector("#view-title");
const description = document.querySelector("#view-description");
const platform = document.querySelector("#platform");
const apiState = document.querySelector("#api-state");
const settingsDialog = document.querySelector("#settings-dialog");
const playerFields = document.querySelector("#player-fields");
const settingsMessage = document.querySelector("#settings-message");
const playerCount = document.querySelector("#player-count");

const viewCopy = {
  ranking: ["Ranking SoloQ", "Comparativa de rango, LP y MMR estimado."],
  today: ["Lo que ha pasado hoy", "Balance de LP desde las 00:00 y partidas recientes."],
  live: ["En partida", "Estado actual del grupo y composiciones detectadas."],
  builds: ["Builds por campeón", "Runas, objetos, habilidades y matchups en una consulta rápida."],
};

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

async function getJson(url) {
  const response = await fetch(url);
  let payload;
  try { payload = await response.json(); } catch { payload = {}; }
  if (!response.ok) throw new Error(payload.detail || `Error HTTP ${response.status}`);
  return payload;
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
  const icon = player.profile_icon_url || "/assets/mmr-logo-app.png";
  return `<div class="identity"><img src="${escapeHtml(icon)}" alt="" loading="lazy"><div><strong>${escapeHtml(player.game_name)}</strong><span>#${escapeHtml(player.tag_line)}</span></div></div>`;
}

function championIconUrl(championId) {
  const id = Number(championId) || 0;
  return id > 0
    ? `https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champion-icons/${id}.png`
    : "/assets/mmr-logo-app.png";
}

function renderRanking(data) {
  const rows = data.players.map((result, index) => {
    if (!result.ok) return `<div class="error-row">${escapeHtml(result.riot_id)} · ${escapeHtml(result.error)}</div>`;
    const p = result.player;
    const rank = p.soloq?.display_rank || "Sin clasificar";
    const mmr = p.estimated_mmr == null ? "—" : p.estimated_mmr.toLocaleString("es-ES");
    const winrate = p.global_winrate == null ? "—" : `${p.global_winrate}%`;
    const games = p.ranked_games == null ? "—" : p.ranked_games;
    return `<article class="player-row">
      <div class="position">${index + 1}</div>
      ${playerIdentity(p)}
      <div class="rank">${escapeHtml(rank)}</div>
      <div class="metric mmr"><strong>${mmr}</strong><span>MMR</span></div>
      <div class="metric winrate"><strong>${winrate}</strong><span>Winrate</span></div>
      <div class="metric games"><strong>${games}</strong><span>Partidas</span></div>
      <span class="source">${escapeHtml(result.source)}</span>
    </article>`;
  }).join("");
  content.innerHTML = `<div class="ranking-head"><span>#</span><span>Jugador</span><span>Rango</span><span>MMR</span><span>WR</span><span>Partidas</span><span>Fuente</span></div><div class="player-list">${rows || "<p>Sin jugadores configurados.</p>"}</div>`;
}

function renderToday(data) {
  const cards = data.players.map(result => {
    if (!result.ok) return `<article class="summary-card"><h2>${escapeHtml(result.riot_id)}</h2><p>${escapeHtml(result.error)}</p></article>`;
    const s = result.summary;
    const changeClass = s.lp_change > 0 ? "positive" : s.lp_change < 0 ? "negative" : "";
    const matches = (s.today_matches || []).map(match => {
      const outcome = match.won ? "Victoria" : "Derrota";
      const label = `${outcome} · ${match.champion} · ${match.kills}/${match.deaths}/${match.assists}`;
      return `<span class="match-result ${match.won ? "win" : "loss"}" data-outcome="${match.won ? "W" : "L"}" title="${escapeHtml(label)}" aria-label="${escapeHtml(label)}"><img src="${championIconUrl(match.champion_id)}" alt="" loading="lazy"></span>`;
    }).join("");
    return `<article class="summary-card"><header>${playerIdentity(s.player)}</header><div class="lp-change ${changeClass}">${escapeHtml(s.change_text)}</div><p>${escapeHtml(s.current_rank_text || "Sin datos de SoloQ")}</p><div class="match-strip">${matches || "<span>Sin SoloQ hoy</span>"}</div><span class="source">${escapeHtml(result.source)}</span></article>`;
  }).join("");
  content.innerHTML = `<div class="summary-grid">${cards}</div>`;
}

function renderLive(data) {
  const cards = data.players.map(result => {
    if (!result.ok) return `<article class="summary-card"><h2>${escapeHtml(result.riot_id)}</h2><p>${escapeHtml(result.error)}</p></article>`;
    const s = result.summary;
    const riotId = `${s.game_name}#${s.tag_line}`;
    const teams = (s.participants || []).map(player => `<div class="live-player"><img src="${championIconUrl(player.champion_id)}" alt="" loading="lazy"><span>${escapeHtml(player.game_name)}${player.tag_line ? `#${escapeHtml(player.tag_line)}` : ""}</span><small>${escapeHtml(player.team_color)}</small></div>`).join("");
    return `<article class="summary-card live-card"><h2>${escapeHtml(riotId)}</h2><p>${escapeHtml(s.champion || "Esperando partida")}</p><div class="live-status ${s.in_game ? "online" : ""}">${s.in_game ? escapeHtml(s.status_text || "En partida") : escapeHtml(s.status_text || "Fuera de partida")}</div>${s.in_game ? `<div class="live-roster">${teams}</div>` : ""}<span class="source">${escapeHtml(result.source)}</span></article>`;
  }).join("");
  content.innerHTML = `<div class="summary-grid">${cards}</div>`;
}

function renderChampions(champions) {
  content.innerHTML = `<div class="build-toolbar"><input id="champion-search" class="search" type="search" placeholder="Buscar campeón" autocomplete="off"></div><div id="champion-grid" class="champion-grid"></div>`;
  const grid = document.querySelector("#champion-grid");
  const draw = query => {
    const filtered = champions.filter(champion => champion.name.toLowerCase().includes(query.toLowerCase()));
    grid.innerHTML = filtered.map(champion => `<button class="champion" data-slug="${escapeHtml(champion.slug)}"><img src="${escapeHtml(champion.icon_url)}" alt="" loading="lazy"><strong>${escapeHtml(champion.name)}</strong></button>`).join("");
    grid.querySelectorAll(".champion").forEach(button => button.addEventListener("click", () => loadBuild(button.dataset.slug)));
  };
  document.querySelector("#champion-search").addEventListener("input", event => draw(event.target.value));
  draw("");
}

function assetImages(items = []) {
  return items.map(item => `<img src="${escapeHtml(item.icon_url || "/assets/mmr-logo-app.png")}" alt="${escapeHtml(item.name)}" title="${escapeHtml(item.name)}" loading="lazy">`).join("");
}

async function loadBuild(slug) {
  loading("Cargando build…");
  try {
    const build = await getJson(`/api/builds/${encodeURIComponent(slug)}`);
    const sections = [build.starting_items, build.core_build].filter(Boolean).map(section => `<section class="build-section"><h3>${escapeHtml(section.title)}</h3><div class="asset-list">${assetImages(section.items)}</div></section>`).join("");
    content.innerHTML = `<div class="build-detail"><button class="back-button" id="back-builds">← Todos los campeones</button><div class="build-title"><img src="${escapeHtml(build.icon_url)}" alt=""><div><h2>${escapeHtml(build.champion)}</h2><p>${escapeHtml(build.summary || `${build.role || ""} · ${build.patch || ""}`)}</p></div></div><div class="build-sections"><section class="build-section"><h3>Runas</h3><div class="asset-list">${assetImages([...(build.primary_runes || []), ...(build.secondary_runes || [])])}</div></section><section class="build-section"><h3>Hechizos</h3><div class="asset-list">${assetImages(build.summoner_spells)}</div></section>${sections}</div></div>`;
    document.querySelector("#back-builds").addEventListener("click", () => renderChampions(state.champions));
  } catch (error) { showError(error.message); }
}

async function loadView(force = false) {
  const [nextTitle, nextDescription] = viewCopy[state.view];
  title.textContent = nextTitle;
  description.textContent = nextDescription;
  loading();
  try {
    if (state.view === "ranking") renderRanking(await getJson(`/api/ranking?platform=${state.platform}&force_refresh=${force}`));
    if (state.view === "today") renderToday(await getJson(`/api/today?platform=${state.platform}&force_refresh=${force}`));
    if (state.view === "live") renderLive(await getJson(`/api/live?platform=${state.platform}`));
    if (state.view === "builds") {
      if (!state.champions || force) state.champions = (await getJson(`/api/builds/champions?force_refresh=${force}`)).champions;
      renderChampions(state.champions);
    }
  } catch (error) { showError(error.message); }
}

async function initialise() {
  try {
    state.config = await getJson("/api/config");
    state.platform = state.config.default_platform;
    platform.innerHTML = state.config.platforms.map(item => `<option value="${item}" ${item === state.platform ? "selected" : ""}>${item}</option>`).join("");
    apiState.className = `api-state ${state.config.riot_configured ? "is-ready" : "is-fallback"}`;
    apiState.querySelector("strong").textContent = state.config.riot_configured ? "Riot API conectada" : "Fuentes públicas activas";
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
    platform.value = state.platform;
    settingsDialog.close();
    await loadView(true);
  } catch (error) { setSettingsMessage(error.message, "error"); }
}

document.querySelectorAll(".tab").forEach(button => button.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach(tab => tab.classList.toggle("is-active", tab === button));
  state.view = button.dataset.view;
  location.hash = state.view;
  loadView();
}));
platform.addEventListener("change", () => { state.platform = platform.value; loadView(); });
document.querySelector("#refresh").addEventListener("click", () => loadView(true));
document.querySelector("#settings").addEventListener("click", openSettings);
document.querySelector("#add-player").addEventListener("click", () => addPlayerField());
document.querySelectorAll("[data-dialog-close]").forEach(button => button.addEventListener("click", () => settingsDialog.close()));
document.querySelector("#settings-form").addEventListener("submit", saveSettings);

initialise();
